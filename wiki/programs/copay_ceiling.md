---
id: copay_ceiling
name: 본인부담상한제
level: national
agency: 국민건강보험공단
contact: nhis_namyangju
departments: [spine, joint, internal, neuro, surgery]
priority: 2
covers_noncovered: false
deadline: {type: after_year_end, years: 3}
symbolic:
  hard:
    - {fact: insurance, op: in, value: [nhi_employee, nhi_regional], fail: "건강보험 가입자만 해당(의료급여는 별도 상한제)"}
  amount: copay_ceiling_amount
documents: []
---
# 본인부담상한제

1년간(1/1~12/31) 여러 요양기관에서 낸 **급여 본인부담금 합계**가 소득분위별 상한액을 넘으면 초과분 전액을 공단이 환급. 자동 산정되며 매년 8월 안내문 발송. 신청하지 않으면 3년 뒤 소멸.

## 2026년 진료분 상한액
1분위 90만 / 2~3분위 112만 / 4~5분위 173만 / 6~7분위 326만 / 8분위 446만 / 9분위 536만 / 10분위 843만 원 (요양병원 120일 초과 시 별도 상향).

## 제외
비급여, 선별급여, 임플란트, 2~3인실 입원료, 추나요법 등.

## 사전급여
같은 병원에서 한 해 본인부담이 최고 상한액(843만 원)을 넘으면 병원이 초과분을 받지 않고 공단에 직접 청구 → 원무과 청구 담당 확인 사항.

## 신경-기호 경계
- 환자의 **소득분위**는 건강보험료로 추정만 가능 → 엔진은 `income_decile` 입력이 없으면 중위소득 %로 근사하고 `review`로 표시.
