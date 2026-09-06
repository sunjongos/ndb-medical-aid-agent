"""Neural layer of the neurosymbolic pipeline.

Three LLM jobs, each with a strict JSON contract so the symbolic engine can consume the output:
  1. extract   : free-text 진료내용/상담메모 → Patient/Encounter JSON (fills unknown facts)
  2. resolve   : for each `review` result, read the wiki page and decide eligible/likely/ineligible + rationale
  3. narrate   : produce patient-friendly Korean sentences for the PDF (no promises of amounts)

Inside Claude Code, Claude itself performs these steps by reading the prompt files this module writes
(`output/<case>/prompt_*.md`). Outside Claude Code, `call_llm()` uses the Anthropic API when ANTHROPIC_API_KEY is set.
"""
from __future__ import annotations
import json, os, pathlib
from typing import Dict, Any, List
from .kb import KB
from .rules import Result

EXTRACT_SCHEMA = {
    "patient": {"age": "int", "household_size": "int", "monthly_income": "int|null", "income_pct": "float|null",
                "assets": "int|null", "beneficiary": "none|basic|near_poor|medical_aid_1|medical_aid_2|single_parent",
                "insurance": "nhi_employee|nhi_regional|medical_aid", "is_main_earner": "bool",
                "crisis_events": ["main_earner_serious_illness|job_loss|business_closure|caregiving_income_loss|excessive_debt|..."],
                "caregiver_needed": "bool", "cognitive_concern": "bool", "private_insurance_paid": "int"},
    "encounter": {"department": "spine|joint|internal|neuro|surgery", "setting": "inpatient|outpatient",
                  "diagnosis_codes": ["ICD-10 codes if stated"], "diagnosis_text": "str", "surgery": "bool",
                  "surgery_done": "bool", "procedure_knee_replacement": "bool", "knees": "int",
                  "admission_date": "YYYY-MM-DD|null", "discharge_date": "YYYY-MM-DD|null",
                  "special_disease_registered": "bool", "special_category_override": "cancer|cerebrovascular|cardiac|rare|intractable|severe_burn|severe_trauma|tuberculosis|severe_dementia|null",
                  "flags": {"mild_disease_only": "bool", "severe_trauma": "bool"},
                  "costs": {"covered_copay": "int", "covered_copay_uncapped": "int", "full_self_pay": "int",
                            "noncovered": "int", "single_room": "int", "manual_therapy": "int"}},
    "evidence": {"<field>": "짧은 인용 근거"},
    "unknown_fields": ["fields you could not determine"]
}


def prompt_extract(free_text: str) -> str:
    return f"""당신은 남양주백병원 원무과 의료비 지원 상담 에이전트의 **추출 단계**입니다.
아래 진료내용·상담 메모에서 환자/진료 정보를 JSON으로만 추출하세요. 추측하지 말고 모르면 null과 unknown_fields에 남기세요.
금액은 원 단위 정수. 상병코드는 명시된 것만. 위기사유는 환자 발언에서 근거가 있을 때만.

스키마:
{json.dumps(EXTRACT_SCHEMA, ensure_ascii=False, indent=1)}

=== 진료내용 / 상담 메모 ===
{free_text}
=== 끝 ===
JSON만 출력:"""


def prompt_resolve(results: List[Result], facts: Dict[str, Any], kb: KB) -> str:
    items = [r for r in results if r.status == "review"]
    if not items:
        return ""
    blocks = []
    for r in items:
        blocks.append(f"## {r.name} ({r.program_id})\n미확정 사유: {r.unknowns}\n경고: {r.warnings}\n\n### 위키 본문\n{kb.bodies[r.program_id]}")
    safe_facts = {k: (v.isoformat() if hasattr(v, 'isoformat') else v) for k, v in facts.items()}
    return f"""당신은 **검토 단계**입니다. 기호 엔진이 `review`로 남긴 제도에 대해 위키 본문과 사실(facts)을 읽고 판단하세요.
규칙: 위키에 없는 기준을 만들지 말 것. 확정 불가하면 status="review" 유지하고 필요한 추가 질문(ask_staff)을 적을 것. 금액을 약속하지 말 것.

=== facts ===
{json.dumps(safe_facts, ensure_ascii=False, indent=1)}

{chr(10).join(blocks)}

출력(JSON 배열만): [{{"program_id": "...", "status": "eligible|likely|ineligible|review", "rationale": "위키 근거 인용", "ask_staff": ["추가 확인 질문"]}}]"""


def prompt_narrate(results: List[Result], patient_name: str) -> str:
    top = [r for r in results if r.status in ("eligible", "likely", "review")]
    lines = [f"- {r.name}: status={r.status}, band={r.band}, estimate={r.estimate}, deadline={r.deadline or r.deadline_note}, warnings={r.warnings}" for r in top]
    return f"""당신은 **환자 안내문 작성 단계**입니다. 아래 판정 결과를 {patient_name} 님이 읽을 쉬운 한국어로 바꾸세요.
원칙: (1) 금액은 '최대 ~원까지 가능할 수 있습니다'처럼 가능성으로만, (2) 기한은 날짜로 명시, (3) 제도별 3문장 이내, (4) 의료 용어는 괄호로 풀어쓰기, (5) 마지막에 '원무과에 문의' 한 줄.

{chr(10).join(lines)}

출력(JSON만): {{"intro": "1~2문장", "items": [{{"program_id": "...", "title": "...", "text": "..."}}], "closing": "1문장"}}"""


def call_llm(prompt: str, model: str = "claude-sonnet-4-6", max_tokens: int = 2000) -> str:
    """Optional: run a prompt through the Anthropic API. Returns raw text. Requires ANTHROPIC_API_KEY."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set — inside Claude Code, answer the prompt file yourself instead.")
    import urllib.request
    body = json.dumps({"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "Content-Type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return "".join(b.get("text", "") for b in data.get("content", []))


def parse_json(text: str) -> Any:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1]
        t = t[t.find("\n") + 1:] if t.startswith("json") else t
    return json.loads(t.strip().rstrip("`"))


def apply_resolution(results: List[Result], resolution: List[Dict[str, Any]]) -> List[Result]:
    by_id = {r.program_id: r for r in results}
    for item in resolution:
        r = by_id.get(item.get("program_id"))
        if not r:
            continue
        r.status = item.get("status", r.status)
        if item.get("rationale"):
            r.reasons.append("LLM 검토: " + item["rationale"])
        for q in item.get("ask_staff", []) or []:
            r.unknowns.append("확인 질문: " + q)
    order = {"eligible": 0, "likely": 1, "review": 2, "ineligible": 3}
    results.sort(key=lambda r: (order[r.status], r.priority))
    return results


def write_prompt(path: pathlib.Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf8")
