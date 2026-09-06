import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from agent import confirm

def test_unticked_critical_nulled_and_ticked_kept():
    p = {"name": "x", "age": 66, "household_size": 1, "beneficiary": "basic", "insurance": "medical_aid", "is_main_earner": True}
    e = {"department": "joint", "setting": "outpatient", "surgery_done": False, "procedure_knee_replacement": True, "costs": {"noncovered": 100}}
    sheet = confirm.make_sheet(p, e)
    sheet = sheet.replace("- [ ] 수술 완료 여부", "- [x] 수술 완료 여부").replace("- [ ] 수급자격", "- [x] 수급자격")
    p2, e2, ok, no = confirm.apply_sheet(sheet, dict(p), dict(e))
    assert "encounter.surgery_done" in ok and e2["surgery_done"] is False
    assert p2["beneficiary"] == "basic"
    assert p2["is_main_earner"] is False          # unticked bool → False (conservative)
    assert e2["costs"]["noncovered"] == 0          # unticked cost → 0
    assert "patient.is_main_earner" in no

def test_edited_value_in_sheet_wins():
    p = {"name": "x", "age": 66, "household_size": 1}
    e = {"department": "spine", "setting": "inpatient"}
    sheet = confirm.make_sheet(p, e).replace("- [ ] 나이 (`patient.age`) 값: `66`", "- [x] 나이 (`patient.age`) 값: `71`")
    p2, *_ = confirm.apply_sheet(sheet, p, e)
    assert p2["age"] == 71
