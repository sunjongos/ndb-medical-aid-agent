# NDB 의료비 지원 LLM-Wiki (온톨로지 DB)

각 페이지의 YAML frontmatter가 **기호(symbolic) 규칙**이고, 본문이 **LLM이 읽는 맥락**이다. `agent/kb.py`가 frontmatter를 파싱해 규칙 엔진에 넘기고, 본문은 `review` 항목을 추론할 때 LLM 프롬프트에 삽입된다.

## 엔티티 온톨로지
- **Program** (`wiki/programs/*.md`): id, level(national/province/local), agency, contact, departments, priority, covers_noncovered, deadline, symbolic{hard, soft, band, amount}, excluded_costs, documents
- **Patient** (`agent/models.py:Patient`): 인구·소득·재산·수급자격·위기사유·간병·거주지
- **Encounter** (`agent/models.py:Encounter`): 진료과·상병·진료형태·수술·비용 구조·산정특례
- **Threshold** (`db/thresholds_2026.json`): 연도별 수치. 페이지의 `ref:` 경로가 이 파일을 가리킨다.
- **Fact** (`agent/facts.py`): Patient+Encounter → 규칙이 평가하는 원자 사실(income_pct, special_category, has_crisis_event …)

## 페이지 목록
| id | 제도 | 우선순위 | 비급여 |
|---|---|---|---|
| catastrophic_medical | 재난적 의료비 | 1 | ○ |
| special_disease | 산정특례 | 1 | × |
| knee_replacement | 노인 인공관절 | 1 | △ |
| copay_ceiling | 본인부담상한제 | 2 | × |
| cancer_aid | 암환자 의료비 | 2 | ○ |
| rare_disease_aid | 희귀질환 의료비 | 2 | × |
| emergency_welfare_national | 긴급복지 의료지원 | 3 | △ |
| dementia_aid | 치매 검진·관리비 | 3 | × |
| medical_aid_copay_refund | 의료급여 보상금 | 3 | × |
| emergency_welfare_gyeonggi | 경기도 무한돌봄 | 4 | ○ |
| living_support | 긴급복지 생계 | 4 | — |
| senior65_benefits | 65세+ 접종·치과 | 5 | × |

## 갱신 규칙
분기 1회 `db/thresholds_2026.json`과 각 페이지 `출처` 절을 공단·경기도·남양주시 고시로 대조. 연도가 바뀌면 `thresholds_2027.json`을 추가하고 `agent/kb.py`의 `YEAR`를 올린다.
