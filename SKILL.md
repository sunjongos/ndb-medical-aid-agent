---
name: ndb-medical-aid-agent
description: 남양주백병원 환자의 의료비 지원 제도(재난적 의료비, 본인부담상한제, 긴급복지·경기도 무한돌봄, 산정특례, 암·희귀질환·치매·인공관절 지원 등 12종)를 LLM-wiki 온톨로지 + 기호 규칙 엔진(neurosymbolic)으로 자동 매칭하고, 원무과 판정 시트와 환자에게 카톡으로 보낼 안내 PDF까지 생성한다. 환자 정보·진료내용·비용을 주면서 "의료비 지원", "지원 받을 수 있나", "재난적 의료비", "긴급복지", "산정특례", "환자 안내문 만들어", "원무과 상담", "병원비 부담", "카톡으로 보낼 PDF"를 언급하면 반드시 이 스킬을 사용한다. 진료과(척추·관절·내과·신경과·외과) 무관. 외래 간호사 메모나 자유 텍스트만 있어도 작동한다.
---

# NDB 의료비 지원 매칭 에이전트

**구조**: `wiki/programs/*.md`(제도별 규칙 frontmatter + LLM 맥락 본문) + `db/thresholds_2026.json`(수치) → `agent/rules.py`(기호 판정) ↔ Claude(신경 추론: 추출·검토·안내문) → `agent/render.py`(카톡용 PDF).

원칙: **기호 엔진이 판정, Claude는 빈칸을 채우고 애매한 것을 위키 근거로 검토하며 환자 문장을 쓴다.** Claude가 위키에 없는 기준을 만들거나 금액을 약속하면 안 된다.

## 실행 순서

### 0. 환경
```bash
pip install -r requirements.txt && python -m playwright install chromium   # 최초 1회
# 또는: docker build -t ndb-aid . && docker run --rm -v $PWD/output:/app/output ndb-aid run ...
```

### 1. 입력 확보 (EMR 화면 캡처 + 진료내용 텍스트)
사용자가 EMR 환자정보 화면 캡처(이미지)와 진료내용(텍스트)을 준다. 진료내용을 파일로 저장한 뒤:
```bash
python -m agent extract --image <캡처.png> --text <note.txt> --out output/<case>
```
그러면 `prompt_extract_screen.md`, `prompt_extract_text.md`가 생긴다. **Claude가 직접**:
1. 캡처 이미지를 보고 `prompt_extract_screen.md`에 답해 `output/<case>/extract_screen.json` 저장 (환자 기본정보 필드만, 화면 근거 evidence 필수, 없으면 null)
2. `prompt_extract_text.md`에 답해 `output/<case>/extract_text.json` 저장 (진료·비용·사회경제 정보)
3. `python -m agent merge --out output/<case>` → patient.json / encounter.json / extract_evidence.json

사용자가 JSON을 직접 주면 1~3 생략. FHIR Bundle이 있으면 `extract --fhir bundle.json`.
캡처 이미지는 PHI — `output/` 밖으로 복사하지 말고, 대화에 내용을 옮겨 적지 않는다.

### 1.5 사람 확인 (LLM 추출을 썼다면 필수)
```bash
python -m agent confirm --out output/<case>            # confirm_sheet.md 생성
# 원무과가 각 줄 [ ]→[x] 체크·값 수정 후
python -m agent confirm --out output/<case> --apply    # 미확인 필드는 null → 판정에서 review
```
JSON을 사용자가 직접 준 경우에는 생략 가능. `patient.confirmed_fields`가 비어 있으면 match가 경고를 낸다.

### 2. 기호 판정
```bash
python -m agent match --patient output/<case>/patient.json --encounter output/<case>/encounter.json --out output/<case>
```
생성물: `results.json`(제도별 status: eligible/likely/review/ineligible + 추정액·기한·서류), `facts.json`, `staff_sheet.md`(원무과 시트), `prompt_resolve.md`(review가 있을 때), `prompt_narrate.md`.

### 3. 검토 (review 항목이 있을 때만)
`prompt_resolve.md`를 읽고 위키 본문 근거로 판단해 `output/<case>/resolution.json`(JSON 배열)을 저장한 뒤:
```bash
python -m agent resolve --out output/<case> --resolution output/<case>/resolution.json
```
확정 불가하면 `status: review` 유지 + `ask_staff` 질문을 남긴다. 사용자에게 그 질문을 그대로 물어본 뒤 재실행해도 된다.

### 4. 환자 안내문 작성
`prompt_narrate.md`를 읽고 `output/<case>/narrative.json` 저장(intro / items[program_id,title,text] / closing). 문장 원칙: 금액은 가능성으로만, 기한은 날짜로, 제도별 3문장 이내, 의학용어 괄호 설명.

### 5. PDF 생성 (카톡 전송용, 120×213mm)
```bash
python -m agent render --out output/<case>
```
→ `output/<case>/NDB_의료비지원안내_<이름>.pdf`. 사용자에게 경로와 `staff_sheet.md` 요약(eligible/likely/review 개수, 최우선 제도, 가장 급한 기한)을 보고한다.

### 6. 마무리
- 사용자에게 보고: eligible/likely/review 개수, 최우선 제도, 가장 급한 기한, `staff_sheet.md` 경로, PDF 경로.
- 판정 근거를 물으면 `results.json`의 `trace[]`를 규칙 단위로 설명한다.
- 모든 단계는 `audit/audit.jsonl`에 자동 기록된다(이름·전화 없이 해시 키만).

### 원샷 (API 키가 있을 때)
```bash
ANTHROPIC_API_KEY=... python -m agent run --patient p.json --encounter e.json --out output/<case> --llm
```

## 판정 결과 읽는 법
- `likely` 경고에 "수치 미검증 섹션"이 있으면 `db/thresholds_2026.json`의 `verification`이 false인 수치에 의존한 것 — 사용자에게 원문 대조가 필요하다고 알린다. 검증되면 `verified: true`로 바꾸고 커밋.
- 재난적 의료비와 본인부담상한제는 병행 제도 — 급여 본인부담은 상한제, 비급여·전액본인부담은 재난적 의료비. 환자에게 합산해서 말하지 않는다.
- 상한제 추정은 `patient.covered_copay_ytd`(올해 타기관 급여 본인부담 누계)를 받아야 정확하다.

## Claude가 지켜야 할 규칙
- 판정 결과를 바꾸고 싶으면 `resolution.json`으로만 바꾼다(코드·결과 파일 직접 수정 금지). 근거는 반드시 위키 본문 인용.
- 산정특례 질환군을 서술만으로 추정했다면 `special_category_override`에 넣되 `review`로 표시되게 `special_disease_registered=false`로 둔다.
- 도수치료·1인실은 재난적 의료비 제외 항목 — 비용에 반드시 분리 입력.
- 남양주시 치매 치료관리비, 보건소 전화, 원무과 내선은 `db/thresholds_2026.json`에 UNCONFIRMED/[확인 필요]로 되어 있음. 사용자가 알려주면 그 파일을 갱신하고 커밋한다.
- 개인정보: `output/`은 git 제외. 환자 이름·전화는 PDF 파일명과 본문에만 사용.

## 품질 게이트 (지식·코드 변경 시 반드시)
```bash
pytest -q                 # 경계값·확인시트·FHIR·감사 65개
python -m agent eval      # 골드 케이스 7건 × 42판정, hard miss 0이어야 함 → eval/report.md
```
운영 규범(트리거·개인정보·거버넌스)은 `docs/operations.md`.

## 지식 갱신
새 제도·수치 변경 시 `wiki/programs/<id>.md`의 frontmatter(hard/soft/amount)와 `db/thresholds_<year>.json`을 함께 수정하고 `pytest -q`로 회귀 확인. 규칙 DSL: `{fact, op(lte|gte|eq|neq|in|not_null), ref(thresholds 경로)|value, fail|warn}`. 새 추정 함수는 `agent/rules.py:AMOUNTS`에 등록.

## Antigravity IDE & LUCA 뇌 시스템 연계
- **대뇌피질 (Port 5050 HBM 메모리)**: 환자 매칭 및 원무과 상담 이력 캐싱
- **심층피질 (Neo4j Graph DB)**: `knowledge_assets/ontology_graph.json` 지식그래프 노드/관계 연동
- **NDB Palantir DSS**: 환자 본인부담 감면 시뮬레이션 데이터를 병원 재무/미수금 리스크 관리 모델과 실시간 연계

## 참고 파일
- `wiki/index.md` — 온톨로지 설명·제도 목록
- `assets/` — 직원 매뉴얼 v2·환자 안내책자(원본 HTML/PDF), 위키의 출처
- `examples/` — 척추·내과 샘플 JSON, 관절센터 간호사 메모
- `tests/test_rules.py` — 회귀 테스트
