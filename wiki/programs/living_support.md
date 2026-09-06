---
id: living_support
name: 긴급복지 생계지원
level: national
agency: 읍면동 행정복지센터
contact: welfare_129
departments: [spine, joint, internal, neuro, surgery]
priority: 4
covers_noncovered: false
deadline: {type: asap}
symbolic:
  hard:
    - {fact: income_pct, op: lte, ref: emergency_welfare_national.income_pct_max, fail: "기준중위소득 75% 초과"}
    - {fact: has_crisis_event, op: eq, value: true, fail: "위기사유 없음"}
  amount: living_amount
documents: [id_card, bankbook]
---
# 긴급복지 생계지원

위기가구에 압류 금지 현금 지급. 1인 78.3만 / 2인 128.7만 / 3인 164.4만 / 4인 199.5만 원(월), 기본 3개월·최대 6개월. 의료지원과 별도 신청 가능.
