#!/usr/bin/env bash
# Usage: GH_TOKEN=ghp_xxx ./scripts/push_to_github.sh   (or run `gh auth login` first and omit GH_TOKEN)
set -euo pipefail
REPO=ndb-medical-aid-agent
OWNER=sunjongos
cd "$(dirname "$0")/.."
git init -q 2>/dev/null || true
git add -A && git commit -qm "feat: NDB medical-aid neurosymbolic agent skill v0.1.0" || true
if command -v gh >/dev/null; then
  gh repo create "$OWNER/$REPO" --public --source=. --remote=origin --push --description "남양주백병원 의료비 지원 매칭 에이전트 (LLM-wiki ontology + symbolic rules → 환자 카톡 PDF)"
else
  curl -s -H "Authorization: token ${GH_TOKEN}" https://api.github.com/user/repos -d "{\"name\":\"$REPO\",\"private\":false}" >/dev/null
  git remote add origin "https://${GH_TOKEN}@github.com/$OWNER/$REPO.git" 2>/dev/null || true
  git branch -M main && git push -u origin main
fi
echo "pushed → https://github.com/$OWNER/$REPO"
