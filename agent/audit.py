"""Append-only audit trail (JSONL). One line per pipeline step. No names/phones — only a salted patient key.

Fields: ts, case, patient_key, actor, step, hook, kb_version, thresholds_updated, inputs_sha256, summary
"""
from __future__ import annotations
import hashlib, json, os, pathlib, subprocess, datetime
from typing import Any, Dict

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG = ROOT / "audit" / "audit.jsonl"
SALT = os.environ.get("NDB_AUDIT_SALT", "ndb-default-salt-change-me")


def kb_version() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "nogit"


def patient_key(name: str | None, age: Any, phone: str | None) -> str:
    return hashlib.sha256(f"{SALT}|{name}|{age}|{phone}".encode()).hexdigest()[:16]


def sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:16]


def log(step: str, case: str, patient: Dict[str, Any] | None = None, hook: str | None = None, inputs: Any = None, summary: Any = None):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    thr = json.loads((ROOT / "db" / "thresholds_2026.json").read_text(encoding="utf8"))
    rec = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "case": case, "patient_key": patient_key(patient.get("name"), patient.get("age"), patient.get("phone")) if patient else None,
        "actor": os.environ.get("NDB_ACTOR", os.environ.get("USER", "unknown")),
        "step": step, "hook": hook, "kb_version": kb_version(), "thresholds_updated": thr.get("updated"),
        "inputs_sha256": sha(inputs) if inputs is not None else None, "summary": summary,
    }
    with open(LOG, "a", encoding="utf8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def purge(days_capture: int, days_case: int, output_dir: pathlib.Path) -> Dict[str, int]:
    """Delete EMR captures older than N days and case folders older than M days (retention policy)."""
    now = datetime.datetime.now().timestamp(); n_cap = n_case = 0
    for case in output_dir.glob("*"):
        if not case.is_dir():
            continue
        for cap in case.glob("emr_capture.*"):
            if now - cap.stat().st_mtime > days_capture * 86400:
                cap.unlink(); n_cap += 1
        if now - case.stat().st_mtime > days_case * 86400:
            import shutil; shutil.rmtree(case); n_case += 1
    return {"captures_deleted": n_cap, "cases_deleted": n_case}
