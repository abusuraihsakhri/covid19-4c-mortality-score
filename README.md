# ISARIC 4C Mortality Score for COVID-19 Inpatients

[![ISARIC 4C / BMJ 2020](https://img.shields.io/badge/Validation-BMJ%202020%3B370%3Am3339-blue.svg)](#)
[![Clinical Verification](https://img.shields.io/badge/Clinical%20Validation-100%25%20Passing-brightgreen.svg)](#)
[![Zero-PHI Guard](https://img.shields.io/badge/HIPAA%20Safe%20Harbor-Zero--PHI-success.svg)](#)

A clinical risk-stratification engine implementing the validated **ISARIC 4C Mortality Score** (Knight et al., BMJ 2020) for hospitalized COVID-19 patients based on 8 admission parameters.

## Scoring Algorithm (0 – 21 Points)

| Variable | Parameters & Thresholds | Points |
|:---|:---|:---|
| **Age** | <50 (0), 50–59 (+2), 60–69 (+4), 70–79 (+6), $\ge 80$ (+7) | 0 – 7 |
| **Sex** | Female (0), Male (+1) | 0 – 1 |
| **Comorbidities** | 0 (0), 1 (+1), $\ge 2$ (+2) | 0 – 2 |
| **Respiratory Rate** | <20 (0), 20–29 (+1), $\ge 30$ (+2) | 0 – 2 |
| **Room Air $SpO_2$** | $\ge 92\%$ (0), $< 92\%$ (+2) | 0 – 2 |
| **Glasgow Coma Scale** | 15 (0), $< 15$ (+2) | 0 – 2 |
| **Blood Urea / BUN** | $< 7\text{ mmol/L}$ (0), $7 - 14\text{ mmol/L}$ (+1), $> 14\text{ mmol/L}$ (+3) | 0 – 3 |
| **C-Reactive Protein** | $< 50\text{ mg/L}$ (0), $50 - 99\text{ mg/L}$ (+1), $\ge 100\text{ mg/L}$ (+2) | 0 – 2 |

## Risk Stratification & In-Hospital Mortality

- **Low (0 – 3 points)**: Mortality **1.2%** (0.9% – 1.5%) — Outpatient care / general ward.
- **Intermediate (4 – 8 points)**: Mortality **9.9%** (9.2% – 10.6%) — Inpatient hospital admission & close vital monitoring.
- **High (9 – 14 points)**: Mortality **31.4%** (30.7% – 32.2%) — Stepdown / high-acuity unit, corticosteroids, antivirals, HFNC.
- **Very High (15 – 21 points)**: Mortality **61.5%** (60.0% – 63.0%) — Urgent Critical Care / ICU admission.

## CLI Usage

```bash
# Evaluate a patient
python covid_4c_score.py eval --age 72 --sex M --comorbidities 2 --rr 26 --spo2 89 --urea 11.2 --crp 120

# Output structured JSON
python covid_4c_score.py eval --age 65 --sex F --json
```

## Running Unit Tests

```bash
python -m unittest test_covid_4c_score.py
```
