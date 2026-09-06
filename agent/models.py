"""Patient / Encounter schemas. All monetary values in KRW, ages in years."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import date

BENEFICIARY = {"none", "basic", "near_poor", "medical_aid_1", "medical_aid_2", "single_parent"}
INSURANCE = {"nhi_employee", "nhi_regional", "medical_aid", "none"}
SETTING = {"inpatient", "outpatient"}
DEPARTMENTS = {"spine", "joint", "internal", "neuro", "surgery"}


@dataclass
class Patient:
    name: str
    age: int
    household_size: int = 1
    sex: Optional[str] = None
    # income: give either monthly_income (KRW) or income_pct (기준중위소득 대비 %)
    monthly_income: Optional[int] = None
    income_pct: Optional[float] = None
    income_decile: Optional[int] = None  # 건강보험료 분위 1~10 (본인부담상한제)
    assets: Optional[int] = None
    financial_assets: Optional[int] = None
    beneficiary: str = "none"          # none|basic|near_poor|medical_aid_1|medical_aid_2|single_parent
    insurance: str = "nhi_employee"    # nhi_employee|nhi_regional|medical_aid|none
    region_province: str = "경기도"
    region_city: str = "남양주시"
    is_main_earner: bool = False
    crisis_events: List[str] = field(default_factory=list)
    caregiver_needed: bool = False
    cognitive_concern: bool = False
    private_insurance_paid: int = 0
    other_public_aid_received: int = 0
    covered_copay_ytd: int = 0   # 올해 다른 기관 급여 본인부담 누계 (상한제 합산용)
    confirmed_fields: List[str] = field(default_factory=list)  # 사람이 확인한 추출 필드
    phone: Optional[str] = None
    notes: str = ""

    def __post_init__(self):
        assert self.beneficiary in BENEFICIARY, f"beneficiary must be one of {BENEFICIARY}"
        assert self.insurance in INSURANCE, f"insurance must be one of {INSURANCE}"
        for k in ("private_insurance_paid", "other_public_aid_received", "covered_copay_ytd"):
            if getattr(self, k) is None: setattr(self, k, 0)
        if self.crisis_events is None: self.crisis_events = []
        assert 0 <= self.age <= 120, "age out of range"
        assert self.household_size >= 1, "household_size >= 1"
        for k in ("monthly_income", "assets", "financial_assets"):
            v = getattr(self, k)
            assert v is None or v >= 0, f"{k} must be >= 0"


@dataclass
class Costs:
    covered_copay: int = 0          # 급여 일부본인부담금 (상한제 대상)
    covered_copay_uncapped: int = 0  # 급여 일부본인부담 중 상한제 미적용분(선별급여 등)
    full_self_pay: int = 0          # 전액본인부담금
    noncovered: int = 0             # 비급여 총액 (아래 제외항목 포함)
    single_room: int = 0            # 1인실 (제외)
    manual_therapy: int = 0         # 도수치료 (제외)
    total_billed: Optional[int] = None

    @property
    def patient_burden(self) -> int:
        return self.covered_copay + self.covered_copay_uncapped + self.full_self_pay + self.noncovered


@dataclass
class Encounter:
    department: str                          # spine|joint|internal|neuro|surgery
    setting: str                             # inpatient|outpatient
    diagnosis_codes: List[str] = field(default_factory=list)
    diagnosis_text: str = ""
    procedure_text: str = ""
    surgery: bool = False
    surgery_done: bool = False
    procedure_knee_replacement: bool = False
    knees: int = 1
    admission_date: Optional[str] = None
    discharge_date: Optional[str] = None
    last_visit_date: Optional[str] = None
    special_disease_registered: bool = False
    special_category_override: Optional[str] = None   # LLM/staff가 확정한 질환군
    flags: Dict[str, Any] = field(default_factory=dict)  # severe_trauma, mild_disease_only ...
    costs: Costs = field(default_factory=Costs)

    def __post_init__(self):
        assert self.department in DEPARTMENTS, f"department must be one of {DEPARTMENTS}"
        assert self.setting in SETTING
        if isinstance(self.flags, list):
            self.flags = {k: True for k in self.flags}
        if isinstance(self.costs, dict):
            self.costs = Costs(**self.costs)

    @property
    def last_date(self) -> Optional[date]:
        d = self.discharge_date or self.last_visit_date or self.admission_date
        return date.fromisoformat(d) if d else None


def load_patient(d: Dict[str, Any]) -> Patient:
    return Patient(**d)


def load_encounter(d: Dict[str, Any]) -> Encounter:
    return Encounter(**d)


def to_dict(obj) -> Dict[str, Any]:
    return asdict(obj)
