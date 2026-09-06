import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from agent.kb import KB
from agent.models import load_patient, load_encounter
from agent.facts import derive
from agent.rules import run_all

EX = pathlib.Path(__file__).resolve().parent.parent / "examples"

def _run(p, e):
    kb = KB()
    P = load_patient(json.loads((EX / p).read_text(encoding="utf-8")))
    E = load_encounter(json.loads((EX / e).read_text(encoding="utf-8")))
    facts = derive(P, E, kb)
    return {r.program_id: r for r in run_all(facts, kb)}, facts

def test_spine_catastrophic_eligible():
    R, f = _run("patient_spine.json", "encounter_spine.json")
    r = R["catastrophic_medical"]
    assert r.status in ("eligible", "likely"), r.reasons
    assert r.band.startswith("기준중위소득 50~100%")
    # base = 300k + 500k + 6,000k - 600k = 6,200k ; minus 실손 4,000k = 2,200k ; x0.6
    assert r.estimate == int(2_200_000 * 0.6)
    assert r.deadline == "2027-02-28"

def test_spine_gyeonggi_caregiver():
    R, f = _run("patient_spine.json", "encounter_spine.json")
    r = R["emergency_welfare_gyeonggi"]
    assert r.status in ("eligible", "likely")
    assert r.estimate == 3_000_000 + 3_000_000
    assert R["emergency_welfare_national"].status == "ineligible"  # income 69% > 75%? no -> check crisis
    assert R["knee_replacement"].status == "ineligible"

def test_internal_cancer_pathway():
    R, f = _run("patient_internal.json", "encounter_internal.json")
    assert f["special_category"] == "cancer"
    assert R["special_disease"].status in ("eligible", "likely")
    assert R["cancer_aid"].status in ("eligible", "likely")
    assert R["catastrophic_medical"].band == "기초수급자·차상위"
    assert R["medical_aid_copay_refund"].status in ("eligible", "likely")
    assert R["copay_ceiling"].status == "ineligible"
    assert R["dementia_aid"].status in ("eligible", "likely")

def test_unknown_income_goes_review():
    kb = KB()
    P = load_patient({"name": "X", "age": 50, "household_size": 3})
    E = load_encounter({"department": "surgery", "setting": "inpatient", "surgery": True,
                        "costs": {"covered_copay": 1_000_000, "noncovered": 2_000_000}})
    R = {r.program_id: r for r in run_all(derive(P, E, kb), kb)}
    assert R["catastrophic_medical"].status == "review"
    assert R["rare_disease_aid"].status == "ineligible"
    assert R["special_disease"].status == "ineligible"
