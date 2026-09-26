#!/usr/bin/env python3
"""Unit tests for the ISARIC 4C Mortality Score engine and CLI."""

import json
import math
import os
import tempfile
import unittest

from covid_4c_score import FourCMortalityEngine, FourCMortalityResult, ValidationError, main


BASE = dict(
    age_years=55,
    sex="M",
    comorbidities_count=1,
    respiratory_rate=18,
    spo2_percent=96.0,
    gcs_score=15,
    urea_mmol_l=5.0,
    crp_mg_l=20.0,
)


class TestIndividualVariables(unittest.TestCase):
    def test_age_scoring_brackets(self):
        self.assertEqual(FourCMortalityEngine.score_age(45)[0], 0)
        self.assertEqual(FourCMortalityEngine.score_age(50)[0], 2)
        self.assertEqual(FourCMortalityEngine.score_age(59)[0], 2)
        self.assertEqual(FourCMortalityEngine.score_age(60)[0], 4)
        self.assertEqual(FourCMortalityEngine.score_age(69)[0], 4)
        self.assertEqual(FourCMortalityEngine.score_age(70)[0], 6)
        self.assertEqual(FourCMortalityEngine.score_age(79)[0], 6)
        self.assertEqual(FourCMortalityEngine.score_age(80)[0], 7)

    def test_sex_scoring_and_validation(self):
        self.assertEqual(FourCMortalityEngine.score_sex("Female")[0], 0)
        self.assertEqual(FourCMortalityEngine.score_sex("F")[0], 0)
        self.assertEqual(FourCMortalityEngine.score_sex("Male")[0], 1)
        self.assertEqual(FourCMortalityEngine.score_sex("M")[0], 1)
        with self.assertRaises(ValidationError):
            FourCMortalityEngine.score_sex("unknown")

    def test_comorbidities_scoring(self):
        self.assertEqual(FourCMortalityEngine.score_comorbidities(0)[0], 0)
        self.assertEqual(FourCMortalityEngine.score_comorbidities(1)[0], 1)
        self.assertEqual(FourCMortalityEngine.score_comorbidities(2)[0], 2)
        self.assertEqual(FourCMortalityEngine.score_comorbidities(5)[0], 2)

    def test_respiratory_rate_scoring(self):
        self.assertEqual(FourCMortalityEngine.score_respiratory_rate(19)[0], 0)
        self.assertEqual(FourCMortalityEngine.score_respiratory_rate(20)[0], 1)
        self.assertEqual(FourCMortalityEngine.score_respiratory_rate(29)[0], 1)
        self.assertEqual(FourCMortalityEngine.score_respiratory_rate(30)[0], 2)

    def test_oxygen_saturation_scoring(self):
        self.assertEqual(FourCMortalityEngine.score_oxygen_saturation(92.0)[0], 0)
        self.assertEqual(FourCMortalityEngine.score_oxygen_saturation(91.9)[0], 2)

    def test_gcs_scoring(self):
        self.assertEqual(FourCMortalityEngine.score_gcs(15)[0], 0)
        self.assertEqual(FourCMortalityEngine.score_gcs(14)[0], 2)

    def test_urea_and_bun_scoring(self):
        self.assertEqual(FourCMortalityEngine.score_urea(urea_mmol_l=6.9)[0], 0)
        self.assertEqual(FourCMortalityEngine.score_urea(urea_mmol_l=7.0)[0], 1)
        self.assertEqual(FourCMortalityEngine.score_urea(urea_mmol_l=14.0)[0], 1)
        self.assertEqual(FourCMortalityEngine.score_urea(urea_mmol_l=14.1)[0], 3)
        self.assertEqual(FourCMortalityEngine.score_urea(bun_mg_dl=20.0)[0], 1)
        self.assertEqual(FourCMortalityEngine.score_urea(bun_mg_dl=50.0)[0], 3)
        with self.assertRaises(ValidationError):
            FourCMortalityEngine.score_urea()
        with self.assertRaises(ValidationError):
            FourCMortalityEngine.score_urea(urea_mmol_l=8.0, bun_mg_dl=20.0)

    def test_crp_scoring(self):
        self.assertEqual(FourCMortalityEngine.score_crp(49.9)[0], 0)
        self.assertEqual(FourCMortalityEngine.score_crp(50.0)[0], 1)
        self.assertEqual(FourCMortalityEngine.score_crp(99.9)[0], 1)
        self.assertEqual(FourCMortalityEngine.score_crp(100.0)[0], 2)


class TestRiskStratification(unittest.TestCase):
    def test_low_risk_case(self):
        result = FourCMortalityEngine.evaluate(
            age_years=35, sex="F", comorbidities_count=0, respiratory_rate=16,
            spo2_percent=98.0, gcs_score=15, urea_mmol_l=4.5, crp_mg_l=10.0,
        )
        self.assertEqual(result.total_score, 0)
        self.assertEqual(result.risk_group, "Low")
        self.assertEqual(result.mortality_rate_percent, 1.2)

    def test_intermediate_risk_case(self):
        result = FourCMortalityEngine.evaluate(
            age_years=55, sex="M", comorbidities_count=1, respiratory_rate=22,
            spo2_percent=95.0, gcs_score=15, urea_mmol_l=8.0, crp_mg_l=60.0,
        )
        self.assertEqual(result.total_score, 7)
        self.assertEqual(result.risk_group, "Intermediate")
        self.assertEqual(result.mortality_rate_percent, 9.9)

    def test_high_risk_case(self):
        result = FourCMortalityEngine.evaluate(
            age_years=65, sex="M", comorbidities_count=1, respiratory_rate=24,
            spo2_percent=90.0, gcs_score=15, urea_mmol_l=8.0, crp_mg_l=120.0,
        )
        self.assertEqual(result.total_score, 12)
        self.assertEqual(result.risk_group, "High")
        self.assertEqual(result.mortality_rate_percent, 31.4)

    def test_maximum_score(self):
        result = FourCMortalityEngine.evaluate(
            age_years=85, sex="M", comorbidities_count=3, respiratory_rate=35,
            spo2_percent=86.0, gcs_score=12, urea_mmol_l=22.0, crp_mg_l=180.0,
        )
        self.assertEqual(result.total_score, 21)
        self.assertEqual(result.risk_group, "Very High")
        self.assertEqual(result.mortality_rate_percent, 61.5)

    def test_breakdown_sums_to_total(self):
        result = FourCMortalityEngine.evaluate(
            age_years=75, sex="M", comorbidities_count=2, respiratory_rate=30,
            spo2_percent=88.0, gcs_score=13, urea_mmol_l=15.0, crp_mg_l=150.0,
        )
        breakdown = result.score_breakdown
        expected = sum(
            (
                breakdown.age_points,
                breakdown.sex_points,
                breakdown.comorbidities_points,
                breakdown.respiratory_rate_points,
                breakdown.oxygen_saturation_points,
                breakdown.gcs_points,
                breakdown.urea_points,
                breakdown.crp_points,
            )
        )
        self.assertEqual(result.total_score, expected)


class TestInputValidation(unittest.TestCase):
    def test_valid_inputs_accepted(self):
        self.assertIsInstance(FourCMortalityEngine.evaluate(**BASE), FourCMortalityResult)

    def test_under_18_rejected(self):
        with self.assertRaises(ValidationError):
            FourCMortalityEngine.evaluate(**(BASE | {"age_years": 17}))

    def test_invalid_sex_rejected(self):
        with self.assertRaises(ValidationError):
            FourCMortalityEngine.evaluate(**(BASE | {"sex": "X"}))

    def test_missing_or_duplicate_urea_input_rejected(self):
        values = BASE.copy()
        values.pop("urea_mmol_l")
        with self.assertRaises(ValidationError):
            FourCMortalityEngine.evaluate(**values)
        with self.assertRaises(ValidationError):
            FourCMortalityEngine.evaluate(**(BASE | {"bun_mg_dl": 20.0}))

    def test_non_finite_values_rejected(self):
        for field in ("spo2_percent", "urea_mmol_l", "crp_mg_l"):
            for value in (math.nan, math.inf, -math.inf):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValidationError):
                        FourCMortalityEngine.evaluate(**(BASE | {field: value}))

    def test_out_of_range_values_rejected(self):
        cases = {
            "age_years": 151,
            "comorbidities_count": -1,
            "respiratory_rate": 0,
            "spo2_percent": 101.0,
            "gcs_score": 2,
            "urea_mmol_l": -1.0,
            "crp_mg_l": -1.0,
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    FourCMortalityEngine.evaluate(**(BASE | {field: value}))


class TestCLI(unittest.TestCase):
    def test_json_export(self):
        payload = json.loads(FourCMortalityEngine.evaluate(patient_id="PT-999", **BASE).to_json())
        self.assertEqual(payload["patient_id"], "PT-999")
        self.assertIn("interpretation_note", payload)

    def test_cli_eval_command(self):
        args = [
            "eval", "--age", "65", "--sex", "M", "--comorbidities", "1",
            "--rr", "24", "--spo2", "91", "--gcs", "15",
            "--urea", "8.5", "--crp", "45",
        ]
        self.assertEqual(main(args), 0)

    def test_cli_batch_command(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as src:
            src.write("patient_id,age,sex,comorbidities,rr,spo2,gcs,urea,bun,crp\n")
            src.write("PT-T1,65,M,1,22,94.0,15,8.5,,45.0\n")
            src.write("PT-T2,78,F,2,28,89.0,13,12.0,,120.0\n")
            input_path = src.name
        output_path = input_path + ".out.csv"
        try:
            self.assertEqual(main(["batch", "-i", input_path, "-o", output_path]), 0)
            self.assertTrue(os.path.exists(output_path))
        finally:
            os.unlink(input_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_batch_rejects_missing_urea_and_bun(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as src:
            src.write("patient_id,age,sex,comorbidities,rr,spo2,gcs,urea,bun,crp\n")
            src.write("PT-T1,65,M,1,22,94.0,15,,,45.0\n")
            input_path = src.name
        try:
            self.assertEqual(main(["batch", "-i", input_path]), 2)
        finally:
            os.unlink(input_path)


if __name__ == "__main__":
    unittest.main()
