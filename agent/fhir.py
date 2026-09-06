"""FHIR R4 Bundle → agent Patient/Encounter dicts.

Pre-EMR integration layer. When the hospital EMR is connected, its export (or a FHIR facade) only needs to
produce the resources below; nothing downstream changes.

Resources consumed
  Patient        birthDate → age; extension[household-size]; address → region
  Coverage       type.coding → insurance/beneficiary  (KR NHI: employee/regional/medical-aid-1/2, near-poor)
  Encounter      class (IMP/AMB) → setting; period → admission/discharge; serviceType → department
  Condition      code.coding (ICD-10-KR / ICD-10) → diagnosis_codes; text → diagnosis_text
  Procedure      code → surgery / knee replacement; status completed→surgery_done; bodySite laterality → knees
  Claim | ExplanationOfBenefit  item.category (NDB cost-category CodeSystem) + net → costs
  Observation    social determinants (income, assets, main earner, crisis, caregiver, cognition) via NDB codes

Code systems (local, versioned)
  http://ndb.hospital/fhir/CodeSystem/cost-category : covered-copay | covered-copay-uncapped | full-self-pay | noncovered | single-room | manual-therapy
  http://ndb.hospital/fhir/CodeSystem/sdoh          : monthly-income | assets | financial-assets | main-earner | crisis-event | caregiver-needed | cognitive-concern | private-insurance-paid | covered-copay-ytd
  http://ndb.hospital/fhir/CodeSystem/coverage-type  : nhi-employee | nhi-regional | medical-aid-1 | medical-aid-2 | near-poor | single-parent
Unmapped resources/codes are returned in `unmapped` so nothing is silently dropped.
"""
from __future__ import annotations
from datetime import date
from typing import Any, Dict, List, Tuple

CS = "http://ndb.hospital/fhir/CodeSystem/"
DEPT_MAP = {"spine": "spine", "척추": "spine", "joint": "joint", "관절": "joint", "orthopedics": "joint",
            "internal": "internal", "내과": "internal", "neuro": "neuro", "신경": "neuro", "surgery": "surgery", "외과": "surgery"}
KNEE_HINTS = ("knee", "무릎", "슬관절", "tka", "total knee", "arthroplasty", "인공관절")
SNOMED_KNEE = {"609588000", "179344006", "19063003"}  # total knee replacement family (illustrative)


def _age(birth: str, on: date | None = None) -> int:
    b = date.fromisoformat(birth[:10]); on = on or date.today()
    return on.year - b.year - ((on.month, on.day) < (b.month, b.day))


def _codes(cc: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    return [(c.get("system", ""), c.get("code", ""), c.get("display", "")) for c in (cc or {}).get("coding", [])]


def _ndb_code(cc: Dict[str, Any], kind: str) -> str | None:
    for sys_, code, _ in _codes(cc):
        if sys_ == CS + kind:
            return code
    return None


def _num(res: Dict[str, Any]) -> float | None:
    q = res.get("valueQuantity")
    if q and "value" in q:
        return q["value"]
    if "valueInteger" in res:
        return res["valueInteger"]
    if "valueDecimal" in res:
        return res["valueDecimal"]
    m = res.get("valueMoney")
    if m and "value" in m:
        return m["value"]
    return None


def fhir_to_case(bundle: Dict[str, Any], as_of: date | None = None) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    """Return (patient_dict, encounter_dict, unmapped_notes)."""
    P: Dict[str, Any] = {"beneficiary": "none", "insurance": "nhi_employee", "crisis_events": [], "region_province": "경기도", "region_city": "남양주시"}
    E: Dict[str, Any] = {"diagnosis_codes": [], "flags": {}, "costs": {}}
    un: List[str] = []
    entries = [e.get("resource", {}) for e in bundle.get("entry", [])]
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for r in entries:
        by_type.setdefault(r.get("resourceType", "?"), []).append(r)

    for pt in by_type.get("Patient", [])[:1]:
        nm = (pt.get("name") or [{}])[0]
        P["name"] = nm.get("text") or (nm.get("family", "") + "".join(nm.get("given", []))) or "환자"
        if pt.get("birthDate"):
            P["age"] = _age(pt["birthDate"], as_of)
        P["sex"] = {"male": "M", "female": "F"}.get(pt.get("gender"))
        for ext in pt.get("extension", []):
            if ext.get("url", "").endswith("household-size"):
                P["household_size"] = ext.get("valueInteger")
        for ad in pt.get("address", [])[:1]:
            P["region_province"] = ad.get("state") or P["region_province"]
            P["region_city"] = ad.get("city") or P["region_city"]
        P["phone"] = next((t.get("value") for t in pt.get("telecom", []) if t.get("system") == "phone"), None)

    for cov in by_type.get("Coverage", []):
        code = _ndb_code(cov.get("type", {}), "coverage-type")
        if code in ("nhi-employee", "nhi-regional"):
            P["insurance"] = code.replace("-", "_")
        elif code in ("medical-aid-1", "medical-aid-2"):
            P["insurance"] = "medical_aid"; P["beneficiary"] = code.replace("-", "_")
        elif code in ("near-poor", "single-parent"):
            P["beneficiary"] = code.replace("-", "_")
        elif code == "basic":
            P["beneficiary"] = "basic"
        else:
            un.append(f"Coverage.type unmapped: {_codes(cov.get('type', {}))}")

    for enc in by_type.get("Encounter", [])[:1]:
        cls = (enc.get("class") or {}).get("code", "")
        E["setting"] = "inpatient" if cls in ("IMP", "ACUTE", "NONAC") else "outpatient"
        per = enc.get("period", {})
        E["admission_date"] = (per.get("start") or "")[:10] or None
        E["discharge_date"] = (per.get("end") or "")[:10] or None
        if E["setting"] == "outpatient":
            E["last_visit_date"] = E["admission_date"]
        st = enc.get("serviceType", {})
        txt = (st.get("text") or "") + " ".join(d for _, _, d in _codes(st))
        E["department"] = next((v for k, v in DEPT_MAP.items() if k in txt.lower()), None)
        if not E["department"]:
            un.append(f"Encounter.serviceType unmapped: {txt!r}")

    for c in by_type.get("Condition", []):
        for sys_, code, disp in _codes(c.get("code", {})):
            if "icd" in sys_.lower() or code[:1].isalpha():
                E["diagnosis_codes"].append(code)
        E["diagnosis_text"] = ((E.get("diagnosis_text") or "") + " " + (c.get("code", {}).get("text") or "")).strip()

    for pr in by_type.get("Procedure", []):
        E["surgery"] = True
        if pr.get("status") == "completed":
            E["surgery_done"] = True
        elif pr.get("status") in ("preparation", "not-done", "in-progress") or pr.get("resourceType") == "ServiceRequest":
            E.setdefault("surgery_done", False)
        txt = ((pr.get("code", {}).get("text") or "") + " ".join(d for _, _, d in _codes(pr.get("code", {})))).lower()
        codes = {c for _, c, _ in _codes(pr.get("code", {}))}
        if any(h in txt for h in KNEE_HINTS) or codes & SNOMED_KNEE:
            E["procedure_knee_replacement"] = True
            sides = {(_codes(b) or [("", "", "")])[0][2].lower() for b in pr.get("bodySite", [])}
            if any("bilateral" in s or "양측" in s for s in sides) or len(pr.get("bodySite", [])) >= 2:
                E["knees"] = 2
        E["procedure_text"] = ((E.get("procedure_text") or "") + " " + txt).strip()
    for sr in by_type.get("ServiceRequest", []):   # planned surgery (pre-op)
        txt = (sr.get("code", {}).get("text") or "").lower()
        if any(h in txt for h in KNEE_HINTS):
            E.update(surgery=True, surgery_done=False, procedure_knee_replacement=True)
            if "양측" in txt or "bilateral" in txt:
                E["knees"] = 2

    cost_map = {"covered-copay": "covered_copay", "covered-copay-uncapped": "covered_copay_uncapped", "full-self-pay": "full_self_pay",
                "noncovered": "noncovered", "single-room": "single_room", "manual-therapy": "manual_therapy"}
    for cl in by_type.get("Claim", []) + by_type.get("ExplanationOfBenefit", []):
        for it in cl.get("item", []):
            code = _ndb_code(it.get("category", {}), "cost-category")
            amt = (it.get("net") or {}).get("value")
            if code in cost_map and amt is not None:
                E["costs"][cost_map[code]] = E["costs"].get(cost_map[code], 0) + int(amt)
            else:
                un.append(f"Claim.item unmapped: {_codes(it.get('category', {}))} net={amt}")
        tot = (cl.get("total") or {}).get("value") if cl.get("resourceType") == "Claim" else None
        if tot:
            E["costs"]["total_billed"] = int(tot)
    # noncovered must include single_room/manual_therapy per model semantics
    c = E["costs"]
    if c.get("noncovered") is not None:
        c["noncovered"] = c["noncovered"] + c.get("single_room", 0) + c.get("manual_therapy", 0) if not c.get("_inclusive") else c["noncovered"]

    for ob in by_type.get("Observation", []):
        code = _ndb_code(ob.get("code", {}), "sdoh")
        v = _num(ob); b = ob.get("valueBoolean"); s = ob.get("valueString") or _ndb_code(ob.get("valueCodeableConcept", {}), "crisis-event")
        if code == "monthly-income": P["monthly_income"] = int(v or 0)
        elif code == "assets": P["assets"] = int(v or 0)
        elif code == "financial-assets": P["financial_assets"] = int(v or 0)
        elif code == "private-insurance-paid": P["private_insurance_paid"] = int(v or 0)
        elif code == "covered-copay-ytd": P["covered_copay_ytd"] = int(v or 0)
        elif code == "main-earner": P["is_main_earner"] = bool(b)
        elif code == "caregiver-needed": P["caregiver_needed"] = bool(b)
        elif code == "cognitive-concern": P["cognitive_concern"] = bool(b)
        elif code == "crisis-event" and s: P["crisis_events"].append(s.replace("-", "_"))
        elif code == "special-disease-registered": E["special_disease_registered"] = bool(b)
        else:
            un.append(f"Observation unmapped: {_codes(ob.get('code', {}))}")

    for t in by_type:
        if t not in ("Patient", "Coverage", "Encounter", "Condition", "Procedure", "ServiceRequest", "Claim", "ExplanationOfBenefit", "Observation"):
            un.append(f"resourceType ignored: {t} ×{len(by_type[t])}")
    P.setdefault("household_size", 1)
    E.setdefault("surgery", False); E.setdefault("surgery_done", False); E.setdefault("setting", "outpatient")
    return P, E, un
