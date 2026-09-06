---
id: special_disease
name: 본인일부부담금 산정특례
level: national
agency: 국민건강보험공단 (병원 등록)
contact: nhis_namyangju
departments: [internal, neuro, surgery, spine, joint]
priority: 1
covers_noncovered: false
deadline: {type: at_diagnosis}
symbolic:
  hard:
    - {fact: special_category, op: neq, value: none, fail: "산정특례 대상 질환 아님"}
  amount: special_disease_amount
documents: [special_disease_registration_form]
---
# 산정특례 (본인일부부담금 산정특례)

| 질환군 | 본인부담률 | 기간 | 등록 |
|---|---|---|---|
| 암 | 5% | 5년 | 병원 신청서 → 공단 |
| 뇌혈관·심장질환·중증외상 | 5% | 최대 30일 | 별도 등록 없이 적용 |
| 희귀·중증난치질환 | 10% → 2026 하반기 5% 인하 예정 | 5년 | 병원 신청서 → 공단 |
| 중증화상 | 5% | 1년(재등록) | 병원 신청 |
| 결핵 | 0% | 치료 종결까지 | 병원 신청 |
| 중증치매 | 10% | 5년 | 병원 신청 |

급여 항목에만 적용. 비급여·식대·상급병실료 제외. **등록일부터 적용(소급 제한)** — 진단 즉시 등록이 원무과 핵심 업무.

## 신경-기호 경계
- 상병코드 → 질환군 매핑은 기호 규칙(`db/special_disease_map.json`)으로 처리하되, 코드가 없고 서술만 있을 때는 LLM이 후보 질환군을 제시하고 `review`로 남긴다.
- 척추 관련: 강직성 척추염(M45) 등 중증난치 해당 질환은 척추센터에서도 등록 대상.
