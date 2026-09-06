"""Symbolic layer: evaluate wiki frontmatter rules against derived facts.

Status semantics
  eligible  : all hard rules pass with known facts
  likely    : hard rules pass but at least one soft warning
  review    : a hard rule depends on an UNKNOWN fact (needs staff/LLM input)
  ineligible: a hard rule failed on a known fact
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import timedelta, date
from typing import Any, Dict, List, Optional
from .kb import KB

OPS = {
    "lte": lambda a, b: a <= b,
    "gte": lambda a, b: a >= b,
    "eq": lambda a, b: a == b,
    "in": lambda a, b: a in b,
    "not_null": lambda a, b: a is not None,
    "neq": lambda a, b: a != b,
}


@dataclass
class Result:
    program_id: str
    name: str
    status: str
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)
    estimate: Optional[int] = None
    estimate_note: str = ""
    band: Optional[str] = None
    deadline: Optional[str] = None
    deadline_note: str = ""
    documents: List[str] = field(default_factory=list)
    contact: Dict[str, str] = field(default_factory=dict)
    priority: int = 9
    covers_noncovered: Any = False
    trace: List[Dict[str, Any]] = field(default_factory=list)   # explainability: every rule evaluated

    def to_dict(self):
        return asdict(self)


def _resolve(rule: Dict[str, Any], kb: KB):
    if "ref" in rule:
        return kb.ref(rule["ref"])
    return rule.get("value")


def _eval_rule(rule: Dict[str, Any], facts: Dict[str, Any], kb: KB):
    fact = facts.get(rule["fact"])
    op = rule["op"]
    if op == "not_null":
        return (fact is not None), fact
    if fact is None:
        return None, fact
    target = _resolve(rule, kb)
    return OPS[op](fact, target), fact


def evaluate(program: Dict[str, Any], facts: Dict[str, Any], kb: KB) -> Result:
    sym = program.get("symbolic", {})
    r = Result(program_id=program["id"], name=program["name"], status="eligible",
               documents=program.get("documents", []), contact=kb.contact(program.get("contact", "")),
               priority=program.get("priority", 9), covers_noncovered=program.get("covers_noncovered", False))
    failed = False
    for rule in sym.get("hard", []):
        ok, val = _eval_rule(rule, facts, kb)
        r.trace.append({"kind": "hard", "fact": rule["fact"], "op": rule["op"], "target": _resolve(rule, kb) if rule["op"] != "not_null" else None,
                        "ref": rule.get("ref"), "value": val, "result": "unknown" if ok is None else ("pass" if ok else "fail")})
        if ok is None:
            r.unknowns.append(f"{rule['fact']} 값 없음 → {rule.get('fail','')}")
        elif not ok:
            failed = True
            r.reasons.append(rule.get("fail", f"{rule['fact']} 조건 불충족"))
    for rule in sym.get("soft", []):
        ok, val = _eval_rule(rule, facts, kb)
        r.trace.append({"kind": "soft", "fact": rule["fact"], "op": rule["op"], "target": _resolve(rule, kb),
                        "ref": rule.get("ref"), "value": val, "result": "unknown" if ok is None else ("pass" if ok else "warn")})
        if ok is None:
            r.warnings.append(f"{rule['fact']} 미확인: {rule.get('warn','')}")
        elif not ok:
            r.warnings.append(rule.get("warn", f"{rule['fact']} 주의"))
    if failed:
        r.status = "ineligible"
    elif r.unknowns:
        r.status = "review"
    elif r.warnings:
        r.status = "likely"
    if r.status != "ineligible":
        fn = AMOUNTS.get(sym.get("amount", "none"), amount_none)
        fn(r, facts, kb)
        _deadline(r, program.get("deadline", {}), facts)
        _verification_flag(r, program, kb)
    return r


def _verification_flag(r: Result, program: Dict[str, Any], kb: KB):
    """Downgrade eligible→likely when the threshold section this program depends on is not yet verified."""
    ver = kb.thresholds.get("verification", {})
    refs = set()
    for rule in program.get("symbolic", {}).get("hard", []) + program.get("symbolic", {}).get("soft", []):
        if "ref" in rule:
            refs.add(rule["ref"].split(".")[0])
    refs.add(_AMOUNT_SECTION.get(program.get("symbolic", {}).get("amount", ""), ""))
    for sec in refs:
        v = ver.get(sec)
        if v and not v.get("verified", True):
            r.warnings.append(f"수치 미검증 섹션({sec}): {v.get('source','')} — 원문 대조 후 확정")
            if r.status == "eligible":
                r.status = "likely"
            break


_AMOUNT_SECTION = {"catastrophic_amount": "catastrophic", "copay_ceiling_amount": "copay_ceiling",
                   "emergency_national_amount": "emergency_welfare_national", "emergency_gyeonggi_amount": "emergency_welfare_gyeonggi",
                   "special_disease_amount": "special_disease", "cancer_aid_amount": "cancer_aid", "rare_disease_amount": "rare_disease_aid",
                   "knee_amount": "knee_replacement", "dementia_amount": "dementia", "medical_aid_refund_amount": "medical_aid_copay",
                   "living_amount": "emergency_welfare_national"}


def _deadline(r: Result, d: Dict[str, Any], facts: Dict[str, Any]):
    t = d.get("type")
    last: Optional[date] = facts.get("last_date")
    if t == "after_last_visit" and last:
        r.deadline = (last + timedelta(days=d["days"])).isoformat()
        r.deadline_note = f"최종 진료·퇴원 다음 날부터 {d['days']}일 이내"
    elif t == "around_discharge" and last:
        r.deadline = (last + timedelta(days=d["days"])).isoformat()
        r.deadline_note = f"퇴원 전 또는 퇴원 후 {d['days']}일 이내"
    elif t == "after_year_end" and last:
        r.deadline = date(last.year + d["years"], 12, 31).isoformat()
        r.deadline_note = f"진료연도 종료 후 {d['years']}년 이내 (미신청 시 소멸)"
    elif t == "before_discharge":
        r.deadline_note = "퇴원 전 신청 원칙 (입원 중 129 신고 가능)"
    elif t == "before_surgery":
        r.deadline_note = "수술 전 보건소 사전 신청 필수"
    elif t == "at_diagnosis":
        r.deadline_note = "진단 즉시 등록 (등록일부터 적용, 소급 불가)"
    elif t == "annual":
        r.deadline_note = "연중 접수 (예산 소진 시 조기 마감 가능)"
    elif t == "asap":
        r.deadline_note = "즉시 신청"


# ---------------- amount estimators ----------------

def amount_none(r: Result, f, kb):
    r.estimate = None


def catastrophic_amount(r: Result, f: Dict[str, Any], kb: KB):
    T = kb.thresholds["catastrophic"]
    ip = f.get("income_pct")
    benef = f["beneficiary"]
    band = None
    for b in T["bands"]:
        if b.get("requires_beneficiary"):
            if benef in ("basic", "near_poor", "medical_aid_1", "medical_aid_2"):
                band = b; break
        elif ip is not None and ip <= b["income_pct_max"]:
            band = b; break
    if band is None:
        if ip is None:
            r.status = "review"; r.unknowns.append("소득 정보 없음 → 소득구간 미확정")
            return
        r.status = "ineligible"; r.reasons.append("기준중위소득 200% 초과")
        return
    r.band = band["label"]
    if band.get("individual_review"):
        r.warnings.append("개별심사 구간 — 공단 심사로 결정")
        if r.status == "eligible": r.status = "likely"
    # burden threshold check
    burden = f["patient_burden"] - f["excluded_costs"] - f["private_insurance_paid"] - f["other_public_aid_received"]
    base = f["covered_copay_uncapped"] + f["full_self_pay"] + f["noncovered"] - f["excluded_costs"]
    base = max(base, 0)
    thr_ok = None
    if "burden_min" in band:
        thr = band.get("burden_min_single", band["burden_min"]) if f["household_size"] == 1 and "burden_min_single" in band else band["burden_min"]
        thr_ok = f["patient_burden"] > thr
        thr_txt = f"본인부담 {thr:,}원 초과 필요"
    else:
        # need annual income
        if f.get("income_pct") is not None:
            annual = kb.median_income(f["household_size"]) * f["income_pct"] / 100 * 12
            thr = annual * band["burden_income_ratio"]
            thr_ok = f["patient_burden"] > thr
            thr_txt = f"연소득의 {int(band['burden_income_ratio']*100)}%({thr:,.0f}원) 초과 필요"
        else:
            thr_txt = "연소득 대비 기준 확인 필요"
    if thr_ok is False:
        r.status = "ineligible"; r.reasons.append(f"의료비 부담 기준 미달 ({thr_txt})"); return
    if thr_ok is None:
        r.unknowns.append(thr_txt); r.status = "review"
    deductible = f["private_insurance_paid"] + f["other_public_aid_received"]
    est = max(base - deductible, 0) * band["rate"]
    r.estimate = int(min(est, T["annual_cap"]))
    r.estimate_note = (f"[{base:,}원(상한제 미지원 급여+전액본인부담+비급여−제외항목) − {deductible:,}원(실손·타지원)] × {int(band['rate']*100)}% "
                       f"≈ {r.estimate:,}원 (공단 심사액과 다를 수 있음)")
    if f["covered_copay"]:
        r.warnings.append("급여 일부본인부담금은 본인부담상한제로 별도 환급 — 재난적 의료비 계산에서 제외됨(두 제도 병행)")


def copay_ceiling_amount(r: Result, f, kb: KB):
    caps = kb.thresholds["copay_ceiling"]["decile_caps"]
    dec = f.get("income_decile")
    if dec is None:
        # approximate decile from income_pct
        ip = f.get("income_pct")
        if ip is None:
            r.status = "review"; r.unknowns.append("소득분위(건강보험료) 미확인"); return
        dec = 1 if ip <= 30 else 3 if ip <= 50 else 5 if ip <= 70 else 7 if ip <= 100 else 8 if ip <= 130 else 9 if ip <= 170 else 10
        r.warnings.append("소득분위를 중위소득 %로 근사 — 공단 조회로 확정 필요")
        if r.status == "eligible": r.status = "likely"
    key = next(k for k in caps if str(dec) == k or (("-" in k) and int(k.split("-")[0]) <= dec <= int(k.split("-")[1])))
    cap = caps[key]
    ytd = f.get("covered_copay_ytd") or f["covered_copay"]
    over = ytd - cap
    r.band = f"{key}분위 상한 {cap:,}원"
    r.estimate = int(max(over, 0))
    r.estimate_note = (f"올해 급여 본인부담 누계 {ytd:,}원(이번 진료 {f['covered_copay']:,}원 포함) − 상한 {cap:,}원. 다른 기관 지출 추가 시 증가"
                       if over > 0 else f"올해 누계 {ytd:,}원으로는 상한({cap:,}원) 미달 — 연말 합산으로 재확인")


def emergency_national_amount(r: Result, f, kb: KB):
    T = kb.thresholds["emergency_welfare_national"]
    r.estimate = min(f["patient_burden"], T["medical_cap"])
    hs = str(min(f["household_size"], 4))
    r.estimate_note = f"의료지원 최대 {T['medical_cap']:,}원(1회, 추가 1회 가능) + 생계지원 월 {T['living_monthly'][hs]:,}원(최대 {T['living_months_max']}개월)"


def emergency_gyeonggi_amount(r: Result, f, kb: KB):
    T = kb.thresholds["emergency_welfare_gyeonggi"]
    med = min(max(f["noncovered"], 0), T["medical_noncovered_cap"])
    care = T["caregiver_cap"] if f.get("caregiver_needed") else 0
    r.estimate = med + care
    r.estimate_note = f"비급여 의료비 최대 {T['medical_noncovered_cap']:,}원(2회)" + (f" + 간병비 최대 {T['caregiver_cap']:,}원(1회)" if care else "")


def special_disease_amount(r: Result, f, kb: KB):
    cat = f["special_category"]
    S = kb.thresholds["special_disease"][cat]
    saving = int(f["covered_copay"] * (1 - S["rate"] / 0.20)) if f["covered_copay"] else None
    r.band = f"{cat} 본인부담 {int(S['rate']*100)}%"
    if f.get("special_registered"):
        r.warnings.append("이미 등록됨 — 적용 여부만 확인")
    elif S.get("self_register") is False:
        r.warnings.append("별도 등록 불필요 — 청구 시 적용 확인")
    else:
        r.reasons.append("미등록 — 즉시 등록 필요 (소급 불가)")
    r.estimate = max(saving, 0) if saving else None
    r.estimate_note = (f"급여 본인부담률 20%→{int(S['rate']*100)}% 가정 시 절감 추정" if saving else "급여 본인부담 금액 입력 시 절감액 추정")
    if S.get("planned_rate"):
        r.warnings.append(f"{S['planned_from']}부터 {int(S['planned_rate']*100)}%로 인하 예정 — 고시 확인")


def cancer_aid_amount(r: Result, f, kb: KB):
    T = kb.thresholds["cancer_aid"]
    r.estimate = min(f["patient_burden"], T["annual_cap"])
    r.estimate_note = f"급여·비급여 구분 없이 연 최대 {T['annual_cap']:,}원, 연속 {T['years']}년"


def rare_disease_amount(r: Result, f, kb: KB):
    r.estimate = f["covered_copay"]
    r.estimate_note = "급여 본인부담금 지원(보건소 소득·재산 조사 후 공단 지급)"


def knee_amount(r: Result, f, kb: KB):
    T = kb.thresholds["knee_replacement"]
    r.estimate = T["cap_both"] if f.get("knees", 1) >= 2 else T["cap_per_knee"]
    r.estimate_note = f"한쪽 {T['cap_per_knee']:,}원 한도 실비, 양쪽 {T['cap_both']:,}원"


def dementia_amount(r: Result, f, kb: KB):
    T = kb.thresholds["dementia"]
    r.estimate = T["differential_test_aid"][1]
    r.estimate_note = f"선별검사 무료 + 감별검사비 {T['differential_test_aid'][0]:,}~{T['differential_test_aid'][1]:,}원; 치료관리비(월 {T['management_monthly']:,}원)는 남양주시 시행 여부 {T['namyangju_status']}"
    if T["namyangju_status"] == "UNCONFIRMED":
        r.warnings.append("치료관리비 남양주시 시행 여부 미확인")
        if r.status == "eligible": r.status = "likely"


def medical_aid_refund_amount(r: Result, f, kb: KB):
    T = kb.thresholds["medical_aid_copay"]
    thr = T["refund_threshold_30d"].get(f["beneficiary"], 200000)
    over = f["covered_copay"] - thr
    r.estimate = int(max(over, 0) * T["refund_rate"])
    r.estimate_note = f"30일간 본인부담 {thr:,}원 초과분의 50% 보상 (외래 1회 {T['outpatient_visit_cap']:,}원·월 {T['monthly_cap']:,}원 상한 적용 여부 확인)"


def living_amount(r: Result, f, kb: KB):
    T = kb.thresholds["emergency_welfare_national"]
    hs = str(min(f["household_size"], 4))
    r.estimate = T["living_monthly"][hs] * 3
    r.estimate_note = f"월 {T['living_monthly'][hs]:,}원 × 기본 3개월 (최대 {T['living_months_max']}개월)"


AMOUNTS = {
    "none": amount_none,
    "catastrophic_amount": catastrophic_amount,
    "copay_ceiling_amount": copay_ceiling_amount,
    "emergency_national_amount": emergency_national_amount,
    "emergency_gyeonggi_amount": emergency_gyeonggi_amount,
    "special_disease_amount": special_disease_amount,
    "cancer_aid_amount": cancer_aid_amount,
    "rare_disease_amount": rare_disease_amount,
    "knee_amount": knee_amount,
    "dementia_amount": dementia_amount,
    "medical_aid_refund_amount": medical_aid_refund_amount,
    "living_amount": living_amount,
}


def run_all(facts: Dict[str, Any], kb: KB) -> List[Result]:
    out = []
    for prog in kb.ordered_programs():
        out.append(evaluate(prog, facts, kb))
    order = {"eligible": 0, "likely": 1, "review": 2, "ineligible": 3}
    out.sort(key=lambda r: (order[r.status], r.priority))
    return out
