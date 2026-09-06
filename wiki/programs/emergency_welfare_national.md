---
id: emergency_welfare_national
name: 긴급복지 의료지원 (국가형)
level: national
agency: 보건복지부·읍면동 행정복지센터
contact: welfare_129
departments: [spine, joint, internal, neuro, surgery]
priority: 3
covers_noncovered: partial
deadline: {type: before_discharge}
symbolic:
  hard:
    - {fact: income_pct, op: lte, ref: emergency_welfare_national.income_pct_max, fail: "기준중위소득 75% 초과"}
    - {fact: has_crisis_event, op: eq, value: true, fail: "위기사유 없음"}
  soft:
    - {fact: assets, op: lte, ref: emergency_welfare_national.asset_cap_by_area.city, warn: "재산 기준(중소도시 1억 5,200만 원) 초과 가능"}
  amount: emergency_national_amount
documents: [receipt, diagnosis_certificate, admission_certificate, id_card, bankbook]
---
# 긴급복지 의료지원 (국가형)

갑작스러운 위기(주소득자 중병·사망·실직·폐업, 학대, 화재 등)로 생계가 어려운 가구에 **선지원 후조사**로 의료비 300만 원 이내(1회, 추가 1회) 및 생계비(1인 78.3만~4인 199.5만 원/월, 최대 6개월) 지원.

## 핵심 규칙
- 소득: 기준중위소득 75% 이하 (1인 약 192만, 4인 약 487만 원)
- 재산: 대도시 2억 4,100만 / 중소도시 1억 5,200만 / 농어촌 1억 3,000만 원 이하
- 금융재산: 600만 원 + 가구별 생활준비금 이하
- **퇴원 전 신청 원칙** — 입원 중 129 신고 가능

## 신경-기호 경계
- 진료내용·상담 메모에서 **위기사유** 추출 (환자가 "가장이 아파서 일을 못 한다"고 말하면 main_earner_serious_illness)
- 위기사유의 "중한 질병" 해당 여부는 의학적 판단이 필요 → LLM이 진단명·수술 여부로 판단하고 근거를 남김
