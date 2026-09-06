---
id: catastrophic_medical
name: 재난적 의료비 지원사업
level: national
agency: 국민건강보험공단
contact: nhis_namyangju
departments: [spine, joint, internal, neuro, surgery]
priority: 1
covers_noncovered: true
deadline: {type: after_last_visit, days: 180}
setting: {inpatient: any, outpatient: severe_only}
symbolic:
  hard:
    - {fact: assets, op: lte, ref: catastrophic.asset_cap, fail: "재산 7억 원 초과"}
    - {fact: setting_ok_for_catastrophic, op: eq, value: true, fail: "외래 진료는 중증질환(암·뇌혈관·심장·희귀·중증난치·중증화상)만 대상"}
  band: catastrophic.bands
  amount: catastrophic_amount
excluded_costs: [manual_therapy, single_room, mild_disease]
documents: [receipt, noncovered_itemized, diagnosis_certificate, admission_certificate, id_card, bankbook, private_insurance_statement]
---
# 재난적 의료비 지원사업

**한 줄 요약**: 소득 대비 과도한 의료비를 부담한 가구에 **비급여를 포함한** 본인부담 의료비의 50~80%를 연 최대 5,000만 원까지 지원. 우리 병원 척추 수술 환자에게 가장 자주 해당하는 제도.

## 계산식
지원금 = [ 급여 일부본인부담금 중 본인부담상한제 미지원분 + 전액본인부담금 + 비급여 ] − [ 지원제외항목(도수치료·1인실·경증) + 국가·지자체 지원금 + 실손보험금 등 ] × 소득구간별 지원율

## 소득구간과 신청 가능 기준
| 구간 | 의료비 부담 기준 | 지원율 |
|---|---|---|
| 기초수급자·차상위 | 본인부담 80만 원 초과 | 80% |
| 기준중위소득 50% 이하 | 160만 원 초과(1인 가구 120만 원) | 70% |
| 50~100% | 연소득의 10% 초과 | 60% |
| 100~200% (개별심사) | 연소득의 20% 초과 | 50% |

## 신경-기호 경계 (LLM이 판단해야 하는 것)
- 진료내용 텍스트에서 **외래 중증질환 여부** 판정 (상병코드 없이 서술만 있을 때)
- "경증질환" 제외 여부가 애매한 동반 진료 (예: 고혈압 약 처방이 섞인 입원)
- 개별심사(100~200%) 구간의 신청 가치 — 실익이 있는지 환자에게 설명

## 원무과 액션
1. 비급여 세부내역서를 급여/전액본인부담/비급여/1인실/도수치료 항목으로 구분 발급
2. 퇴원 시 180일 기한을 **문서로** 고지
3. 입원 중 신청 가능함을 안내 (퇴원을 기다릴 필요 없음)

## 출처
정책브리핑(공감) 재난적 의료비 지원사업, 국민건강보험공단. 2026-09 기준. 일부 민간 자료의 구기준(한도 3천만·50% 단일)은 사용하지 않음.
