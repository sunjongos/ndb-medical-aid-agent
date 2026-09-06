"""Intake layer: EMR screen capture (image) + typed clinical note → patient.json / encounter.json.

Design (pre-EMR-integration best practice)
  * The EMR screenshot is treated as a *transient PHI artifact*: it is hashed for the audit trail, never copied into
    git, and deleted by `python -m agent purge` after the case closes (retention policy in db/policy.json).
  * Claude (vision) reads the screenshot and fills ONLY the fields listed in PATIENT_FIELDS_FROM_SCREEN. Everything
    else must come from the typed note or staff confirmation — no guessing from UI clutter.
  * Every extracted field must carry evidence (the on-screen label/value it came from) so `confirm` can show it.
"""
from __future__ import annotations
import hashlib, json, pathlib, shutil
from typing import Dict, Any

PATIENT_FIELDS_FROM_SCREEN = ["name", "age", "sex", "insurance", "beneficiary", "region_province", "region_city", "phone",
                              "household_size", "special_disease_registered", "covered_copay_ytd"]
ENCOUNTER_FIELDS_FROM_TEXT = ["department", "setting", "diagnosis_codes", "diagnosis_text", "procedure_text", "surgery", "surgery_done",
                              "procedure_knee_replacement", "knees", "admission_date", "discharge_date", "last_visit_date",
                              "special_category_override", "flags", "costs"]
SOCIAL_FIELDS_FROM_TEXT = ["monthly_income", "income_pct", "assets", "financial_assets", "is_main_earner", "crisis_events",
                           "caregiver_needed", "cognitive_concern", "private_insurance_paid"]


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stage_screenshot(src: pathlib.Path, out: pathlib.Path) -> Dict[str, Any]:
    """Copy screenshot into the case folder (git-ignored) and record its hash. Returns manifest entry."""
    out.mkdir(parents=True, exist_ok=True)
    dst = out / f"emr_capture{src.suffix.lower()}"
    shutil.copy2(src, dst)
    return {"file": dst.name, "sha256": sha256_file(dst), "bytes": dst.stat().st_size, "phi": True}


def prompt_extract_screen(image_name: str) -> str:
    return f"""당신은 **EMR 화면 캡처 판독 단계**입니다. 첨부 이미지 `{image_name}`는 병원 EMR의 환자 기본정보 화면입니다.
아래 필드만 읽어서 JSON으로 출력하세요. 화면에 없는 값은 null. 절대 추정하지 마세요. 각 값마다 화면의 어떤 라벨/텍스트에서 읽었는지 evidence에 적으세요.

허용 필드: {PATIENT_FIELDS_FROM_SCREEN}
- insurance: 건강보험 직장→"nhi_employee", 지역→"nhi_regional", 의료급여→"medical_aid"
- beneficiary: 의료급여 1종→"medical_aid_1", 2종→"medical_aid_2", 차상위(C/E/F 코드)→"near_poor", 기초수급(건보)→"basic", 한부모→"single_parent", 해당 없음→"none"
- age: 생년월일만 있으면 오늘 기준으로 계산하고 evidence에 생년월일을 남길 것
- special_disease_registered: 산정특례 등록 표시(V코드 등)가 보이면 true
- covered_copay_ytd: 화면에 '올해 본인부담 누계' 류가 있으면 정수(원), 없으면 null

출력(JSON만): {{"patient": {{...}}, "evidence": {{"<field>": "화면 문구"}}, "unreadable": ["읽을 수 없었던 필드"]}}"""


def prompt_extract_text(note: str) -> str:
    return f"""당신은 **진료내용 추출 단계**입니다. 아래 텍스트(진료내용·상담메모)에서 진료 정보와 사회·경제 정보를 JSON으로 추출하세요.
모르면 null. 위기사유·주소득자·간병 필요는 환자/보호자 발언 근거가 있을 때만. 금액은 원 단위 정수. 비급여 총액(noncovered)에는 1인실·도수치료가 포함되고, 그 둘은 별도로도 적으세요.

encounter 필드: {ENCOUNTER_FIELDS_FROM_TEXT}
  department: spine|joint|internal|neuro|surgery · setting: inpatient|outpatient
  costs: {{covered_copay, covered_copay_uncapped, full_self_pay, noncovered, single_room, manual_therapy}}
  special_category_override: cancer|cerebrovascular|cardiac|rare|intractable|severe_burn|severe_trauma|tuberculosis|severe_dementia|null (상병코드 없이 서술만 있을 때 후보)
patient(social) 필드: {SOCIAL_FIELDS_FROM_TEXT}
  crisis_events: main_earner_serious_illness|main_earner_death_or_missing|job_loss|business_closure|caregiving_income_loss|excessive_debt|divorce_income_drop|...

=== 진료내용 ===
{note}
=== 끝 ===
출력(JSON만): {{"encounter": {{...}}, "patient_social": {{...}}, "evidence": {{"<field>": "원문 인용"}}, "unknown_fields": [...]}}"""


def merge(screen: Dict[str, Any] | None, text: Dict[str, Any] | None) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Merge the two LLM outputs into patient/encounter dicts + combined evidence."""
    P: Dict[str, Any] = {"beneficiary": "none", "insurance": "nhi_employee", "crisis_events": [], "household_size": 1,
                         "region_province": "경기도", "region_city": "남양주시"}
    E: Dict[str, Any] = {"diagnosis_codes": [], "flags": {}, "costs": {}}
    ev: Dict[str, Any] = {}
    if screen:
        for k, v in (screen.get("patient") or {}).items():
            if k in PATIENT_FIELDS_FROM_SCREEN and v is not None:
                if k == "special_disease_registered":
                    E[k] = v
                else:
                    P[k] = v
        ev.update(screen.get("evidence") or {})
    if text:
        for k, v in (text.get("encounter") or {}).items():
            if k in ENCOUNTER_FIELDS_FROM_TEXT and v is not None:
                E[k] = v
        for k, v in (text.get("patient_social") or {}).items():
            if k in SOCIAL_FIELDS_FROM_TEXT and v is not None:
                P[k] = v
        ev.update(text.get("evidence") or {})
    P.setdefault("name", "환자"); P.setdefault("age", 0)
    E.setdefault("department", "spine"); E.setdefault("setting", "outpatient")
    E.setdefault("surgery", False); E.setdefault("surgery_done", False)
    return P, E, {"evidence": ev, "unknown_fields": (text or {}).get("unknown_fields", []) + (screen or {}).get("unreadable", [])}
