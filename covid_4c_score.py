#!/usr/bin/env python3
"""
ISARIC 4C Mortality Score for COVID-19 Inpatient Severity & Mortality Prognostication
-------------------------------------------------------------------------------------
Calculates the validated ISARIC 4C Mortality Score (0-21 points) from 8 clinical
variables at hospital admission to predict in-hospital mortality risk in COVID-19 patients.

Reference: Knight SR et al. BMJ 2020; 370:m3339 (ISARIC 4C Prospective Cohort, n=35,463)
Domain: Infectious Diseases / Critical Care / Pulmonology
"""

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple


@dataclass
class VariableScoreBreakdown:
    """Breakdown of points awarded for each of the 8 variables."""
    age_points: int
    sex_points: int
    comorbidities_points: int
    respiratory_rate_points: int
    oxygen_saturation_points: int
    gcs_points: int
    urea_points: int
    crp_points: int


@dataclass
class FourCMortalityResult:
    """Complete 4C Mortality Score evaluation."""
    patient_id: str
    total_score: int  # 0 to 21
    risk_group: str  # 'Low', 'Intermediate', 'High', 'Very High'
    mortality_rate_percent: float
    mortality_confidence_interval: str
    clinical_recommendation: str
    recommended_level_of_care: str  # 'OUTPATIENT_OR_WARD', 'INPATIENT_WARD', 'HIGH_ACUITY_STEPDOWN', 'ICU_CRITICAL_CARE'
    score_breakdown: VariableScoreBreakdown
    risk_factors: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class ValidationError(Exception):
    """Raised when input parameters are outside clinically valid ranges."""
    pass


def _validate_inputs(
    age_years: int,
    sex: str,
    comorbidities_count: int,
    respiratory_rate: int,
    spo2_percent: float,
    gcs_score: int,
    urea_mmol_l: Optional[float],
    bun_mg_dl: Optional[float],
    crp_mg_l: float,
) -> None:
    """Validate all input parameters are within clinically plausible ranges."""
    if not isinstance(age_years, int) or age_years < 0 or age_years > 150:
        raise ValidationError(f"Age must be an integer between 0 and 150, got {age_years}")
    if not isinstance(comorbidities_count, int) or comorbidities_count < 0:
        raise ValidationError(f"Comorbidities count must be a non-negative integer, got {comorbidities_count}")
    if not isinstance(respiratory_rate, int) or respiratory_rate < 0 or respiratory_rate > 100:
        raise ValidationError(f"Respiratory rate must be between 0 and 100, got {respiratory_rate}")
    if not isinstance(spo2_percent, (int, float)) or spo2_percent < 0 or spo2_percent > 100:
        raise ValidationError(f"SpO2 must be between 0 and 100, got {spo2_percent}")
    if not isinstance(gcs_score, int) or gcs_score < 3 or gcs_score > 15:
        raise ValidationError(f"GCS must be between 3 and 15, got {gcs_score}")
    if urea_mmol_l is not None and (not isinstance(urea_mmol_l, (int, float)) or urea_mmol_l < 0):
        raise ValidationError(f"Urea must be a non-negative number, got {urea_mmol_l}")
    if bun_mg_dl is not None and (not isinstance(bun_mg_dl, (int, float)) or bun_mg_dl < 0):
        raise ValidationError(f"BUN must be a non-negative number, got {bun_mg_dl}")
    if not isinstance(crp_mg_l, (int, float)) or crp_mg_l < 0:
        raise ValidationError(f"CRP must be a non-negative number, got {crp_mg_l}")
    if sex is None or str(sex).strip() == "":
        raise ValidationError("Sex must be specified (M/F/Male/Female)")


class FourCMortalityEngine:
    """Computational engine for ISARIC 4C Mortality Score."""

    @staticmethod
    def score_age(age_years: int) -> Tuple[int, Optional[str]]:
        """Age points: <50 (0), 50-59 (2), 60-69 (4), 70-79 (6), >=80 (7)."""
        if age_years < 50:
            return 0, None
        elif age_years <= 59:
            return 2, f"Age {age_years} (50-59 years, +2 pts)"
        elif age_years <= 69:
            return 4, f"Age {age_years} (60-69 years, +4 pts)"
        elif age_years <= 79:
            return 6, f"Age {age_years} (70-79 years, +6 pts)"
        else:
            return 7, f"Age {age_years} (>=80 years, +7 pts)"

    @staticmethod
    def score_sex(sex: str) -> Tuple[int, Optional[str]]:
        """Sex assigned at birth: Female (0), Male (1)."""
        s = str(sex).strip().upper()
        if s.startswith("M"):
            return 1, "Male sex (+1 pt)"
        return 0, None

    @staticmethod
    def score_comorbidities(comorbidities_count: int) -> Tuple[int, Optional[str]]:
        """Comorbidities: 0 (0), 1 (1), >=2 (2)."""
        if comorbidities_count <= 0:
            return 0, None
        elif comorbidities_count == 1:
            return 1, "1 Comorbidity present (+1 pt)"
        else:
            return 2, f"{comorbidities_count} Comorbidities present (+2 pts)"

    @staticmethod
    def score_respiratory_rate(rr_breaths_per_min: int) -> Tuple[int, Optional[str]]:
        """Respiratory rate: <20 (0), 20-29 (1), >=30 (2)."""
        if rr_breaths_per_min < 20:
            return 0, None
        elif rr_breaths_per_min <= 29:
            return 1, f"Tachypnea RR {rr_breaths_per_min}/min (20-29, +1 pt)"
        else:
            return 2, f"Severe Tachypnea RR {rr_breaths_per_min}/min (>=30, +2 pts)"

    @staticmethod
    def score_oxygen_saturation(spo2_percent: float) -> Tuple[int, Optional[str]]:
        """SpO2 on room air: >=92% (0), <92% (2)."""
        if spo2_percent < 92.0:
            return 2, f"Hypoxemia on room air (SpO2 {spo2_percent:.1f}% < 92%, +2 pts)"
        return 0, None

    @staticmethod
    def score_gcs(gcs_score: int) -> Tuple[int, Optional[str]]:
        """Glasgow Coma Scale: 15 (0), <15 (2)."""
        if gcs_score < 15:
            return 2, f"Altered mental status / GCS {gcs_score} < 15 (+2 pts)"
        return 0, None

    @staticmethod
    def score_urea(urea_mmol_l: Optional[float] = None, bun_mg_dl: Optional[float] = None) -> Tuple[int, Optional[str]]:
        """
        Urea points: <7 mmol/L (0), 7-14 mmol/L (1), >14 mmol/L (3).
        Conversion: BUN (mg/dL) / 2.8 = Urea (mmol/L).
        """
        if urea_mmol_l is None and bun_mg_dl is not None:
            urea_val = bun_mg_dl / 2.801
        elif urea_mmol_l is not None:
            urea_val = urea_mmol_l
        else:
            urea_val = 5.0  # nominal default

        if urea_val < 7.0:
            return 0, None
        elif urea_val <= 14.0:
            return 1, f"Elevated blood urea ({urea_val:.1f} mmol/L [7-14], +1 pt)"
        else:
            return 3, f"Markedly elevated blood urea ({urea_val:.1f} mmol/L > 14, +3 pts)"

    @staticmethod
    def score_crp(crp_mg_l: float) -> Tuple[int, Optional[str]]:
        """CRP points: <50 mg/L (0), 50-99 mg/L (1), >=100 mg/L (2)."""
        if crp_mg_l < 50.0:
            return 0, None
        elif crp_mg_l <= 99.0:
            return 1, f"Elevated CRP ({crp_mg_l:.1f} mg/L [50-99], +1 pt)"
        else:
            return 2, f"Markedly elevated CRP ({crp_mg_l:.1f} mg/L >= 100, +2 pts)"

    @classmethod
    def evaluate(
        cls,
        patient_id: str = "PT-001",
        age_years: int = 55,
        sex: str = "M",
        comorbidities_count: int = 0,
        respiratory_rate: int = 18,
        spo2_percent: float = 96.0,
        gcs_score: int = 15,
        urea_mmol_l: Optional[float] = None,
        bun_mg_dl: Optional[float] = None,
        crp_mg_l: float = 20.0,
    ) -> FourCMortalityResult:
        """Evaluate full ISARIC 4C Mortality Score."""
        _validate_inputs(
            age_years=age_years,
            sex=sex,
            comorbidities_count=comorbidities_count,
            respiratory_rate=respiratory_rate,
            spo2_percent=spo2_percent,
            gcs_score=gcs_score,
            urea_mmol_l=urea_mmol_l,
            bun_mg_dl=bun_mg_dl,
            crp_mg_l=crp_mg_l,
        )
        factors = []

        pts_age, desc = cls.score_age(age_years)
        if desc: factors.append(desc)

        pts_sex, desc = cls.score_sex(sex)
        if desc: factors.append(desc)

        pts_comorb, desc = cls.score_comorbidities(comorbidities_count)
        if desc: factors.append(desc)

        pts_rr, desc = cls.score_respiratory_rate(respiratory_rate)
        if desc: factors.append(desc)

        pts_spo2, desc = cls.score_oxygen_saturation(spo2_percent)
        if desc: factors.append(desc)

        pts_gcs, desc = cls.score_gcs(gcs_score)
        if desc: factors.append(desc)

        pts_urea, desc = cls.score_urea(urea_mmol_l=urea_mmol_l, bun_mg_dl=bun_mg_dl)
        if desc: factors.append(desc)

        pts_crp, desc = cls.score_crp(crp_mg_l)
        if desc: factors.append(desc)

        total_score = (
            pts_age + pts_sex + pts_comorb + pts_rr + pts_spo2 + pts_gcs + pts_urea + pts_crp
        )

        # Risk Stratification based on BMJ 2020 validation data (35,463 patients)
        if total_score <= 3:
            risk_group = "Low"
            mortality = 1.2
            ci = "0.9% - 1.5%"
            care_level = "OUTPATIENT_OR_WARD"
            rec = "Low risk of in-hospital death. Suitable for outpatient management or general ward with pulse oximetry."
        elif total_score <= 8:
            risk_group = "Intermediate"
            mortality = 9.9
            ci = "9.2% - 10.6%"
            care_level = "INPATIENT_WARD"
            rec = "Intermediate risk. Inpatient hospital admission indicated. Monitor serial vitals and consider early pharmacological therapeutics."
        elif total_score <= 14:
            risk_group = "High"
            mortality = 31.4
            ci = "30.7% - 32.2%"
            care_level = "HIGH_ACUITY_STEPDOWN"
            rec = "High mortality risk. Prompt multidisciplinary escalation: systemic corticosteroids, antiviral/immunomodulatory therapy, and high-flow oxygen."
        else:
            risk_group = "Very High"
            mortality = 61.5
            ci = "60.0% - 63.0%"
            care_level = "ICU_CRITICAL_CARE"
            rec = "Very high mortality risk. Urgent ICU / Critical Care consultation. Assess for non-invasive/invasive mechanical ventilation and goals of care."

        breakdown = VariableScoreBreakdown(
            age_points=pts_age,
            sex_points=pts_sex,
            comorbidities_points=pts_comorb,
            respiratory_rate_points=pts_rr,
            oxygen_saturation_points=pts_spo2,
            gcs_points=pts_gcs,
            urea_points=pts_urea,
            crp_points=pts_crp,
        )

        return FourCMortalityResult(
            patient_id=patient_id,
            total_score=total_score,
            risk_group=risk_group,
            mortality_rate_percent=mortality,
            mortality_confidence_interval=ci,
            clinical_recommendation=rec,
            recommended_level_of_care=care_level,
            score_breakdown=breakdown,
            risk_factors=factors,
        )


# ==============================================================================
# CLI & BATCH PROCESSING
# ==============================================================================

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="covid19-4c-mortality-score",
        description="ISARIC 4C Mortality Score for Hospitalized COVID-19 Patients"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Eval
    p_eval = subparsers.add_parser("eval", help="Evaluate 4C score for a patient")
    p_eval.add_argument("--patient-id", default="PT-2026-001")
    p_eval.add_argument("--age", type=int, required=True, help="Age in years")
    p_eval.add_argument("--sex", choices=["M", "F", "Male", "Female"], default="M")
    p_eval.add_argument("--comorbidities", type=int, default=0, help="Number of major comorbidities (0, 1, 2+)")
    p_eval.add_argument("--rr", type=int, default=18, help="Respiratory Rate (breaths/min)")
    p_eval.add_argument("--spo2", type=float, default=95.0, help="Room air SpO2 (%)")
    p_eval.add_argument("--gcs", type=int, default=15, help="Glasgow Coma Scale (3-15)")
    p_eval.add_argument("--urea", type=float, default=None, help="Serum Urea (mmol/L)")
    p_eval.add_argument("--bun", type=float, default=None, help="Blood Urea Nitrogen BUN (mg/dL)")
    p_eval.add_argument("--crp", type=float, default=25.0, help="C-Reactive Protein (mg/L)")
    p_eval.add_argument("--json", action="store_true", help="Output JSON format")

    # Chat
    p_chat = subparsers.add_parser("chat", help="Ask clinical questions regarding 4C score")
    p_chat.add_argument("query", nargs="+")

    # Batch
    p_batch = subparsers.add_parser("batch", help="Batch evaluate CSV file")
    p_batch.add_argument("-i", "--input", required=True)
    p_batch.add_argument("-o", "--output", default="4c_results.csv")

    args = parser.parse_args(argv)

    if args.command == "eval":
        res = FourCMortalityEngine.evaluate(
            patient_id=args.patient_id,
            age_years=args.age,
            sex=args.sex,
            comorbidities_count=args.comorbidities,
            respiratory_rate=args.rr,
            spo2_percent=args.spo2,
            gcs_score=args.gcs,
            urea_mmol_l=args.urea,
            bun_mg_dl=args.bun,
            crp_mg_l=args.crp,
        )
        if args.json:
            print(res.to_json())
        else:
            print("=" * 80)
            print(f"  ISARIC 4C MORTALITY SCORE REPORT — {res.patient_id}")
            print("=" * 80)
            print(f"  Total Score:      {res.total_score} / 21")
            print(f"  Risk Category:    [{res.risk_group.upper()}] Risk")
            print(f"  Predicted In-Hospital Mortality: {res.mortality_rate_percent:.1f}% ({res.mortality_confidence_interval})")
            print(f"  Recommended Care: {res.recommended_level_of_care}")
            print("-" * 80)
            print("  Score Breakdown:")
            bd = res.score_breakdown
            print(f"    * Age: {bd.age_points} pts | Sex: {bd.sex_points} pts | Comorbidities: {bd.comorbidities_points} pts")
            print(f"    * RR: {bd.respiratory_rate_points} pts | SpO2: {bd.oxygen_saturation_points} pts | GCS: {bd.gcs_points} pts")
            print(f"    * Urea: {bd.urea_points} pts | CRP: {bd.crp_points} pts")
            print("-" * 80)
            print(f"  Clinical Action: {res.clinical_recommendation}")
            print("=" * 80)
        return 0

    elif args.command == "chat":
        q = " ".join(args.query).lower()
        if "variable" in q or "criteria" in q:
            print("ISARIC 4C includes 8 variables: Age, Sex, Comorbidities, Respiratory Rate, SpO2, GCS, Urea, and CRP.")
        elif "mortality" in q or "risk" in q:
            print("Tiers: Low (0-3, 1.2%), Intermediate (4-8, 9.9%), High (9-14, 31.4%), Very High (15-21, 61.5%).")
        else:
            print("ISARIC 4C Mortality Engine active. Validated across 35,000+ hospitalized COVID-19 patients.")
        return 0

    elif args.command == "batch":
        with open(args.input, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        out_rows = []
        for r in rows:
            pid = r.get("patient_id", "PT-000")
            age = int(r.get("age", r.get("age_years", 60)))
            sex = r.get("sex", "M")
            comorb = int(r.get("comorbidities", r.get("comorbidities_count", 0)))
            rr = int(r.get("rr", r.get("respiratory_rate", 20)))
            spo2 = float(r.get("spo2", r.get("spo2_percent", 95.0)))
            gcs = int(r.get("gcs", 15))
            urea = float(r["urea"]) if "urea" in r and r["urea"] else None
            bun = float(r["bun"]) if "bun" in r and r["bun"] else None
            crp = float(r.get("crp", r.get("crp_mg_l", 20.0)))

            eval_res = FourCMortalityEngine.evaluate(
                patient_id=pid,
                age_years=age,
                sex=sex,
                comorbidities_count=comorb,
                respiratory_rate=rr,
                spo2_percent=spo2,
                gcs_score=gcs,
                urea_mmol_l=urea,
                bun_mg_dl=bun,
                crp_mg_l=crp,
            )
            out_rows.append({
                **r,
                "four_c_score": eval_res.total_score,
                "risk_group": eval_res.risk_group,
                "mortality_percent": eval_res.mortality_rate_percent,
                "recommended_care": eval_res.recommended_level_of_care,
            })
        if out_rows:
            with open(args.output, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
                writer.writeheader()
                writer.writerows(out_rows)
        print(f"Batch processed {len(out_rows)} rows -> {args.output}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
