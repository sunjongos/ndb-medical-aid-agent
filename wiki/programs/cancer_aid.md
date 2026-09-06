---
id: cancer_aid
name: 암환자 의료비 지원 (보건소)
level: national_local
agency: 남양주시 보건소
contact: namyangju_health_center
departments: [internal, surgery]
priority: 2
covers_noncovered: true
deadline: {type: annual}
symbolic:
  hard:
    - {fact: special_category, op: eq, value: cancer, fail: "암 진단 아님"}
    - {fact: beneficiary, op: in, ref: cancer_aid.beneficiary_required, fail: "의료급여·차상위 아님 (건강보험가입자 신규지원은 2021.6.30 종료)"}
  amount: cancer_aid_amount
documents: [diagnosis_certificate, receipt, id_card, bankbook]
---
# 암환자 의료비 지원 (보건소)

의료급여수급자·차상위 본인부담경감대상자 성인 암환자에게 급여·비급여 구분 없이 **연 300만 원, 연속 3년**. 건강보험가입자 신규 지원은 2021-06-30 종료(한시 적용자만). 소아암은 백혈병 3,000만·기타 2,000만 원. 주소지 보건소 연중 접수, 진단서(최종진단일·상병코드) 필요.
