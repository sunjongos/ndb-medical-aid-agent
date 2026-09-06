# ndb-medical-aid-agent-for-antigravity

남양주백병원(NDB) 환자 의료비 지원 매칭 에이전트 — **LLM-wiki 온톨로지 + 기호 규칙 엔진(neurosymbolic)** → 원무과 판정 시트 + 환자 카톡용 PDF (Google Antigravity IDE & Claude Code 최적화).

```
환자 정보 + 진료내용 ──► [LLM/Claude: 추출] ──► patient.json / encounter.json
                                               │
                    wiki/programs/*.md ◄──────┤  db/thresholds_2026.json
                    (규칙 frontmatter+맥락)     ▼
                                  [rules.py: 기호 판정] ──► results.json / staff_sheet.md
                                              │ review 항목
                                  [LLM: 위키 근거 검토] ──► resolution.json
                                              │
                                  [LLM: 환자 문장] ──► narrative.json
                                              ▼
                                  [render.py: Playwright] ──► NDB_의료비지원안내_<이름>.pdf (120×213mm)
```

## 제도 12종
재난적 의료비 · 본인부담상한제 · 긴급복지 의료지원(국가) · 경기도형 긴급복지(무한돌봄) · 산정특례 · 암환자 의료비 · 희귀질환 의료비 · 노인 인공관절 · 치매 검진·관리비 · 65세+ 접종·치과 · 의료급여 본인부담 보상 · 긴급복지 생계지원

## 입력 경로 3가지
| 경로 | 명령 | 용도 |
|---|---|---|
| EMR 화면 캡처 + 진료내용 텍스트 | `extract --image --text` → LLM 판독 → `merge` | **현재 운영 방식** |
| JSON 직접 | `match --patient --encounter` | 테스트·재실행 |
| FHIR R4 Bundle | `extract --fhir` | EMR 직접 연동 시 (로컬 CodeSystem 3종) |

## 운영 규범
`docs/operations.md` — CDS Hooks식 트리거, 감사로그(`audit/audit.jsonl`, PHI 없음), 보존기간(`db/policy.json`, `purge`), 설명가능성(`results.json.trace`), 2인 검증·분기 대조.

## 평가
`python -m agent eval` → `eval/report.md`. 골드 케이스는 `eval/cases/*.json`(진료과별 7건). CI에서 hard miss 발생 시 실패.

## 빠른 시작
```bash
pip install -r requirements.txt && python -m playwright install chromium
python -m agent match --patient examples/patient_spine.json --encounter examples/encounter_spine.json --out output/spine
python -m agent render --out output/spine          # narrative.json 없으면 기본 문구
pytest -q      # 65 tests: 경계값·확인시트·FHIR·감사·회귀
```
Docker:
```bash
docker build -t ndb-aid .
docker run --rm -v $PWD/output:/app/output ndb-aid run --patient examples/patient_spine.json --encounter examples/encounter_spine.json --out output/spine
```

## Google Antigravity IDE 스킬로 설치
Antigravity IDE 워크스페이스의 `.agent/skills/ndb-medical-aid-agent/`에 등록하거나 링크합니다:
```bash
mkdir -p .agent/skills/ndb-medical-aid-agent
cp SKILL.md .agent/skills/ndb-medical-aid-agent/
```
이후 Antigravity IDE에서 "이 환자 의료비 지원 되나?", "원무과 상담", "재난적 의료비", "산정특례" 등을 요청하면 `SKILL.md` 순서대로 기호 엔진과 LLM이 자동 실행됩니다.

## Claude Code 스킬로 설치
```bash
mkdir -p ~/.claude/skills && ln -s "$PWD" ~/.claude/skills/ndb-medical-aid-agent
```
이후 Claude Code에서 "이 환자 의료비 지원 되나?"라고 물으면 `SKILL.md` 순서대로 실행한다.

## 검증 상태 (verification)
`db/thresholds_2026.json` → `verification` 섹션. `verified: false`인 수치에 의존한 판정은 자동으로 `likely`로 강등되고 "수치 미검증" 경고가 붙는다. 현재 미검증: copay_ceiling, rare_disease_aid, knee_replacement, dementia, medical_aid_copay. 원무팀이 원문 대조 후 true로 바꾸면 경고가 사라진다.

## 사람 확인 단계
LLM이 추출한 필드는 `python -m agent confirm`이 만드는 `confirm_sheet.md`에서 원무과가 체크해야 판정에 반영된다. 미확인 필드는 null 처리되어 `review`로 남는다.

## 판정 상태
| status | 의미 |
|---|---|
| eligible | 하드 규칙 전부 통과 |
| likely | 통과했으나 소프트 경고(재산 미확인, 개별심사 등) |
| review | 하드 규칙이 **미확인 사실**에 걸림 → Claude/직원 검토 |
| ineligible | 확인된 사실로 하드 규칙 실패 |

## 온톨로지 그래프
`knowledge_assets/ontology_graph.json` — `wiki/programs/*.md` frontmatter에서 자동 생성한 지식 그래프(제도·사실·수치·기관·진료과 노드, vis-network nodes/edges 스키마). 외부 DB 없이 패키지 단독으로 온톨로지를 탐색할 수 있다. 위키 갱신 후 재생성 필요.

## 지식 갱신
- 수치: `db/thresholds_2026.json` (분기 1회 공단·경기도·남양주시 고시 대조)
- 규칙·맥락: `wiki/programs/<id>.md`
- 미확인: 남양주시 치매 치료관리비 시행 여부, 보건소 대표번호, 원무과 내선 → `UNCONFIRMED` / `[확인 필요]`

## 출처
보건복지부 정책브리핑, 국민건강보험공단, 경기도청, 시군 보건소 공개자료, 조선일보 2026-09-05. `assets/`에 원본 직원 매뉴얼·환자 안내책자 포함.

## 면책
판정은 참고용이며 최종 지원 여부·금액은 각 기관 심사로 결정된다. 환자에게 금액을 약속하지 않는다.
