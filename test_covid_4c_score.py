#!/usr/bin/env python3
"""
Comprehensive Unit Test Suite for ISARIC 4C Mortality Score Engine
Tests individual scoring components for all 8 admission parameters, risk stratification tiers,
BUN to urea conversions, JSON serialization, and CLI execution.
"""

import unittest
from covid_4c_score import (
    FourCMortalityEngine,
    FourCMortalityResult,
    VariableScoreBreakdown,
    main,
)


class TestIndividualVariables(unittest.TestCase):
    """Test suite for isolated parameter scoring logic."""

    def test_age_scoring_brackets(self):
        # <50 -> 0
        self.assertEqual(FourCMortalityEngine.score_age(45)[0], 0)
        # 50-59 -> 2
        self.assertEqual(FourCMortalityEngine.score_age(50)[0], 2)
        self.assertEqual(FourCMortalityEngine.score_age(59)[0], 2)
        # 60-69 -> 4
        self.assertEqual(FourCMortalityEngine.score_age(65)[0], 4)
        # 70-79 -> 6
        self.assertEqual(FourCMortalityEngine.score_age(78)[0], 6)
        # >=80 -> 7
        self.assertEqual(FourCMortalityEngine.score_age(80)[0], 7)
        self.assertEqual(FourCMortalityEngine.score_age(92)[0], 7)

    def test_sex_scoring(self):
        self.assertEqual(FourCMortalityEngine.score_sex("Female")[0], 0)
        self.assertEqual(FourCMortalityEngine.score_sex("F")[0], 0)
        self.assertEqual(FourCMortalityEngine.score_sex("Male")[0], 1)
        self.assertEqual(FourCMortalityEngine.score_sex("M")[0], 1)

    def test_comorbidities_scoring(self):
        self.assertEqual(FourCMortalityEngine.score_comorbidities(0)[0], 0)
        self.assertEqual(FourCMortalityEngine.score_comorbidities(1)[0], 1)
        self.assertEqual(FourCMortalityEngine.score_comorbidities(2)[0], 2)
        self.assertEqual(FourCMortalityEngine.score_comorbidities(5)[0], 2)

    def test_respiratory_rate_scoring(self):
        self.assertEqual(FourCMortalityEngine.score_respiratory_rate(16)[0], 0)
        self.assertEqual(FourCMortalityEngine.score_respiratory_rate(19)[0], 0)
        self.assertEqual(FourCMortalityEngine.score_respiratory_rate(20)[0], 1)
        self.assertEqual(FourCMortalityEngine.score_respiratory_rate(28)[0], 1)
        self.assertEqual(FourCMortalityEngine.score_respiratory_rate(30)[0], 2)
        self.assertEqual(FourCMortalityEngine.score_respiratory_rate(36)[0], 2)

    def test_oxygen_saturation_scoring(self):
        self.assertEqual(FourCMortalityEngine.score_oxygen_saturation(98.0)[0], 0)
        self.assertEqual(FourCMortalityEngine.score_oxygen_saturation(92.0)[0], 0)
        self.assertEqual(FourCMortalityEngine.score_oxygen_saturation(91.9)[0], 2)
        self.assertEqual(FourCMortalityEngine.score_oxygen_saturation(85.0)[0], 2)

    def test_gcs_scoring(self):
        self.assertEqual(FourCMortalityEngine.score_gcs(15)[0], 0)
        self.assertEqual(FourCMortalityEngine.score_gcs(14)[0], 2)
        self.assertEqual(FourCMortalityEngine.score_gcs(8)[0], 2)

    def test_urea_and_bun_scoring(self):
        # Urea <7 -> 0
        self.assertEqual(FourCMortalityEngine.score_urea(urea_mmol_l=5.5)[0], 0)
        # Urea 7-14 -> 1
        self.assertEqual(FourCMortalityEngine.score_urea(urea_mmol_l=10.0)[0], 1)
        # Urea >14 -> 3
        self.assertEqual(FourCMortalityEngine.score_urea(urea_mmol_l=18.0)[0], 3)

        # BUN conversion: BUN 20 mg/dL -> ~7.14 mmol/L -> 1 pt
        self.assertEqual(FourCMortalityEngine.score_urea(bun_mg_dl=20.0)[0], 1)
        # BUN 50 mg/dL -> ~17.85 mmol/L -> 3 pts
        self.assertEqual(FourCMortalityEngine.score_urea(bun_mg_dl=50.0)[0], 3)

    def test_crp_scoring(self):
        self.assertEqual(FourCMortalityEngine.score_crp(25.0)[0], 0)
        self.assertEqual(FourCMortalityEngine.score_crp(50.0)[0], 1)
        self.assertEqual(FourCMortalityEngine.score_crp(85.0)[0], 1)
        self.assertEqual(FourCMortalityEngine.score_crp(100.0)[0], 2)
        self.assertEqual(FourCMortalityEngine.score_crp(250.0)[0], 2)


class TestRiskStratificationTiers(unittest.TestCase):
    """Test suite for total score calculation and mortality risk groups."""

    def test_low_risk_case(self):
        # 35yo female, 0 comorbidities, normal vitals & labs -> 0 points (Low Risk, 1.2% mortality)
        res = FourCMortalityEngine.evaluate(
            age_years=35,
            sex="F",
            comorbidities_count=0,
            respiratory_rate=16,
            spo2_percent=98.0,
            gcs_score=15,
            urea_mmol_l=4.5,
            crp_mg_l=10.0,
        )
        self.assertEqual(res.total_score, 0)
        self.assertEqual(res.risk_group, "Low")
        self.assertEqual(res.mortality_rate_percent, 1.2)
        self.assertEqual(res.recommended_level_of_care, "OUTPATIENT_OR_WARD")

    def test_intermediate_risk_case(self):
        # 55yo (+2) male (+1), 1 comorbidity (+1), RR 22 (+1), SpO2 95% (0), GCS 15 (0), Urea 8 (+1), CRP 60 (+1) -> 7 points
        res = FourCMortalityEngine.evaluate(
            age_years=55,
            sex="M",
            comorbidities_count=1,
            respiratory_rate=22,
            spo2_percent=95.0,
            gcs_score=15,
            urea_mmol_l=8.0,
            crp_mg_l=60.0,
        )
        self.assertEqual(res.total_score, 7)
        self.assertEqual(res.risk_group, "Intermediate")
        self.assertEqual(res.mortality_rate_percent, 9.9)
        self.assertEqual(res.recommended_level_of_care, "INPATIENT_WARD")

    def test_high_risk_case(self):
        # 72yo (+6) male (+1), 2 comorb (+2), RR 24 (+1), SpO2 90% (+2), GCS 15 (0), Urea 10 (+1), CRP 120 (+2) -> 15? Wait: 6+1+2+1+2+0+1+2 = 15 (Very High)
        # Let's adjust to 12 pts (High Risk):
        # 65yo (+4) male (+1), 1 comorb (+1), RR 24 (+1), SpO2 90% (+2), GCS 15 (0), Urea 8 (+1), CRP 120 (+2) -> 12 points
        res = FourCMortalityEngine.evaluate(
            age_years=65,
            sex="M",
            comorbidities_count=1,
            respiratory_rate=24,
            spo2_percent=90.0,
            gcs_score=15,
            urea_mmol_l=8.0,
            crp_mg_l=120.0,
        )
        self.assertEqual(res.total_score, 12)
        self.assertEqual(res.risk_group, "High")
        self.assertEqual(res.mortality_rate_percent, 31.4)
        self.assertEqual(res.recommended_level_of_care, "HIGH_ACUITY_STEPDOWN")

    def test_maximum_score_very_high_risk(self):
        # 85yo (+7) male (+1), >=2 comorb (+2), RR 35 (+2), SpO2 86% (+2), GCS 12 (+2), Urea 22 (+3), CRP 180 (+2) -> 21 points
        res = FourCMortalityEngine.evaluate(
            age_years=85,
            sex="M",
            comorbidities_count=3,
            respiratory_rate=35,
            spo2_percent=86.0,
            gcs_score=12,
            urea_mmol_l=22.0,
            crp_mg_l=180.0,
        )
        self.assertEqual(res.total_score, 21)
        self.assertEqual(res.risk_group, "Very High")
        self.assertEqual(res.mortality_rate_percent, 61.5)
        self.assertEqual(res.recommended_level_of_care, "ICU_CRITICAL_CARE")


class TestEndToEndAndCLI(unittest.TestCase):
    """Test suite for full report generation, JSON output, and CLI."""

    def test_json_export(self):
        res = FourCMortalityEngine.evaluate(patient_id="PT-999", age_years=62, sex="M")
        json_str = res.to_json()
        self.assertIn("PT-999", json_str)
        self.assertIn("total_score", json_str)

    def test_cli_eval_command(self):
        self.assertEqual(main(["eval", "--age", "65", "--sex", "M", "--rr", "24", "--spo2", "91"]), 0)
        self.assertEqual(main(["eval", "--age", "82", "--sex", "F", "--json"]), 0)

    def test_cli_chat_command(self):
        self.assertEqual(main(["chat", "What", "are", "the", "variables?"]), 0)


if __name__ == "__main__":
    unittest.main()
