# COVID-19 4C Mortality Score

A reproducible implementation of the ISARIC 4C Mortality Score described by Knight et al. for **adults admitted to hospital with COVID-19**. The repository provides a Python scoring library, CLI, batch CSV processing, FastAPI endpoint, tests, and a dependency-free browser calculator.

## Scope

The original score uses eight admission variables and ranges from 0 to 21 points:

| Variable | Points |
| --- | --- |
| Age | <50: 0; 50–59: 2; 60–69: 4; 70–79: 6; ≥80: 7 |
| Sex in original score | Female: 0; Male: 1 |
| Comorbidities | 0: 0; 1: 1; ≥2: 2 |
| Respiratory rate | <20: 0; 20–29: 1; ≥30: 2 |
| Room-air SpO₂ | ≥92%: 0; <92%: 2 |
| Glasgow Coma Scale | 15: 0; <15: 2 |
| Urea | <7 mmol/L: 0; 7–14: 1; >14: 3 |
| C-reactive protein | <50 mg/L: 0; 50–99: 1; ≥100: 2 |

Historical mortality proportions in the 2020 validation cohort were 1.2% for scores 0–3, 9.9% for 4–8, 31.4% for 9–14, and 61.5% for scores ≥15.

**Clinical limitation:** these are historical prognostic estimates from the original validation population. This implementation does not infer a treatment, escalation, or disposition decision from the score. Use current clinical guidance and the complete patient context.

Reference: Knight SR, Ho A, Pius R, et al. *BMJ*. 2020;370:m3339. doi:10.1136/bmj.m3339.

## Browser calculator

The static calculator is in `docs/` (with the same interface retained in `web/`). It performs the calculation entirely in the browser with no server-side code and no external JavaScript dependencies.

- No patient identifier is requested.
- Entered clinical values are not transmitted by the static page.
- The page is responsive and keyboard accessible.
- Urea can be entered directly in mmol/L or as BUN in mg/dL.

GitHub Pages deployment is automated from `docs/`. A live application link is added here only after the deployed site has been verified.

## Python installation

Python 3.10–3.12 is supported.

```bash
git clone https://github.com/abusuraihsakhri/covid19-4c-mortality-score.git
cd covid19-4c-mortality-score
python -m pip install -e .
```

For development:

```bash
python -m pip install -e ".[dev]"
```

## CLI

All eight clinical variables are required. Provide either urea or BUN, not both.

```bash
covid19-4c-score eval \
  --age 65 \
  --sex M \
  --comorbidities 1 \
  --rr 24 \
  --spo2 90 \
  --gcs 15 \
  --urea 8.0 \
  --crp 120
```

JSON output:

```bash
covid19-4c-score eval \
  --age 65 --sex M --comorbidities 1 --rr 24 --spo2 90 \
  --gcs 15 --urea 8.0 --crp 120 --json
```

### Batch CSV

```bash
covid19-4c-score batch -i sample.csv -o 4c_results.csv
```

Required columns are `age`, `sex`, `comorbidities`, `rr`, `spo2`, `gcs`, `crp`, and exactly one populated value per row from `urea` or `bun`. `patient_id` is optional.

## API

Start the FastAPI service locally:

```bash
python cli.py serve --host 127.0.0.1 --port 8000
```

The primary endpoint is:

```text
POST /api/score
```

Interactive API documentation is available from FastAPI at `/docs`, and the generated OpenAPI schema is served at `/openapi.json`.

The previous `/api/audit`, `/api/chat`, and `/api/audit/logs` routes remain for backward compatibility. The identifier-screening helper used by those legacy routes is regex-based and is **not** a substitute for formal de-identification or a HIPAA compliance process.

## Verification

```bash
python -m compileall -q .
ruff check .
pytest -q
python -m build
pip-audit
```

CI runs the test suite on Python 3.10, 3.11, and 3.12, plus dependency auditing and package build verification.

## Docker

```bash
docker build -t covid19-4c-mortality-score .
docker run --rm -p 8000:8000 covid19-4c-mortality-score
```

For persistent verification of the legacy HMAC audit chain, set a private `AUDIT_SECRET_KEY`. If it is omitted, the process generates an ephemeral key rather than using a fixed default.

## Technology and browser compatibility

- Python 3.10–3.12
- FastAPI and Pydantic v2
- Standard HTML/CSS/JavaScript for the static calculator
- GitHub Actions for CI and Pages deployment

The static calculator uses standard browser APIs and does not require Python/WebAssembly. Current versions of Chrome, Edge, Firefox, and Safari are expected to work.

## License

MIT — see [LICENSE](LICENSE).
