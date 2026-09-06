---
id: rare_disease_aid
name: 희귀질환자 의료비 지원
level: national_local
agency: 남양주시 보건소 → 공단 지급
contact: namyangju_health_center
departments: [internal, neuro, spine]
priority: 2
covers_noncovered: false
deadline: {type: annual}
symbolic:
  hard:
    - {fact: special_category, op: eq, value: rare, fail: "희귀질환 산정특례 대상 아님"}
    - {fact: income_pct, op: lte, ref: rare_disease_aid.income_pct_max, fail: "기준중위소득 140% 초과"}
  amount: rare_disease_amount
documents: [special_disease_registration_form, diagnosis_certificate, id_card, bankbook]
---
# 희귀질환자 의료비 지원

산정특례(희귀질환) 등록 후 소득·재산 기준(2026 희귀질환 기준 중위 140%: 1인 359만·4인 909만 원) 충족 시 급여 본인부담금 등 지원. **2026년부터 부양의무자 소득기준 폐지.** 절차: 산정특례 등록(병원) → 의료비 지원 신청(보건소) → 소득·재산 조사 → 공단 지급.
