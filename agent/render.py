"""Render patient PDF (KakaoTalk phone size) and staff markdown."""
from __future__ import annotations
import pathlib, datetime
from typing import List, Dict, Any
from jinja2 import Environment, FileSystemLoader, select_autoescape
from .kb import KB
from .rules import Result
from .models import Patient, Encounter

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC_LABELS = {
    "receipt": "진료비 계산서·영수증", "noncovered_itemized": "비급여 세부내역서(급여/전액본인부담/비급여/1인실/도수 구분)",
    "diagnosis_certificate": "진단서(상병코드·수술명)", "admission_certificate": "입퇴원확인서",
    "special_disease_registration_form": "산정특례 등록신청서", "surgery_recommendation": "수술 필요 소견서",
    "id_card": "신분증", "bankbook": "통장사본", "private_insurance_statement": "실손보험 지급 내역",
}
HOSPITAL_DOCS = {"receipt", "noncovered_itemized", "diagnosis_certificate", "admission_certificate", "special_disease_registration_form", "surgery_recommendation"}
DEPT = {"spine": "척추센터", "joint": "관절센터", "internal": "내과", "neuro": "신경과", "surgery": "외과"}
SETTING = {"inpatient": "입원", "outpatient": "외래"}


def build_context(p: Patient, e: Encounter, results: List[Result], narrative: Dict[str, Any], kb: KB) -> Dict[str, Any]:
    active = [r for r in results if r.status in ("eligible", "likely", "review")]
    docs = set()
    for r in active:
        docs.update(r.documents)
    docs_h = [DOC_LABELS[d] for d in DOC_LABELS if d in docs and d in HOSPITAL_DOCS]
    docs_p = [DOC_LABELS[d] for d in DOC_LABELS if d in docs and d not in HOSPITAL_DOCS]
    deadlines = [f"{r.name}: {r.deadline}까지" if r.deadline else f"{r.name}: {r.deadline_note}" for r in active if r.deadline or r.deadline_note][:5]
    ckeys = []
    for r in active:
        for k, v in kb.thresholds["contacts"].items():
            if v["name"] == r.contact.get("name") and k not in ckeys:
                ckeys.append(k)
    contacts = [kb.thresholds["contacts"][k] for k in ckeys] + [kb.thresholds["contacts"]["ndb_admin"]]
    narrative = narrative or {"intro": "", "items": [], "closing": "궁금한 점은 원무과에 언제든 문의해 주세요."}
    return {
        "patient": p, "today": datetime.date.today().isoformat(),
        "dept_label": DEPT.get(e.department, e.department), "setting_label": SETTING.get(e.setting, e.setting),
        "results": results, "narrative": narrative,
        "narrative_map": {i["program_id"]: i["text"] for i in narrative.get("items", [])},
        "docs_hospital": docs_h, "docs_patient": docs_p, "deadlines": deadlines, "contacts": contacts,
    }


def render_html(ctx: Dict[str, Any]) -> str:
    env = Environment(loader=FileSystemLoader(str(ROOT / "templates")), autoescape=select_autoescape(["html"]))
    return env.get_template("patient_report.html").render(**ctx)


def html_to_pdf(html: str, out_pdf: pathlib.Path) -> pathlib.Path:
    from playwright.sync_api import sync_playwright
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_pdf.with_suffix(".html")
    tmp.write_text(html, encoding="utf8")
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page()
        pg.goto(tmp.resolve().as_uri())
        pg.wait_for_timeout(300)
        pg.pdf(path=str(out_pdf), print_background=True, prefer_css_page_size=True)
        b.close()
    return out_pdf


def staff_markdown(p: Patient, e: Encounter, facts: Dict[str, Any], results: List[Result]) -> str:
    L = [f"# 원무과 판정 시트 — {p.name} ({p.age}세, {DEPT.get(e.department)} {SETTING.get(e.setting)})", ""]
    L.append(f"- 소득: 중위 {facts.get('income_pct')}% · 수급자격: {p.beneficiary} · 재산: {p.assets} · 위기사유: {facts.get('crisis_events')}")
    L.append(f"- 산정특례 질환군: {facts.get('special_category')} (등록: {facts.get('special_registered')}) · 본인부담 합계 {facts.get('patient_burden'):,}원 (제외항목 {facts.get('excluded_costs'):,}원, 실손 {facts.get('private_insurance_paid'):,}원)")
    L.append("")
    L.append("| 제도 | 판정 | 구간 | 추정 | 기한 | 사유/미확인 |")
    L.append("|---|---|---|---|---|---|")
    for r in results:
        est = f"{r.estimate:,}원" if r.estimate else "-"
        why = "; ".join(r.reasons + r.unknowns + r.warnings)[:160]
        L.append(f"| {r.name} | **{r.status}** | {r.band or ''} | {est} | {r.deadline or r.deadline_note} | {why} |")
    L.append("")
    L.append("## 원무과 액션")
    for r in results:
        if r.status in ("eligible", "likely"):
            L.append(f"- [ ] {r.name}: 서류 {', '.join(DOC_LABELS.get(d, d) for d in r.documents if d in HOSPITAL_DOCS) or '없음'} 발급 → {r.contact.get('name')} 안내 ({r.deadline or r.deadline_note})")
        elif r.status == "review":
            L.append(f"- [ ] {r.name}: 확인 필요 — {'; '.join(r.unknowns)}")
    return "\n".join(L)
