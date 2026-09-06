"""Load the LLM-wiki (ontology) and thresholds DB."""
from __future__ import annotations
import json, re, pathlib
from typing import Dict, Any, List
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
YEAR = 2026
FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.S)


class KB:
    def __init__(self, root: pathlib.Path = ROOT, year: int = YEAR):
        self.root = root
        self.thresholds: Dict[str, Any] = json.loads((root / "db" / f"thresholds_{year}.json").read_text(encoding="utf8"))
        self.special_map: Dict[str, Any] = json.loads((root / "db" / "special_disease_map.json").read_text(encoding="utf8"))
        self.programs: Dict[str, Dict[str, Any]] = {}
        self.bodies: Dict[str, str] = {}
        for p in sorted((root / "wiki" / "programs").glob("*.md")):
            fm, body = self._parse(p.read_text(encoding="utf8"))
            self.programs[fm["id"]] = fm
            self.bodies[fm["id"]] = body

    @staticmethod
    def _parse(text: str):
        m = FM_RE.match(text)
        if not m:
            raise ValueError("wiki page without frontmatter")
        return yaml.safe_load(m.group(1)), m.group(2)

    def ref(self, path: str) -> Any:
        """Resolve 'a.b.c' into thresholds JSON."""
        cur: Any = self.thresholds
        for k in path.split("."):
            cur = cur[k]
        return cur

    def median_income(self, household: int) -> int:
        mi = self.thresholds["median_income_monthly"]
        if str(household) in mi:
            return mi[str(household)]
        base = mi["6"]
        return base + (household - 6) * mi["per_additional_member"]

    def special_category(self, codes: List[str]) -> str | None:
        pm = self.special_map["prefix_map"]
        best = None
        for c in codes:
            c = c.upper().strip()
            for prefix in sorted(pm, key=len, reverse=True):
                if c.startswith(prefix):
                    cat = pm[prefix]
                    # priority: cancer > cerebrovascular/cardiac > others
                    if best is None or _rank(cat) < _rank(best):
                        best = cat
                    break
        return best

    def contact(self, key: str) -> Dict[str, str]:
        return self.thresholds["contacts"].get(key, {"name": key, "tel": ""})

    def ordered_programs(self) -> List[Dict[str, Any]]:
        return sorted(self.programs.values(), key=lambda p: (p.get("priority", 9), p["id"]))


_RANK = {"cancer": 0, "cerebrovascular": 1, "cardiac": 1, "severe_burn": 2, "severe_trauma": 2, "tuberculosis": 3, "rare": 4, "intractable": 4, "severe_dementia": 5}


def _rank(cat: str) -> int:
    return _RANK.get(cat, 9)
