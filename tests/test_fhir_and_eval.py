import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from agent import fhir, evaluate, intake, audit
ROOT = pathlib.Path(__file__).resolve().parent.parent

def test_fhir_bundle_maps_core_fields():
    P, E, un = fhir.fhir_to_case(json.loads((ROOT/"examples/fhir_bundle_spine.json").read_text(encoding="utf-8")))
    assert P["insurance"] == "nhi_regional" and P["household_size"] == 2 and P["monthly_income"] == 2900000 and P["caregiver_needed"]
    assert E["setting"] == "inpatient" and E["department"] == "spine" and "M48.06" in E["diagnosis_codes"] and E["surgery_done"]
    assert E["costs"]["covered_copay"] == 2500000 and E["costs"]["single_room"] == 600000 and E["costs"]["noncovered"] == 6000000
    assert any("AllergyIntolerance" in u for u in un)   # nothing silently dropped

def test_fhir_planned_knee_via_servicerequest():
    b = {"resourceType":"Bundle","entry":[{"resource":{"resourceType":"Patient","birthDate":"1960-01-01"}},
         {"resource":{"resourceType":"ServiceRequest","code":{"text":"양측 슬관절 인공관절 치환술"}}}]}
    P, E, _ = fhir.fhir_to_case(b)
    assert E["procedure_knee_replacement"] and E["surgery_done"] is False and E["knees"] == 2

def test_intake_merge_precedence_and_evidence():
    scr = {"patient": {"name": "X", "age": 70, "beneficiary": "medical_aid_1", "special_disease_registered": True}, "evidence": {"age": "생년월일"}, "unreadable": ["phone"]}
    txt = {"encounter": {"department": "internal", "setting": "inpatient", "costs": {"noncovered": 100}}, "patient_social": {"is_main_earner": True}, "evidence": {"is_main_earner": "가장"}, "unknown_fields": ["assets"]}
    P, E, ev = intake.merge(scr, txt)
    assert P["beneficiary"] == "medical_aid_1" and P["is_main_earner"] and E["special_disease_registered"] is True
    assert set(ev["unknown_fields"]) == {"assets", "phone"} and "age" in ev["evidence"]

def test_eval_harness_all_gold_pass():
    s, _ = evaluate.run()
    assert s["hard_miss"] == 0, [r for r in s["rows"] if not r["ok"]]

def test_audit_key_has_no_phi():
    k = audit.patient_key("홍길동", 70, "010-1234-5678")
    assert "홍" not in k and "1234" not in k and len(k) == 16
