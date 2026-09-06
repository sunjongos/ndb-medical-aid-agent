"""Boundary-value tests: 12 programs × edge thresholds."""
import pathlib, sys, pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from agent.kb import KB
from agent.models import Patient, Encounter, Costs
from agent.facts import derive
from agent.rules import run_all

kb = KB()
M4 = kb.median_income(4)  # 6,494,738

def R(p: dict, e: dict):
    P = Patient(**{"name": "T", "age": 50, "household_size": 4, **p})
    E = Encounter(**{"department": "spine", "setting": "inpatient", **e})
    return {r.program_id: r for r in run_all(derive(P, E, kb), kb)}

BIG = {"costs": {"covered_copay": 1_000_000, "full_self_pay": 500_000, "noncovered": 40_000_000}, "surgery": True, "surgery_done": True, "discharge_date": "2026-09-01"}

# ---- 재난적 의료비 ----
@pytest.mark.parametrize("pct,band", [(40, "기초수급자·차상위"), (50, "기준중위소득 50% 이하"), (50.1, "기준중위소득 50~100%"), (100, "기준중위소득 50~100%"), (100.1, "기준중위소득 100~200% (개별심사)"), (200, "기준중위소득 100~200% (개별심사)")])
def test_cat_bands(pct, band):
    p = {"income_pct": pct, "assets": 100_000_000}
    if pct == 40: p["beneficiary"] = "basic"
    r = R(p, BIG)["catastrophic_medical"]
    assert r.status != "ineligible", r.reasons
    assert r.band == band

def test_cat_over_200_ineligible():
    assert R({"income_pct": 200.1, "assets": 1}, BIG)["catastrophic_medical"].status == "ineligible"

@pytest.mark.parametrize("assets,ok", [(700_000_000, True), (700_000_001, False)])
def test_cat_asset_cap(assets, ok):
    r = R({"income_pct": 80, "assets": assets}, BIG)["catastrophic_medical"]
    assert (r.status != "ineligible") == ok

def test_cat_burden_threshold_basic():
    e = {**BIG, "costs": {"covered_copay": 0, "noncovered": 800_000}}
    assert R({"beneficiary": "basic", "assets": 1}, e)["catastrophic_medical"].status == "ineligible"
    e["costs"]["noncovered"] = 800_001
    assert R({"beneficiary": "basic", "assets": 1}, e)["catastrophic_medical"].status != "ineligible"

def test_cat_single_household_le50_threshold():
    e = {**BIG, "costs": {"noncovered": 1_200_001}}
    assert R({"income_pct": 45, "assets": 1, "household_size": 1}, e)["catastrophic_medical"].status != "ineligible"
    e["costs"]["noncovered"] = 1_200_000
    assert R({"income_pct": 45, "assets": 1, "household_size": 1}, e)["catastrophic_medical"].status == "ineligible"

def test_cat_outpatient_needs_severe():
    e = {**BIG, "setting": "outpatient"}
    assert R({"income_pct": 80, "assets": 1}, e)["catastrophic_medical"].status == "ineligible"
    e["diagnosis_codes"] = ["C50.9"]
    assert R({"income_pct": 80, "assets": 1}, e)["catastrophic_medical"].status != "ineligible"

def test_cat_excludes_single_room_and_manual():
    e = {**BIG, "costs": {"noncovered": 40_000_000, "single_room": 1_000_000, "manual_therapy": 500_000}}
    r = R({"income_pct": 80, "assets": 1}, e)["catastrophic_medical"]
    assert r.estimate == int((40_000_000 - 1_500_000) * 0.6)

def test_cat_cap_5000():
    e = {**BIG, "costs": {"noncovered": 200_000_000}}
    assert R({"income_pct": 80, "assets": 1}, e)["catastrophic_medical"].estimate == 50_000_000

def test_cat_burden_ratio_le100():
    # 4인 가구 80%: 연소득 ≈ 62.3M → 10% ≈ 6.23M
    annual = M4 * 0.8 * 12
    e = {**BIG, "costs": {"noncovered": int(annual * 0.10) + 1}}
    assert R({"income_pct": 80, "assets": 1}, e)["catastrophic_medical"].status != "ineligible"
    e["costs"]["noncovered"] = int(annual * 0.10) - 1
    assert R({"income_pct": 80, "assets": 1}, e)["catastrophic_medical"].status == "ineligible"

def test_cat_deadline_180():
    assert R({"income_pct": 80, "assets": 1}, BIG)["catastrophic_medical"].deadline == "2027-02-28"

# ---- 긴급복지 국가형 / 경기도 ----
@pytest.mark.parametrize("pct,nat,gg", [(75, True, True), (75.1, False, True), (100, False, True), (100.1, False, False)])
def test_emergency_income_edges(pct, nat, gg):
    p = {"income_pct": pct, "crisis_events": ["job_loss"]}
    r = R(p, BIG)
    assert (r["emergency_welfare_national"].status != "ineligible") == nat
    assert (r["emergency_welfare_gyeonggi"].status != "ineligible") == gg

def test_emergency_requires_crisis():
    r = R({"income_pct": 50}, BIG)
    assert r["emergency_welfare_national"].status == "ineligible"
    assert r["living_support"].status == "ineligible"

def test_main_earner_surgery_implies_crisis():
    r = R({"income_pct": 50, "is_main_earner": True}, BIG)
    assert r["emergency_welfare_national"].status != "ineligible"

def test_caregiver_only_gyeonggi():
    r = R({"income_pct": 90, "caregiver_needed": True}, BIG)
    assert r["emergency_welfare_gyeonggi"].status != "ineligible"
    assert r["emergency_welfare_national"].status == "ineligible"
    assert r["emergency_welfare_gyeonggi"].estimate == 6_000_000

def test_non_gyeonggi_resident():
    r = R({"income_pct": 50, "crisis_events": ["job_loss"], "region_province": "서울특별시"}, BIG)
    assert r["emergency_welfare_gyeonggi"].status == "ineligible"

# ---- 산정특례 / 암 / 희귀 ----
@pytest.mark.parametrize("code,cat", [("C34.1", "cancer"), ("I63.9", "cerebrovascular"), ("I21.0", "cardiac"), ("M45", "intractable"), ("G12.2", "rare"), ("A15.0", "tuberculosis"), ("M51.1", "none")])
def test_special_map(code, cat):
    r = R({"income_pct": 80}, {**BIG, "diagnosis_codes": [code]})
    assert (r["special_disease"].status != "ineligible") == (cat != "none")
    if cat != "none":
        assert r["special_disease"].band.startswith(cat)

def test_cancer_priority_over_stroke():
    E = Encounter(department="internal", setting="inpatient", diagnosis_codes=["I63.9", "C18.7"])
    assert derive(Patient(name="x", age=70), E, kb)["special_category"] == "cancer"

@pytest.mark.parametrize("benef,ok", [("medical_aid_2", True), ("near_poor", True), ("basic", False), ("none", False)])
def test_cancer_aid_beneficiary(benef, ok):
    r = R({"beneficiary": benef}, {**BIG, "diagnosis_codes": ["C16.9"]})["cancer_aid"]
    assert (r.status != "ineligible") == ok

@pytest.mark.parametrize("pct,ok", [(140, True), (140.1, False)])
def test_rare_income(pct, ok):
    r = R({"income_pct": pct}, {**BIG, "diagnosis_codes": ["G12.2"]})["rare_disease_aid"]
    assert (r.status != "ineligible") == ok

# ---- 인공관절 ----
@pytest.mark.parametrize("age,benef,done,region,status", [
    (60, "basic", False, "남양주시", "likely"),     # verified=false → likely
    (59, "basic", False, "남양주시", "ineligible"),
    (70, "none", False, "남양주시", "ineligible"),
    (70, "basic", True, "남양주시", "ineligible"),
    (70, "single_parent", False, "구리시", "likely")])
def test_knee(age, benef, done, region, status):
    r = R({"age": age, "beneficiary": benef, "region_city": region},
          {"department": "joint", "procedure_knee_replacement": True, "surgery": True, "surgery_done": done, "knees": 2})["knee_replacement"]
    assert r.status == status, r.reasons + r.warnings
    if status != "ineligible":
        assert r.estimate == 2_400_000
        if region != "남양주시":
            assert any("타 지자체" in w for w in r.warnings)

# ---- 상한제 / 의료급여 / 치매 / 65+ ----
def test_ceiling_uses_ytd():
    r = R({"income_decile": 1, "covered_copay_ytd": 500_000}, {**BIG, "costs": {"covered_copay": 600_000}})["copay_ceiling"]
    assert r.estimate == 500_000 + 600_000 - 900_000

def test_ceiling_medical_aid_ineligible():
    assert R({"beneficiary": "medical_aid_1"}, BIG)["copay_ceiling"].status == "ineligible"

@pytest.mark.parametrize("benef,copay,est", [("medical_aid_1", 30_000, 5_000), ("medical_aid_2", 250_000, 25_000), ("medical_aid_2", 200_000, 0)])
def test_medical_aid_refund(benef, copay, est):
    r = R({"beneficiary": benef}, {**BIG, "costs": {"covered_copay": copay}})["medical_aid_copay_refund"]
    assert r.estimate == est

@pytest.mark.parametrize("age,concern,ok", [(60, True, True), (59, True, False), (75, False, False)])
def test_dementia(age, concern, ok):
    r = R({"age": age, "cognitive_concern": concern, "income_pct": 100}, BIG)["dementia_aid"]
    assert (r.status != "ineligible") == ok

@pytest.mark.parametrize("age,ok", [(65, True), (64, False)])
def test_senior65(age, ok):
    assert (R({"age": age}, BIG)["senior65_benefits"].status != "ineligible") == ok

# ---- 검증 플래그 ----
def test_unverified_section_downgrades():
    r = R({"income_decile": 3}, {**BIG, "costs": {"covered_copay": 5_000_000}})["copay_ceiling"]
    assert r.status == "likely" and any("미검증" in w for w in r.warnings)
