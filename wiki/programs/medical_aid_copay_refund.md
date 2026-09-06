---
id: medical_aid_copay_refund
name: 의료급여 본인부담 상한·보상금
level: national
agency: 국민건강보험공단
contact: nhis_namyangju
departments: [spine, joint, internal, neuro, surgery]
priority: 3
covers_noncovered: false
deadline: {type: none}
symbolic:
  hard:
    - {fact: beneficiary, op: in, value: [medical_aid_1, medical_aid_2], fail: "의료급여 수급자 아님"}
  amount: medical_aid_refund_amount
documents: []
---
# 의료급여 본인부담 상한·보상금

외래 1회 본인부담 최대 2만 원, 약국 5천 원, 월 5만 원 상한. 30일간 1종 2만 원·2종 20만 원 초과 시 초과분의 50% 보상금. 원무과는 수급자 청구 시 상한 적용 여부 확인.
