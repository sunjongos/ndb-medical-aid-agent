"""Human-in-the-loop confirmation sheet for LLM-extracted fields.

Fields that flip a decision (surgery_done, is_main_earner, beneficiary, income, costs) must be ticked by staff
before `match` treats them as known. Unticked critical fields are blanked to null → engine yields `review`.
"""
from __future__ import annotations
import json, pathlib, re
from typing import Dict, Any, List

CRITICAL_PATIENT = ["age", "household_size", "monthly_income", "income_pct", "assets", "beneficiary", "insurance",
                    "is_main_earner", "crisis_events", "caregiver_needed", "cognitive_concern", "private_insurance_paid"]
CRITICAL_ENCOUNTER = ["department", "setting", "diagnosis_codes", "surgery", "surgery_done", "procedure_knee_replacement",
                      "knees", "discharge_date", "special_disease_registered", "special_category_override",
                      "costs.covered_copay", "costs.full_self_pay", "costs.noncovered", "costs.single_room", "costs.manual_therapy"]
LABEL = {"age": "나이", "household_size": "가구원 수", "monthly_income": "월소득", "income_pct": "중위소득 %", "assets": "재산",
         "beneficiary": "수급자격", "insurance": "보험 구분", "is_main_earner": "주소득자 여부", "crisis_events": "위기사유",
         "caregiver_needed": "간병 필요", "cognitive_concern": "인지저하 호소", "private_insurance_paid": "실손 수령액",
         "department": "진료과", "setting": "입원/외래", "diagnosis_codes": "상병코드", "surgery": "수술 여부",
         "surgery_done": "수술 완료 여부", "procedure_knee_replacement": "무릎 인공관절", "knees": "무릎 수",
         "discharge_date": "퇴원일", "special_disease_registered": "산정특례 등록", "special_category_override": "산정특례 질환군",
         "costs.covered_copay": "급여 본인부담", "costs.full_self_pay": "전액본인부담", "costs.noncovered": "비급여",
         "costs.single_room": "1인실", "costs.manual_therapy": "도수치료"}


def _get(d: Dict[str, Any], dotted: str):
    cur = d
    for k in dotted.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _set(d: Dict[str, Any], dotted: str, v):
    parts = dotted.split("."); cur = d
    for k in parts[:-1]:
        cur = cur.setdefault(k, {})
    cur[parts[-1]] = v


def make_sheet(patient: Dict[str, Any], encounter: Dict[str, Any], evidence: Dict[str, Any] | None = None) -> str:
    ev = (evidence or {}).get("evidence", {}) if evidence else {}
    L = ["# 추출 확인 시트 (원무과 체크 후 저장)", "",
         "각 줄의 `[ ]`를 `[x]`로 바꾸면 확인된 값으로 처리됩니다. 값이 틀리면 뒤의 `값:` 부분을 고치세요. 확인하지 않은 항목은 null로 취급되어 `review`가 됩니다.", "",
         "## 환자"]
    for k in CRITICAL_PATIENT:
        L.append(f"- [ ] {LABEL.get(k,k)} (`patient.{k}`) 값: `{json.dumps(_get(patient,k), ensure_ascii=False)}`" + (f" ← 근거: {ev.get(k)}" if ev.get(k) else ""))
    L += ["", "## 진료"]
    for k in CRITICAL_ENCOUNTER:
        L.append(f"- [ ] {LABEL.get(k,k)} (`encounter.{k}`) 값: `{json.dumps(_get(encounter,k), ensure_ascii=False)}`" + (f" ← 근거: {ev.get(k)}" if ev.get(k) else ""))
    return "\n".join(L) + "\n"


LINE = re.compile(r"^- \[(x|X| )\] .*?\(`(patient|encounter)\.([\w.]+)`\) 값: `(.*?)`", re.M)


def apply_sheet(sheet_text: str, patient: Dict[str, Any], encounter: Dict[str, Any]):
    """Return (patient, encounter, confirmed, unconfirmed). Unticked critical fields are nulled."""
    confirmed, unconfirmed = [], []
    for m in LINE.finditer(sheet_text):
        ticked, who, key, raw = m.group(1).lower() == "x", m.group(2), m.group(3), m.group(4)
        target = patient if who == "patient" else encounter
        try:
            val = json.loads(raw)
        except Exception:
            val = raw
        if ticked:
            _set(target, key, val); confirmed.append(f"{who}.{key}")
        else:
            unconfirmed.append(f"{who}.{key}")
            if key not in ("department", "setting", "age", "household_size"):   # required fields keep extracted value
                _set(target, key, None if not isinstance(val, (list, dict)) else val)
    # None costs → 0 so dataclass works; None booleans → keep None semantics via flags
    c = encounter.get("costs") or {}
    for k in list(c):
        if c[k] is None: c[k] = 0
    for k in ("surgery", "surgery_done", "procedure_knee_replacement", "special_disease_registered", "is_main_earner", "caregiver_needed", "cognitive_concern"):
        d = encounter if k in encounter else patient
        if d.get(k) is None: d[k] = False if k != "surgery_done" else False
    if patient.get("beneficiary") is None: patient["beneficiary"] = "none"
    if patient.get("insurance") is None: patient["insurance"] = "nhi_employee"
    if patient.get("crisis_events") is None: patient["crisis_events"] = []
    if encounter.get("diagnosis_codes") is None: encounter["diagnosis_codes"] = []
    if encounter.get("knees") is None: encounter["knees"] = 1
    patient["confirmed_fields"] = confirmed
    return patient, encounter, confirmed, unconfirmed
