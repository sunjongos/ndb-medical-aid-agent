"""Derive atomic facts from Patient + Encounter. Each fact is either a value or None (= unknown)."""
from __future__ import annotations
from typing import Dict, Any
from .models import Patient, Encounter
from .kb import KB

BENEF_ORDER = {"medical_aid_1": 0, "medical_aid_2": 0, "basic": 0, "near_poor": 1, "single_parent": 2, "none": 9}


def derive(p: Patient, e: Encounter, kb: KB) -> Dict[str, Any]:
    f: Dict[str, Any] = {}
    # income as % of 기준중위소득
    if p.income_pct is not None:
        f["income_pct"] = float(p.income_pct)
    elif p.monthly_income is not None:
        f["income_pct"] = round(100.0 * p.monthly_income / kb.median_income(p.household_size), 1)
    elif p.beneficiary in ("basic", "medical_aid_1", "medical_aid_2"):
        f["income_pct"] = 40.0   # 수급자는 중위 40% 이하로 간주 (생계급여 32%, 의료급여 40%)
    elif p.beneficiary == "near_poor":
        f["income_pct"] = 50.0
    else:
        f["income_pct"] = None
    f["income_decile"] = p.income_decile
    f["age"] = p.age
    f["assets"] = p.assets
    f["financial_assets"] = p.financial_assets
    f["beneficiary"] = p.beneficiary
    f["insurance"] = "medical_aid" if p.beneficiary.startswith("medical_aid") else p.insurance
    f["household_size"] = p.household_size
    f["region_gyeonggi"] = ("경기" in (p.region_province or ""))
    f["region_city"] = p.region_city
    f["covered_copay_ytd"] = (p.covered_copay_ytd or 0) + e.costs.covered_copay
    f["cognitive_concern"] = bool(p.cognitive_concern)
    f["caregiver_needed"] = bool(p.caregiver_needed)

    nat = set(kb.thresholds["emergency_welfare_national"]["crisis_events"])
    gg = nat | set(kb.thresholds["emergency_welfare_gyeonggi"]["extra_crisis_events"])
    ev = set(p.crisis_events)
    # implicit crisis: main earner hospitalised with surgery
    if p.is_main_earner and e.setting == "inpatient" and e.surgery:
        ev.add("main_earner_serious_illness")
    if p.caregiver_needed:
        ev.add("caregiving_income_loss")
    f["crisis_events"] = sorted(ev)
    f["has_crisis_event"] = bool(ev & nat)
    f["has_crisis_event_gg"] = bool(ev & gg)

    # special disease category
    cat = e.special_category_override or kb.special_category(e.diagnosis_codes)
    if e.flags.get("severe_trauma"):
        cat = cat or "severe_trauma"
    f["special_category"] = cat or "none"
    f["special_registered"] = bool(e.special_disease_registered)
    f["setting"] = e.setting
    f["department"] = e.department
    allowed = set(kb.thresholds["catastrophic"]["outpatient_allowed_categories"])
    f["setting_ok_for_catastrophic"] = (e.setting == "inpatient") or (cat in allowed)
    f["mild_disease_only"] = bool(e.flags.get("mild_disease_only", False))
    f["surgery"] = bool(e.surgery)
    f["surgery_done"] = bool(e.surgery_done)
    f["procedure_knee_replacement"] = bool(e.procedure_knee_replacement)
    f["knees"] = e.knees
    c = e.costs
    f["patient_burden"] = c.patient_burden
    f["covered_copay"] = c.covered_copay
    f["covered_copay_uncapped"] = c.covered_copay_uncapped
    f["full_self_pay"] = c.full_self_pay
    f["noncovered"] = c.noncovered
    f["excluded_costs"] = c.single_room + c.manual_therapy
    f["private_insurance_paid"] = p.private_insurance_paid or 0
    f["other_public_aid_received"] = p.other_public_aid_received or 0
    f["last_date"] = e.last_date
    return f
