---
id: emergency_welfare_gyeonggi
name: 경기도형 긴급복지 (무한돌봄)
level: province
agency: 경기도·읍면동 행정복지센터
contact: gyeonggi_hotline
departments: [spine, joint, internal, neuro, surgery]
priority: 4
covers_noncovered: true
deadline: {type: around_discharge, days: 30}
symbolic:
  hard:
    - {fact: region_gyeonggi, op: eq, value: true, fail: "경기도민 아님"}
    - {fact: income_pct, op: lte, ref: emergency_welfare_gyeonggi.income_pct_max, fail: "기준중위소득 100% 초과"}
    - {fact: has_crisis_event_gg, op: eq, value: true, fail: "위기사유 없음"}
  soft:
    - {fact: assets, op: lte, ref: emergency_welfare_gyeonggi.asset_cap_by_area.city, warn: "재산 기준(시 지역 3억 1,000만 원) 초과 가능"}
  amount: emergency_gyeonggi_amount
documents: [receipt, noncovered_itemized, diagnosis_certificate, admission_certificate, id_card, bankbook]
---
# 경기도형 긴급복지 (무한돌봄)

국가형 긴급복지에서 탈락했거나 지원 후에도 위기가 계속되는 **경기도민**을 위한 2차 안전망. 소득 기준이 중위 100%로 국가형보다 넓고, **간병비 300만 원**과 항암치료비 항목이 있다.

## 지원
- 비급여 의료비 300만 원 이내 (2회)
- 간병비 300만 원 이내 (1회) ← 척추 수술 후 간병 필요 환자에게 유용
- 항암치료비 100만 원 이내 (3회)
- 생계비 국가형과 동일 수준 (6회)

## 위기사유 (국가형 + 추가)
입원환자·치매노인 등을 간병하느라 소득활동이 어려운 경우, 과다채무·빚 독촉도 인정.

## 신청
읍면동 행정복지센터 또는 경기도 긴급복지 핫라인 031-120. 퇴원 전 및 퇴원 후 30일 이내.
