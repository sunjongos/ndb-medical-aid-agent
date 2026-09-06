"""Evaluation harness: gold cases in eval/cases/*.json → per-program accuracy report (eval/report.md).

Each gold case: {description, patient, encounter, expected: {program_id: status}}.
A regression in status for any expected pair fails CI. Statuses are compared exactly, except that
`eligible`↔`likely` mismatches are counted as *soft* misses (verification flags may flip them) and reported separately.
"""
from __future__ import annotations
import json, pathlib, datetime
from collections import defaultdict
from typing import Dict, Any, List, Tuple
from .kb import KB
from .models import load_patient, load_encounter
from .facts import derive
from .rules import run_all

ROOT = pathlib.Path(__file__).resolve().parent.parent
CASES = ROOT / "eval" / "cases"
SOFT = {frozenset({"eligible", "likely"})}


def run(case_dir: pathlib.Path = CASES) -> Tuple[Dict[str, Any], str]:
    kb = KB()
    rows: List[Dict[str, Any]] = []
    per_prog = defaultdict(lambda: {"n": 0, "hit": 0, "soft": 0})
    for f in sorted(case_dir.glob("*.json")):
        c = json.loads(f.read_text(encoding="utf8"))
        p = load_patient(c["patient"]); e = load_encounter(c["encounter"])
        R = {r.program_id: r for r in run_all(derive(p, e, kb), kb)}
        for pid, exp in c["expected"].items():
            got = R[pid].status
            hit = got == exp; soft = (not hit) and frozenset({got, exp}) in SOFT
            per_prog[pid]["n"] += 1; per_prog[pid]["hit"] += hit; per_prog[pid]["soft"] += soft
            rows.append({"case": f.stem, "program": pid, "expected": exp, "got": got, "ok": hit, "soft": soft,
                         "why": "; ".join(R[pid].reasons + R[pid].unknowns)[:120]})
    n = len(rows); hits = sum(r["ok"] for r in rows); softs = sum(r["soft"] for r in rows)
    hard_miss = n - hits - softs
    summary = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), "n": n, "exact": hits, "soft": softs, "hard_miss": hard_miss,
               "exact_acc": round(hits / n, 3) if n else None, "lenient_acc": round((hits + softs) / n, 3) if n else None,
               "per_program": {k: {**v, "acc": round(v["hit"] / v["n"], 3)} for k, v in per_prog.items()}, "rows": rows}
    md = [f"# 평가 리포트 ({summary['ts']})", "", f"- 골드 판정 {n}건 · 정확 일치 {hits} · eligible/likely 차이 {softs} · **불일치 {hard_miss}**",
          f"- exact accuracy **{summary['exact_acc']}** · lenient **{summary['lenient_acc']}**", "", "| 제도 | n | 정확 | soft | acc |", "|---|---|---|---|---|"]
    for k, v in sorted(summary["per_program"].items()):
        md.append(f"| {k} | {v['n']} | {v['hit']} | {v['soft']} | {v['acc']} |")
    bad = [r for r in rows if not r["ok"]]
    if bad:
        md += ["", "## 불일치 상세", "", "| 케이스 | 제도 | 기대 | 결과 | soft | 사유 |", "|---|---|---|---|---|---|"]
        md += [f"| {r['case']} | {r['program']} | {r['expected']} | {r['got']} | {'○' if r['soft'] else ''} | {r['why']} |" for r in bad]
    return summary, "\n".join(md) + "\n"


def main(fail_on_hard_miss: bool = True) -> int:
    s, md = run()
    (ROOT / "eval" / "report.md").write_text(md, encoding="utf8")
    (ROOT / "eval" / "report.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf8")
    print(md)
    return 1 if (fail_on_hard_miss and s["hard_miss"]) else 0
