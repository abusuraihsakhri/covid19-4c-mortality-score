#!/usr/bin/env python3
"""ISARIC 4C Mortality Score calculator.

Implements the point score described by Knight SR et al., BMJ 2020;370:m3339
for adults admitted to hospital with COVID-19. The score is prognostic support,
not a standalone treatment or disposition rule.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

REFERENCE = "Knight SR et al. BMJ 2020;370:m3339. doi:10.1136/bmj.m3339"
VALID_SEX_VALUES = {"M": "M", "MALE": "M", "F": "F", "FEMALE": "F"}


@dataclass
class VariableScoreBreakdown:
    """Points awarded for each of the eight 4C variables."""

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
    total_score: int
    risk_group: str
    mortality_rate_percent: float
    mortality_confidence_interval: str
    clinical_recommendation: str
    recommended_level_of_care: str
    score_breakdown: VariableScoreBreakdown
    risk_factors: List[str]
    interpretation_note: str = (
        "Validation-cohort mortality rates are historical 2020 estimates for adults "
        "admitted to hospital with COVID-19. Do not use this score alone to determine "
        "treatment, escalation, or disposition."
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class ValidationError(ValueError):
    """Raised when input parameters are invalid for the 4C score."""


def _is_finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _normalize_sex(sex: str) -> str:
    key = str(sex).strip().upper()
    try:
        return VALID_SEX_VALUES[key]
    except KeyError as exc:
        raise ValidationError("Sex must be one of M, F, Male, or Female") from exc


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
    """Validate inputs against the score's population and safe numeric bounds."""

    if not _is_int(age_years) or age_years < 18 or age_years > 150:
        raise ValidationError(
            f"Age must be an integer from 18 to 150 years; the 4C score was validated in adults, got {age_years!r}"
        )
    _normalize_sex(sex)
    if not _is_int(comorbidities_count) or comorbidities_count < 0:
        raise ValidationError(
            f"Comorbidities count must be a non-negative integer, got {comorbidities_count!r}"
        )
    if not _is_int(respiratory_rate) or respiratory_rate < 1 or respiratory_rate > 100:
        raise ValidationError(
            f"Respiratory rate must be an integer from 1 to 100 breaths/min, got {respiratory_rate!r}"
        )
    if not _is_finite_number(spo2_percent) or not 0 < float(spo2_percent) <= 100:
        raise ValidationError(f"SpO2 must be a finite number >0 and <=100, got {spo2_percent!r}")
    if not _is_int(gcs_score) or not 3 <= gcs_score <= 15:
        raise ValidationError(f"GCS must be an integer from 3 to 15, got {gcs_score!r}")

    if (urea_mmol_l is None) == (bun_mg_dl is None):
        raise ValidationError("Provide exactly one of urea_mmol_l or bun_mg_dl")
    if urea_mmol_l is not None and (
        not _is_finite_number(urea_mmol_l) or float(urea_mmol_l) < 0
    ):
        raise ValidationError(f"Urea must be a finite non-negative number, got {urea_mmol_l!r}")
    if bun_mg_dl is not None and (
        not _is_finite_number(bun_mg_dl) or float(bun_mg_dl) < 0
    ):
        raise ValidationError(f"BUN must be a finite non-negative number, got {bun_mg_dl!r}")
    if not _is_finite_number(crp_mg_l) or float(crp_mg_l) < 0:
        raise ValidationError(f"CRP must be a finite non-negative number, got {crp_mg_l!r}")


class FourCMortalityEngine:
    """Computational engine for the ISARIC 4C Mortality Score."""

    @staticmethod
    def score_age(age_years: int) -> Tuple[int, Optional[str]]:
        """Age points: <50 (0), 50-59 (2), 60-69 (4), 70-79 (6), >=80 (7)."""
        if age_years < 50:
            return 0, None
        if age_years <= 59:
            return 2, f"Age {age_years} (50-59 years, +2 pts)"
        if age_years <= 69:
            return 4, f"Age {age_years} (60-69 years, +4 pts)"
        if age_years <= 79:
            return 6, f"Age {age_years} (70-79 years, +6 pts)"
        return 7, f"Age {age_years} (>=80 years, +7 pts)"

    @staticmethod
    def score_sex(sex: str) -> Tuple[int, Optional[str]]:
        """Sex points in the original score: female (0), male (1)."""
        normalized = _normalize_sex(sex)
        if normalized == "M":
            return 1, "Male sex (+1 pt)"
        return 0, None

    @staticmethod
    def score_comorbidities(comorbidities_count: int) -> Tuple[int, Optional[str]]:
        """Comorbidities: 0 (0), 1 (1), >=2 (2)."""
        if comorbidities_count <= 0:
            return 0, None
        if comorbidities_count == 1:
            return 1, "1 comorbidity present (+1 pt)"
        return 2, f"{comorbidities_count} comorbidities present (+2 pts)"

    @staticmethod
    def score_respiratory_rate(rr_breaths_per_min: int) -> Tuple[int, Optional[str]]:
        """Respiratory rate: <20 (0), 20-29 (1), >=30 (2)."""
        if rr_breaths_per_min < 20:
            return 0, None
        if rr_breaths_per_min <= 29:
            return 1, f"Respiratory rate {rr_breaths_per_min}/min (20-29, +1 pt)"
        return 2, f"Respiratory rate {rr_breaths_per_min}/min (>=30, +2 pts)"

    @staticmethod
    def score_oxygen_saturation(spo2_percent: float) -> Tuple[int, Optional[str]]:
        """Room-air SpO2: >=92% (0), <92% (2)."""
        if spo2_percent < 92.0:
            return 2, f"Room-air SpO2 {spo2_percent:.1f}% (<92%, +2 pts)"
        return 0, None

    @staticmethod
    def score_gcs(gcs_score: int) -> Tuple[int, Optional[str]]:
        """Glasgow Coma Scale: 15 (0), <15 (2)."""
        if gcs_score < 15:
            return 2, f"GCS {gcs_score} (<15, +2 pts)"
        return 0, None

    @staticmethod
    def score_urea(
        urea_mmol_l: Optional[float] = None,
        bun_mg_dl: Optional[float] = None,
    ) -> Tuple[int, Optional[str]]:
        """Urea: <7 (0), 7-14 (1), >14 mmol/L (3).

        BUN is accepted as a convenience input and converted with BUN/2.801.
        Exactly one of urea or BUN must be supplied.
        """
        if (urea_mmol_l is None) == (bun_mg_dl is None):
            raise ValidationError("Provide exactly one of urea_mmol_l or bun_mg_dl")
        if urea_mmol_l is not None:
            urea_val = float(urea_mmol_l)
        else:
            urea_val = float(bun_mg_dl) / 2.801

        if urea_val < 7.0:
            return 0, None
        if urea_val <= 14.0:
            return 1, f"Blood urea {urea_val:.1f} mmol/L (7-14, +1 pt)"
        return 3, f"Blood urea {urea_val:.1f} mmol/L (>14, +3 pts)"

    @staticmethod
    def score_crp(crp_mg_l: float) -> Tuple[int, Optional[str]]:
        """CRP: <50 (0), 50-99 (1), >=100 mg/L (2)."""
        if crp_mg_l < 50.0:
            return 0, None
        if crp_mg_l < 100.0:
            return 1, f"CRP {crp_mg_l:.1f} mg/L (50-99, +1 pt)"
        return 2, f"CRP {crp_mg_l:.1f} mg/L (>=100, +2 pts)"

    @classmethod
    def evaluate(
        cls,
        patient_id: str = "PT-001",
        *,
        age_years: int,
        sex: str,
        comorbidities_count: int,
        respiratory_rate: int,
        spo2_percent: float,
        gcs_score: int,
        crp_mg_l: float,
        urea_mmol_l: Optional[float] = None,
        bun_mg_dl: Optional[float] = None,
    ) -> FourCMortalityResult:
        """Evaluate the complete ISARIC 4C Mortality Score."""
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

        factors: List[str] = []
        pts_age, desc = cls.score_age(age_years)
        if desc:
            factors.append(desc)
        pts_sex, desc = cls.score_sex(sex)
        if desc:
            factors.append(desc)
        pts_comorb, desc = cls.score_comorbidities(comorbidities_count)
        if desc:
            factors.append(desc)
        pts_rr, desc = cls.score_respiratory_rate(respiratory_rate)
        if desc:
            factors.append(desc)
        pts_spo2, desc = cls.score_oxygen_saturation(spo2_percent)
        if desc:
            factors.append(desc)
        pts_gcs, desc = cls.score_gcs(gcs_score)
        if desc:
            factors.append(desc)
        pts_urea, desc = cls.score_urea(urea_mmol_l=urea_mmol_l, bun_mg_dl=bun_mg_dl)
        if desc:
            factors.append(desc)
        pts_crp, desc = cls.score_crp(crp_mg_l)
        if desc:
            factors.append(desc)

        total_score = sum(
            (pts_age, pts_sex, pts_comorb, pts_rr, pts_spo2, pts_gcs, pts_urea, pts_crp)
        )

        if total_score <= 3:
            risk_group = "Low"
            mortality = 1.2
            care_level = "OUTPATIENT_OR_WARD"
        elif total_score <= 8:
            risk_group = "Intermediate"
            mortality = 9.9
            care_level = "INPATIENT_WARD"
        elif total_score <= 14:
            risk_group = "High"
            mortality = 31.4
            care_level = "HIGH_ACUITY_STEPDOWN"
        else:
            risk_group = "Very High"
            mortality = 61.5
            care_level = "ICU_CRITICAL_CARE"

        recommendation = (
            f"{risk_group} 4C risk stratum in the 2020 validation cohort. "
            "Interpret with current clinical guidance and the complete patient context; "
            "the score is not a standalone treatment, escalation, or disposition rule."
        )

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
            patient_id=str(patient_id),
            total_score=total_score,
            risk_group=risk_group,
            mortality_rate_percent=mortality,
            mortality_confidence_interval="Not supplied by this implementation",
            clinical_recommendation=recommendation,
            recommended_level_of_care=care_level,
            score_breakdown=breakdown,
            risk_factors=factors,
        )


def _required_cell(row: Dict[str, str], row_number: int, *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    raise ValidationError(f"Row {row_number}: missing required value for {'/'.join(names)}")


def _parse_batch_row(row: Dict[str, str], row_number: int) -> FourCMortalityResult:
    urea_raw = row.get("urea") or row.get("urea_mmol_l")
    bun_raw = row.get("bun") or row.get("bun_mg_dl")
    if bool(urea_raw and str(urea_raw).strip()) == bool(bun_raw and str(bun_raw).strip()):
        raise ValidationError(f"Row {row_number}: provide exactly one of urea or bun")

    return FourCMortalityEngine.evaluate(
        patient_id=row.get("patient_id", "") or f"ROW-{row_number}",
        age_years=int(_required_cell(row, row_number, "age", "age_years")),
        sex=_required_cell(row, row_number, "sex"),
        comorbidities_count=int(
            _required_cell(row, row_number, "comorbidities", "comorbidities_count")
        ),
        respiratory_rate=int(_required_cell(row, row_number, "rr", "respiratory_rate")),
        spo2_percent=float(_required_cell(row, row_number, "spo2", "spo2_percent")),
        gcs_score=int(_required_cell(row, row_number, "gcs", "gcs_score")),
        crp_mg_l=float(_required_cell(row, row_number, "crp", "crp_mg_l")),
        urea_mmol_l=float(str(urea_raw).strip()) if urea_raw and str(urea_raw).strip() else None,
        bun_mg_dl=float(str(bun_raw).strip()) if bun_raw and str(bun_raw).strip() else None,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="covid19-4c-mortality-score",
        description="ISARIC 4C Mortality Score for adults admitted with COVID-19",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_eval = subparsers.add_parser("eval", help="Evaluate a complete 4C score")
    p_eval.add_argument("--patient-id", default="PT-001")
    p_eval.add_argument("--age", type=int, required=True, help="Age in years (>=18)")
    p_eval.add_argument("--sex", choices=["M", "F", "Male", "Female"], required=True)
    p_eval.add_argument("--comorbidities", type=int, required=True)
    p_eval.add_argument("--rr", type=int, required=True, help="Respiratory rate (breaths/min)")
    p_eval.add_argument("--spo2", type=float, required=True, help="Room-air SpO2 (%)")
    p_eval.add_argument("--gcs", type=int, required=True, help="Glasgow Coma Scale (3-15)")
    urea_group = p_eval.add_mutually_exclusive_group(required=True)
    urea_group.add_argument("--urea", type=float, help="Serum urea (mmol/L)")
    urea_group.add_argument("--bun", type=float, help="Blood urea nitrogen (mg/dL)")
    p_eval.add_argument("--crp", type=float, required=True, help="C-reactive protein (mg/L)")
    p_eval.add_argument("--json", action="store_true", help="Output JSON")

    p_chat = subparsers.add_parser("chat", help="Show static information about the score")
    p_chat.add_argument("query", nargs="+")

    p_batch = subparsers.add_parser("batch", help="Batch evaluate a CSV file")
    p_batch.add_argument("-i", "--input", required=True)
    p_batch.add_argument("-o", "--output", default="4c_results.csv")

    args = parser.parse_args(argv)

    if args.command == "eval":
        try:
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
        except ValidationError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

        if args.json:
            print(res.to_json())
        else:
            print("=" * 80)
            print(f"  ISARIC 4C MORTALITY SCORE — {res.patient_id}")
            print("=" * 80)
            print(f"  Total Score: {res.total_score} / 21")
            print(f"  Risk Group: {res.risk_group}")
            print(f"  2020 Validation-Cohort Mortality: {res.mortality_rate_percent:.1f}%")
            print(f"  Study-era Management Stratum: {res.recommended_level_of_care}")
            bd = res.score_breakdown
            print("-" * 80)
            print(
                "  Breakdown: "
                f"age {bd.age_points}, sex {bd.sex_points}, comorbidities {bd.comorbidities_points}, "
                f"RR {bd.respiratory_rate_points}, SpO2 {bd.oxygen_saturation_points}, "
                f"GCS {bd.gcs_points}, urea {bd.urea_points}, CRP {bd.crp_points}"
            )
            print("-" * 80)
            print(f"  Interpretation: {res.clinical_recommendation}")
            print(f"  Reference: {REFERENCE}")
            print("=" * 80)
        return 0

    if args.command == "chat":
        q = " ".join(args.query).lower()
        if "variable" in q or "criteria" in q:
            print(
                "The 4C score uses age, sex, comorbidity count, respiratory rate, room-air SpO2, "
                "GCS, urea, and CRP."
            )
        elif "mortality" in q or "risk" in q:
            print(
                "2020 validation strata: Low 0-3 (1.2%), Intermediate 4-8 (9.9%), "
                "High 9-14 (31.4%), Very High >=15 (61.5%)."
            )
        else:
            print(
                "The ISARIC 4C Mortality Score was validated in adults admitted to hospital with "
                "COVID-19. It is prognostic support, not a standalone treatment rule."
            )
        return 0

    if args.command == "batch":
        try:
            with open(args.input, mode="r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames:
                    raise ValidationError("Input CSV has no header row")
                rows = list(reader)

            out_rows = []
            for row_number, row in enumerate(rows, start=2):
                result = _parse_batch_row(row, row_number)
                out_rows.append(
                    {
                        **row,
                        "four_c_score": result.total_score,
                        "risk_group": result.risk_group,
                        "mortality_percent": result.mortality_rate_percent,
                        "recommended_care": result.recommended_level_of_care,
                    }
                )

            output_fields = list(reader.fieldnames)
            for field_name in (
                "four_c_score",
                "risk_group",
                "mortality_percent",
                "recommended_care",
            ):
                if field_name not in output_fields:
                    output_fields.append(field_name)

            with open(args.output, mode="w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=output_fields)
                writer.writeheader()
                writer.writerows(out_rows)
        except (OSError, ValueError, ValidationError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

        print(f"Batch processed {len(out_rows)} rows -> {args.output}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
