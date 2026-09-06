"""CLI for the NDB medical-aid agent.

  python -m agent extract  --text notes.txt --out output/case1            # writes prompt_extract.md (LLM step 1)
  python -m agent match    --patient p.json --encounter e.json --out output/case1
  python -m agent resolve  --out output/case1 --resolution resolution.json   # apply LLM step 2 answers
  python -m agent render   --out output/case1 [--narrative narrative.json]   # PDF for KakaoTalk
  python -m agent run      --patient p.json --encounter e.json --out output/case1 [--llm]   # whole pipeline
"""
from __future__ import annotations
import argparse, json, pathlib, sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
from typing import Any, Dict, List
from .kb import KB
from .models import load_patient, load_encounter, to_dict
from .facts import derive
from .rules import run_all, Result
from . import reason, render, confirm, intake, audit, fhir, evaluate


def _load(p: str) -> Dict[str, Any]:
    return json.loads(pathlib.Path(p).read_text(encoding="utf8"))


def _save(path: pathlib.Path, obj: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf8")


def _results_from(out: pathlib.Path) -> List[Result]:
    data = _load(str(out / "results.json"))
    return [Result(**d) for d in data["results"]]


def cmd_extract(a):
    """Intake: --image (EMR 화면 캡처) and/or --text (진료내용). Writes prompts for Claude; --llm answers text prompt via API."""
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    manifest = {}
    if a.image:
        manifest["capture"] = intake.stage_screenshot(pathlib.Path(a.image), out)
        reason.write_prompt(out / "prompt_extract_screen.md", intake.prompt_extract_screen(manifest["capture"]["file"]))
    if a.text:
        note = pathlib.Path(a.text).read_text(encoding="utf8")
        manifest["note_sha256"] = audit.sha(note)
        reason.write_prompt(out / "prompt_extract_text.md", intake.prompt_extract_text(note))
        if a.llm:
            _save(out / "extract_text.json", reason.parse_json(reason.call_llm(intake.prompt_extract_text(note))))
    if a.fhir:
        P, E, un = fhir.fhir_to_case(_load(a.fhir))
        _save(out / "patient.json", P); _save(out / "encounter.json", E); _save(out / "fhir_unmapped.json", un)
        manifest["fhir"] = {"unmapped": len(un)}
    _save(out / "intake_manifest.json", manifest)
    audit.log("extract", out.name, hook="patient-view", inputs=manifest, summary={k: (v if k != "capture" else v["sha256"]) for k, v in manifest.items()})
    print(f"[extract] prompts in {out}: " + ", ".join(p.name for p in out.glob("prompt_extract_*.md")) +
          "\n  → Claude가 각 프롬프트에 답해 extract_screen.json / extract_text.json 저장 후 `python -m agent merge --out {out}`")


def cmd_merge(a):
    out = pathlib.Path(a.out)
    scr = _load(str(out / "extract_screen.json")) if (out / "extract_screen.json").exists() else None
    txt = _load(str(out / "extract_text.json")) if (out / "extract_text.json").exists() else None
    if not scr and not txt:
        sys.exit("[merge] extract_screen.json / extract_text.json 둘 다 없음")
    P, E, ev = intake.merge(scr, txt)
    _save(out / "patient.json", P); _save(out / "encounter.json", E); _save(out / "extract_evidence.json", ev)
    audit.log("merge", out.name, patient=P, inputs={"screen": bool(scr), "text": bool(txt)}, summary={"unknown": ev["unknown_fields"]})
    print(f"[merge] patient.json / encounter.json written; unknown: {ev['unknown_fields']} → next: `confirm`")


def cmd_purge(a):
    pol = _load(str(pathlib.Path(__file__).resolve().parent.parent / "db" / "policy.json"))["retention"]
    res = audit.purge(pol["emr_capture_days"], pol["case_folder_days"], pathlib.Path(a.output_dir))
    audit.log("purge", "-", summary=res); print(f"[purge] {res}")


def cmd_eval(a):
    sys.exit(evaluate.main(fail_on_hard_miss=not a.no_fail))


def cmd_confirm(a):
    out = pathlib.Path(a.out)
    p = _load(str(out / "patient.json")); e = _load(str(out / "encounter.json"))
    ev = _load(str(out / "extract_evidence.json")) if (out / "extract_evidence.json").exists() else None
    if a.apply:
        sheet = (out / "confirm_sheet.md").read_text(encoding="utf8")
        p, e, ok, no = confirm.apply_sheet(sheet, p, e)
        _save(out / "patient.json", p); _save(out / "encounter.json", e)
        audit.log("confirm", out.name, patient=p, summary={"confirmed": ok, "unconfirmed": no})
        print(f"[confirm] confirmed {len(ok)}, unconfirmed→null {len(no)}: {no}")
    else:
        (out / "confirm_sheet.md").write_text(confirm.make_sheet(p, e, ev), encoding="utf8")
        print(f"[confirm] sheet written: {out/'confirm_sheet.md'} — 원무과가 [x] 체크 후 `confirm --apply`")


def cmd_match(a):
    kb = KB()
    out = pathlib.Path(a.out)
    p = load_patient(_load(a.patient))
    e = load_encounter(_load(a.encounter))
    facts = derive(p, e, kb)
    results = run_all(facts, kb)
    if not p.confirmed_fields:
        print("[match] WARNING: 추출 필드가 사람 확인을 거치지 않음 — `confirm` 단계 권장 (patient.confirmed_fields 비어 있음)")
    _save(out / "facts.json", facts)
    _save(out / "results.json", {"patient": to_dict(p), "encounter": to_dict(e), "results": [r.to_dict() for r in results]})
    (out / "staff_sheet.md").write_text(render.staff_markdown(p, e, facts, results), encoding="utf8")
    audit.log("match", out.name, patient=to_dict(p), hook="encounter-discharge", inputs={"patient": to_dict(p), "encounter": to_dict(e)},
              summary={r.program_id: r.status for r in results})
    rp = reason.prompt_resolve(results, facts, kb)
    if rp:
        reason.write_prompt(out / "prompt_resolve.md", rp)
    reason.write_prompt(out / "prompt_narrate.md", reason.prompt_narrate(results, p.name))
    print(f"[match] {sum(r.status=='eligible' for r in results)} eligible / {sum(r.status=='likely' for r in results)} likely / "
          f"{sum(r.status=='review' for r in results)} review / {sum(r.status=='ineligible' for r in results)} ineligible → {out}")
    for r in results:
        print(f"  {r.status:10s} {r.name:22s} {('~'+format(r.estimate,',')+'원') if r.estimate else ''}")
    return results


def cmd_resolve(a):
    out = pathlib.Path(a.out)
    data = _load(str(out / "results.json"))
    results = [Result(**d) for d in data["results"]]
    res = _load(a.resolution)
    results = reason.apply_resolution(results, res)
    data["results"] = [r.to_dict() for r in results]
    _save(out / "results.json", data)
    print(f"[resolve] applied {len(res)} LLM decisions")


def cmd_render(a):
    kb = KB()
    out = pathlib.Path(a.out)
    data = _load(str(out / "results.json"))
    p = load_patient(data["patient"]); e = load_encounter(data["encounter"])
    results = [Result(**d) for d in data["results"]]
    narrative = _load(a.narrative) if a.narrative else (_load(str(out / "narrative.json")) if (out / "narrative.json").exists() else None)
    ctx = render.build_context(p, e, results, narrative, kb)
    html = render.render_html(ctx)
    pdf = render.html_to_pdf(html, out / f"NDB_의료비지원안내_{p.name}.pdf")
    audit.log("render", out.name, patient=data["patient"], summary={"pdf_sha256": intake.sha256_file(pdf)})
    print(f"[render] {pdf}")
    return pdf


def cmd_run(a):
    out = pathlib.Path(a.out)
    results = cmd_match(a)
    if a.llm:
        kb = KB()
        facts = _load(str(out / "facts.json"))
        # dates were stringified; reason.prompt_resolve only reads facts for display
        rp = reason.prompt_resolve(results, facts, kb)
        if rp:
            res = reason.parse_json(reason.call_llm(rp))
            _save(out / "resolution.json", res)
            a.resolution = str(out / "resolution.json"); cmd_resolve(a)
            results = _results_from(out)
        nar = reason.parse_json(reason.call_llm(reason.prompt_narrate(results, load_patient(_load(a.patient)).name)))
        _save(out / "narrative.json", nar)
    a.narrative = None
    cmd_render(a)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ndb-medical-aid-agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("extract"); s.add_argument("--image"); s.add_argument("--text"); s.add_argument("--fhir"); s.add_argument("--out", required=True); s.add_argument("--llm", action="store_true"); s.set_defaults(fn=cmd_extract)
    s = sub.add_parser("merge"); s.add_argument("--out", required=True); s.set_defaults(fn=cmd_merge)
    s = sub.add_parser("purge"); s.add_argument("--output-dir", default="output"); s.set_defaults(fn=cmd_purge)
    s = sub.add_parser("eval"); s.add_argument("--no-fail", action="store_true"); s.set_defaults(fn=cmd_eval)
    s = sub.add_parser("confirm"); s.add_argument("--out", required=True); s.add_argument("--apply", action="store_true"); s.set_defaults(fn=cmd_confirm)
    s = sub.add_parser("match"); s.add_argument("--patient", required=True); s.add_argument("--encounter", required=True); s.add_argument("--out", required=True); s.set_defaults(fn=cmd_match)
    s = sub.add_parser("resolve"); s.add_argument("--out", required=True); s.add_argument("--resolution", required=True); s.set_defaults(fn=cmd_resolve)
    s = sub.add_parser("render"); s.add_argument("--out", required=True); s.add_argument("--narrative"); s.set_defaults(fn=cmd_render)
    s = sub.add_parser("run"); s.add_argument("--patient", required=True); s.add_argument("--encounter", required=True); s.add_argument("--out", required=True); s.add_argument("--llm", action="store_true"); s.add_argument("--narrative"); s.set_defaults(fn=cmd_run)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
