# Fence — Covenant Calculation Platform

Automates covenant compliance for credit facilities: ingests portfolio data from asset originators, computes facility-specific effective interest rates, and publishes the results as immutable covenant reports.

---

## Overview

Fence operates as a **Calculation Agency** for multiple facilities, each with a different Asset Originator, a different asset data model, and a different rate calculation formula defined in their Credit Agreement. The system must:

1. **Ingest** raw portfolio data submitted by the originator
2. **Compute** the effective interest rate using the facility's formula
3. **Publish** the result as an immutable covenant report that both the Capital Provider and the Asset Originator can independently verify

---

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

The API starts at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

### Run a calculation

```bash
# Facility A — Educa Capital I
curl -X POST http://localhost:8000/api/v1/covenants/facility-a/calculate \
  -H "Content-Type: application/json" \
  -d @data/facility_a_educa_isa.json

# Facility B — PayEarly US
curl -X POST http://localhost:8000/api/v1/covenants/facility-b/calculate \
  -H "Content-Type: application/json" \
  -d @data/facility_b_payearly_ewa.json

# Facility C — Nomina Express I
curl -X POST http://localhost:8000/api/v1/covenants/facility-c/calculate \
  -H "Content-Type: application/json" \
  -d @data/facility_c_nomina.json
```

### Retrieve a report

```bash
curl http://localhost:8000/api/v1/covenants/facility-a/reports/{report_id}
curl http://localhost:8000/api/v1/covenants/facility-a/reports
```

---

## Architecture

The system follows **Domain Driven Design** with a strict dependency rule:

```
Interfaces (FastAPI routes)
       ↓
Application (use cases, registry)
       ↓
Domain (entities, calculators, policies — pure Python)
       ↑
Infrastructure (SQLAlchemy, publishers — depends on Domain interfaces)
```

### Directory layout

```
app/
  domain/
    asset/          — EducaAsset, PayEarlyAsset, NominaAsset (Pydantic, Decimal)
    facility/       — FacilityCalculator, EligibilityPolicy, FacilityMapper (ABC)
    covenant/       — CovenantReport entity, CovenantReportRepository (ABC)
    calculations/   — One module per facility: calculator + policy + mapper
    publishers/     — Publisher (ABC)
    errors.py       — Domain exceptions (no FastAPI/HTTP dependency)
  application/
    use_cases/      — CalculateCovenantUseCase, GetCovenantReportUseCase
    registry.py     — FacilityRegistry (maps facility_id → FacilityCalculator)
  infrastructure/
    database/       — SQLAlchemy models + session
    repositories/   — PostgresCovenantReportRepository
    publishers/     — DatabasePublisher, SmartContractPublisher (stub)
  interfaces/
    api/            — FastAPI routes, Pydantic schemas, DI wiring
```

---

## Handling Facility Variability — Strategy Pattern

Each facility has its own data model, status vocabulary, and rate formula. The **Strategy Pattern** isolates this variability:

| Abstraction | Purpose |
|---|---|
| `FacilityMapper` | Translates raw originator JSON → typed domain asset |
| `EligibilityPolicy` | Applies facility-specific include/exclude rules |
| `FacilityCalculator` | Orchestrates mapping → filtering → formula |

Adding a new facility requires only:

1. A new asset model (`app/domain/asset/facility_d.py`)
2. A new calculations module (`app/domain/calculations/facility_d.py`) with mapper, policy, and calculator
3. One `registry.register("facility-d", FacilityDCalculator())` line in `dependencies.py`

No existing calculation logic is touched.

---

## Rate Calculation Specifications

### Facility A — Educa Capital I (Education Loans)

**Formula:** Weighted Average Loan IRR

```
Effective Rate = Σ(outstanding_amount_i × interest_rate_percentage_i) / Σ(outstanding_amount_i)
```

**Eligibility:** `status == "open"` (case-insensitive), `is_eligible == True`, `loan_status == "current"`, `interest_rate_percentage` not null

**Threshold:** `< 22.00%` — breach triggers disbursement pause

### Facility B — PayEarly US (Earned Wage Access)

**Formula:** Portfolio Fee Yield (EWA products carry 0% interest)

```
tenor_days_i    = (due_date - created_at.date()).days
fee_yield_i     = (total_fee_amount_i / total_principal_amount_i) × (365 / tenor_days_i)
Effective Rate  = Σ(outstanding_principal_i × fee_yield_i) / Σ(outstanding_principal_i)
```

**Eligibility:** `status == "performing"` (case-insensitive), `is_eligible == True`, `outstanding_principal_amount > 0`

**Threshold:** `< 3.00%` — breach triggers Advance Cap Review

### Facility C — Nomina Express I (Salary Advance)

**Formula:** Weighted Average Annualized Advance Fee

```
repayment_months_i = calendar months between origination_date and maturity_date
annualized_fee_i   = fee_percentage_i × (12 / repayment_months_i)
Effective Rate     = Σ(outstanding_amount_i × annualized_fee_i) / Σ(outstanding_amount_i)
```

Note: `maturity_date` is in `DD/MM/YYYY` format.

**Eligibility:** `status == "active"` (case-insensitive), `is_eligible == True`, `outstanding_amount > 0`

**Threshold:** `< 5.00%` — breach requires originator to reduce advance ratio

---

## Covenant Model and Immutability

The effective interest rate is a **covenant** — a binding term in the Credit Agreement. Once computed and published, it must be independently verifiable by both parties and serve as an authoritative input for downstream settlement and compliance checks.

This has two architectural consequences:

1. **Immutable reports**: each calculation creates a new `covenant_reports` row. Existing rows are never updated or deleted. `report_id` (UUID) is the stable reference.

2. **Publisher abstraction**: the `Publisher` interface decouples the persistence mechanism from the domain logic. The `DatabasePublisher` (default) writes to PostgreSQL. The `SmartContractPublisher` is a documented stub ready for a `web3.py` integration — see `app/infrastructure/publishers/smart_contract_publisher.py` for the extension points.

To switch to smart contract publishing, set `PUBLISHER_BACKEND=smart_contract` in `.env`.

---

## Financial Calculation Correctness

All arithmetic uses Python's `Decimal` type — never `float`. Every rate is rounded to 2 decimal places with `ROUND_HALF_UP` before the threshold comparison and before returning to the caller. This ensures deterministic, auditable results regardless of platform.

---

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/covenants/{facility_id}/calculate` | Submit portfolio, receive covenant report |
| `GET` | `/api/v1/covenants/{facility_id}/reports/{report_id}` | Retrieve report by ID |
| `GET` | `/api/v1/covenants/{facility_id}/reports` | List all reports for facility |

Pass `X-Correlation-ID` header for end-to-end tracing. Auto-generated if absent.

**Error responses:**

| Error | HTTP |
|---|---|
| Unknown `facility_id` | 404 |
| Malformed asset data | 422 |
| No eligible assets | 500 |
| Persistence failure | 500 |

---

## Testing

```bash
# Unit + integration (SQLite in-memory)
pytest --cov=app --cov-fail-under=90

# Via Docker
docker compose run api pytest
```

Coverage targets:
- Overall: ≥ 90% (currently ~97%)
- `app/domain/calculations/`: 100%

---

## IA transcript

I used Claude Code with Sonnet 4.6 effort Hight.

The file [prompts.md](prompts.md) contains all the prompts I used.

the file [full_transcript_calude_code.md](full_transcript_calude_code.md) contains the full transcript obtained from the project.
