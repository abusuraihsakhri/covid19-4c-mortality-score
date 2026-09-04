# Covid19 4C Mortality Score

> **Domain:** Clinical Decision Support & Biomedical Computing  
> **Reference:** Knight SR et al. BMJ 2020; 370:m3339 (ISARIC 4C Prospective Cohort, n=35,463)

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg?logo=fastapi&logoColor=white)
![Audit Trail](https://img.shields.io/badge/Audit-HMAC--SHA256_Tamper--Evident-brightgreen.svg)
![Zero-PHI Guard](https://img.shields.io/badge/Guard-Zero--PHI_Outbound-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)

</div>

---

## 📖 What It Does

ISARIC 4C Mortality Score for COVID-19 Inpatient Severity & Mortality Prognostication.

Calculates the validated ISARIC 4C Mortality Score (0-21 points) from 8 clinical
variables at hospital admission to predict in-hospital mortality risk in COVID-19 patients.

---

## ⚙️ Key Capabilities & Algorithmic Modules

### 🔬 Core Algorithmic & Evaluation Engines

- **`VariableScoreBreakdown`**: Breakdown of points awarded for each of the 8 variables.
- **`FourCMortalityResult`**: Complete 4C Mortality Score evaluation.
- **`FourCMortalityEngine`**: Computational engine for ISARIC 4C Mortality Score.

### 8 Clinical Variables Scored

| Variable | Scoring Logic |
|:---------|:--------------|
| Age | <50 (0), 50-59 (2), 60-69 (4), 70-79 (6), >=80 (7) |
| Sex | Female (0), Male (1) |
| Comorbidities | 0 (0), 1 (1), >=2 (2) |
| Respiratory Rate | <20 (0), 20-29 (1), >=30 (2) |
| SpO2 (room air) | >=92% (0), <92% (2) |
| GCS | 15 (0), <15 (2) |
| Urea | <7 mmol/L (0), 7-14 (1), >14 (3) |
| CRP | <50 mg/L (0), 50-99 (1), >=100 (2) |

### Risk Stratification

| Score | Risk Group | Mortality | Recommended Care |
|:------|:-----------|:----------|:-----------------|
| 0-3 | Low | 1.2% | Outpatient or general ward |
| 4-8 | Intermediate | 9.9% | Inpatient ward |
| 9-14 | High | 31.4% | High acuity stepdown |
| 15-21 | Very High | 61.5% | ICU critical care |

---

## 💻 Installation

```bash
# Clone the repository
git clone https://github.com/abusuraihsakhri/covid19-4c-mortality-score.git
cd covid19-4c-mortality-score

# Install dependencies
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

---

## 💻 CLI Quickstart & Usage

### 1. Evaluate a Single Patient
```bash
python covid_4c_score.py eval --patient-id PT-001 --age 65 --sex M --comorbidities 1 --rr 24 --spo2 91 --gcs 15 --urea 8.5 --crp 45.0
```

### 2. JSON Output
```bash
python covid_4c_score.py eval --age 72 --sex F --json
```

### 3. Batch Process CSV File
```bash
python covid_4c_score.py batch -i sample.csv -o results.csv
```

### 4. Clinical Q&A Chat
```bash
python covid_4c_score.py chat "What are the variables?"
```

### Parameter Reference
- `--patient-id`: Unique patient identifier
- `--age`: Age in years (0-150)
- `--sex`: Biological sex (M/F/Male/Female)
- `--comorbidities`: Number of major comorbidities (0, 1, 2+)
- `--rr`: Respiratory Rate (breaths/min, 0-100)
- `--spo2`: Room air SpO2 (%, 0-100)
- `--gcs`: Glasgow Coma Scale (3-15)
- `--urea`: Serum Urea (mmol/L)
- `--bun`: Blood Urea Nitrogen (mg/dL, alternative to urea)
- `--crp`: C-Reactive Protein (mg/L)

### Input CSV Schema for Batch Processing

| Field | Description | Requirement |
|:------|:------------|:------------|
| `patient_id` | Patient identifier | Required |
| `age` | Age in years | Required |
| `sex` | M/F/Male/Female | Required |
| `comorbidities` | Number of comorbidities | Optional (default: 0) |
| `rr` | Respiratory rate | Optional (default: 18) |
| `spo2` | Oxygen saturation | Optional (default: 95.0) |
| `gcs` | Glasgow Coma Scale | Optional (default: 15) |
| `urea` | Serum urea (mmol/L) | Optional |
| `bun` | Blood urea nitrogen (mg/dL) | Optional |
| `crp` | C-Reactive Protein | Optional (default: 20.0) |

---

## 🛡️ Security & Enterprise Architecture

* **Zero-PHI Outbound Interceptor:** Active AST and regex inspection blocking SSNs, MRNs, phone numbers, and patient identifiers.
* **Tamper-Evident HMAC-SHA256 Audit Trail:** Chained, cryptographically signed logs for every evaluation and state transition.
* **Input Validation:** All clinical parameters validated against clinically plausible ranges.
* **FastAPI & Prometheus Telemetry:** Exposes OpenAPI 3.1 REST endpoints and operational Prometheus metrics (`/metrics`).

### Environment Variables

| Variable | Description | Default |
|:---------|:------------|:--------|
| `AUDIT_SECRET_KEY` | Secret key for HMAC-SHA256 audit trail | Development fallback (set in production!) |
| `MODEL_PROVIDER` | LLM provider for chat (mock/ollama/claude/openai) | mock |

---

## 🧪 Testing & Verification

Run the automated test suite:

```bash
# Run all tests
python -m unittest test_covid_4c_score -v

# Run with pytest (if installed)
python -m pytest tests/ -v

# Run specific test class
python -m unittest test_covid_4c_score.TestInputValidation -v
```

Execute high-throughput batch simulation benchmarks:

```bash
python simulator.py 1000
```

---

## 🐳 Container Deployment

```bash
# Build and run with Docker
docker build -t covid19-4c-mortality-score .
docker run -p 8000:8000 -e AUDIT_SECRET_KEY=your-secret-key covid19-4c-mortality-score

# Or use docker-compose
AUDIT_SECRET_KEY=your-secret-key docker-compose up
```

---

## 📁 Project Structure

```
covid19-4c-mortality-score/
├── agents/                 # Multi-agent orchestration system
│   ├── api.py             # FastAPI REST endpoints
│   ├── base.py            # Security, PHI guard, audit trail
│   ├── learning.py        # Bayesian calibration engine
│   ├── llm_factory.py     # LLM provider factory
│   ├── metrics.py         # Prometheus metrics
│   ├── models.py          # Pydantic data models
│   ├── streamer.py        # WebSocket telemetry
│   ├── supervisor.py      # Multi-agent supervisor
│   └── workers.py         # Specialized worker agents
├── tests/                 # Pytest test suite
├── web/                   # Operations console (HTML)
├── cli.py                 # CLI entry point
├── covid_4c_score.py      # Core scoring engine & CLI
├── enrichment.py          # Feature enrichment suite
├── simulator.py           # High-throughput simulation
├── sample.csv             # Sample patient data
├── pyproject.toml         # Python project configuration
├── Dockerfile             # Container build
├── docker-compose.yml     # Container orchestration
└── openapi_spec.json      # OpenAPI 3.1 specification
```

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.
