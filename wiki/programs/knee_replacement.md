---
id: knee_replacement
name: 노인 무릎 인공관절 수술비 지원
level: local
agency: 남양주시 보건소
contact: namyangju_health_center
departments: [joint]
priority: 1
covers_noncovered: partial
deadline: {type: before_surgery}
symbolic:
  hard:
    - {fact: age, op: gte, ref: knee_replacement.age_min, fail: "만 60세 미만"}
    - {fact: beneficiary, op: in, ref: knee_replacement.beneficiary_required, fail: "기초수급자·차상위·한부모 아님"}
    - {fact: procedure_knee_replacement, op: eq, value: true, fail: "무릎 인공관절 수술 아님"}
    - {fact: surgery_done, op: eq, value: false, fail: "이미 수술 완료 — 사전신청 불가"}
  soft:
    - {fact: region_city, op: eq, ref: knee_replacement.region_city, warn: "타 지자체 거주 — 거주지 보건소 조건·예산 확인 필요"}
  amount: knee_amount
documents: [surgery_recommendation, id_card, bankbook]
---
# 노인 무릎 인공관절 수술비 지원

만 60세 이상 기초수급자·차상위·한부모가정. 한쪽 무릎 100~120만 원 한도 실비(검사·진료·수술비, 비급여 일부 포함), 양쪽 240만 원. **수술 전** 주소지 보건소 사전 신청 필수, 예산 소진 시 조기 마감.
