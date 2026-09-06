---
id: dementia_aid
name: 치매 검진비·치료관리비
level: national_local
agency: 보건소·치매안심센터
contact: namyangju_health_center
departments: [neuro, internal]
priority: 3
covers_noncovered: false
deadline: {type: annual}
symbolic:
  hard:
    - {fact: age, op: gte, ref: dementia.age_min, fail: "만 60세 미만"}
    - {fact: cognitive_concern, op: eq, value: true, fail: "인지저하 호소·치매 진단 없음"}
  soft:
    - {fact: income_pct, op: lte, ref: dementia.income_pct_max, warn: "감별검사비는 중위 120% 이하만"}
  amount: dementia_amount
documents: [id_card]
---
# 치매 검진비·치료관리비

- 선별검사: 보건소·치매안심센터 무료, 인지저하 시 진단검사 연계
- 감별검사비: 60세 이상, 중위 120% 이하 → 8~11만 원
- 치료관리비: 월 3만 원(연 36만 원) — 지자체별. 남양주시 시행 여부 **UNCONFIRMED** (원무팀 확인 후 db 갱신)
