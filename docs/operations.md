# 운영 규범 (CDS 운영 · 개인정보 · 지식 거버넌스)

임상 의사결정지원(CDS) 소프트웨어의 일반 관행 — HL7 CDS Hooks 트리거 모델, 감사 추적, 최소 수집, 설명가능성, 사람 확인, 검증 주기 — 을 남양주백병원 원무 흐름에 맞춰 적용한다.

## 1. 트리거 (지금은 수동, EMR 연동 시 자동)
| 시점 | CDS Hook | 담당 | 실행 |
|---|---|---|---|
| 외래 접수 | patient-view | 외래 간호사 | 30초 스크리닝 카드 → 해당 시 `extract --image --text` |
| 수술·입원 결정 | order-sign | 원무과 | 인공관절 사전신청·산정특례 등록 확인 |
| 퇴원 결정 | encounter-discharge | 원무과 | `confirm` → `match` → `render` → 카톡 전송 · 180일 기한 고지 |

감사로그의 `hook` 필드에 동일한 이벤트명을 기록하므로, EMR이 붙어도 로그 스키마는 그대로다.

## 2. 입력 원칙
- EMR 화면 캡처는 **환자 기본정보 필드만** 읽는다(`intake.PATIENT_FIELDS_FROM_SCREEN`). 진료내용·비용·사회경제 정보는 텍스트 입력.
- 추출값마다 **근거(evidence)** 를 남기고, 원무과가 `confirm_sheet.md`에서 체크해야 판정에 쓰인다. 미확인은 null → `review`.
- FHIR R4 Bundle 입력(`extract --fhir`)은 EMR 직접 연동 시의 계약이다. 로컬 CodeSystem 3종(cost-category, sdoh, coverage-type)만 맞추면 된다.

## 3. 개인정보
- 화면 캡처·케이스 폴더는 `output/`(git 제외). 보존기간은 `db/policy.json` — 캡처 7일, 케이스 180일(재난적 의료비 기한), 감사로그 5년.
- 감사로그에는 이름·전화 대신 `sha256(salt|name|age|phone)[:16]`만 기록. salt는 `NDB_AUDIT_SALT` 환경변수.
- `python -m agent purge`를 주 1회 크론으로 실행.
- 카톡 전송 PDF는 환자 본인 번호로만, 전송 후 원본은 케이스 폴더에 보존기간까지만.

## 4. 설명가능성
`results.json`의 각 제도에 `trace[]`가 있다: 평가한 규칙·비교값·참조한 수치 경로·pass/fail. 민원·감사 시 "왜 이 판정인가"를 규칙 단위로 답한다. 판정을 바꾸려면 `resolution.json`(검토자·근거 기록)으로만.

## 5. 지식 거버넌스
- 수치는 `db/thresholds_<year>.json` 한 곳. `verification` 섹션에 출처·검증 여부. 미검증 수치에 의존한 판정은 자동 `likely` 강등.
- 변경은 `db/CHANGELOG.md`에 2인(작성자+검증자) 기록 후 커밋. 분기 1회(90일) 공단·경기도·남양주시 고시 대조.
- 변경 후 반드시 `pytest -q`(경계값 65개) + `python -m agent eval`(골드 케이스) 통과. CI가 강제한다.

## 6. 역할 (policy.json)
nurse: screen/extract · admin_staff: confirm/match/render/send · social_worker: resolve · director: verify_thresholds/publish_wiki

## 7. 환자 커뮤니케이션 원칙
금액은 "최대 ~원까지 가능할 수 있음", 기한은 날짜, 최종 판정은 기관 심사. 병원은 서류·안내를 책임진다.
