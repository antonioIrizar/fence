1. Create a Plan to implement Tech_Challenge_Instructions_Senior_Product_Engineering.pdf

file of plan
````
# Plan: Fence Covenant Calculation Platform

## Context

Implement the full covenant calculation platform as specified in the tech challenge. The system must ingest portfolio data from three facilities, apply facility-specific eligibility filters and effective interest rate calculations, produce auditable covenant reports, and publish them to an immutable store. The architecture must follow DDD strictly, with a Strategy Pattern per facility and a Publisher abstraction supporting both Database and Smart Contract backends.

---

## Directory Structure

```
app/
    domain/
        asset/
            base.py            # BaseAsset (Pydantic, Decimal fields)
            educa.py           # EducaAsset
            payearly.py        # PayEarlyAsset
            nomina.py          # NominaAsset
        facility/
            interfaces.py      # FacilityCalculator, EligibilityPolicy, FacilityMapper (ABC)
        covenant/
            entities.py        # CovenantReport, CovenantStatus, ExcludedAsset
            repository.py      # CovenantReportRepository (ABC)
        calculations/
            educa.py           # EducaCalculator, EducaEligibilityPolicy, EducaMapper
            payearly.py        # PayEarlyCalculator, PayEarlyEligibilityPolicy, PayEarlyMapper
            nomina.py          # NominaCalculator, NominaEligibilityPolicy, NominaMapper
        publishers/
            interface.py       # Publisher (ABC)
        errors.py              # FacilityNotSupported, InvalidPortfolioData, CovenantCalculationError, CovenantPublicationError

    application/
        commands/
            calculate_covenant.py   # CalculateCovenantCommand
        queries/
            get_report.py           # GetCovenantReportQuery
        use_cases/
            calculate_covenant.py   # CalculateCovenantUseCase
            get_covenant_report.py  # GetCovenantReportUseCase
        registry.py                 # FacilityRegistry

    infrastructure/
        database/
            base.py            # SQLAlchemy Base
            models.py          # CovenantReportModel
            session.py         # engine + get_session
        repositories/
            postgres_covenant_report_repository.py
        publishers/
            database_publisher.py
            smart_contract_publisher.py  # Stub

    interfaces/
        api/
            routers/
                covenants.py
            schemas/
                request.py
                response.py
            dependencies.py    # DI wiring
            exception_handlers.py

    main.py
    settings.py

tests/
    unit/
        domain/
            calculations/
                test_educa_calculator.py
                test_payearly_calculator.py
                test_nomina_calculator.py
        application/
            test_calculate_covenant_use_case.py
            test_registry.py
    integration/
        test_postgres_repository.py
        test_api_covenants.py
    conftest.py

data/
    facility_a_educa_isa.json
    facility_b_payearly_ewa.json
    facility_c_nomina.json

alembic/
    versions/
        0001_create_covenant_reports.py

pyproject.toml
Dockerfile
docker-compose.yml
.flake8
mypy.ini
.pre-commit-config.yaml
```

---

## Implementation Phases

### Phase 1 — Project Scaffolding

**pyproject.toml** (UV, all deps)
- Runtime: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `sqlalchemy`, `psycopg2-binary`, `alembic`
- Test: `pytest`, `pytest-cov`, `pytest-mock`, `pytest-asyncio`, `httpx`
- Dev: `mypy`, `flake8`, `black`, `pre-commit`

**settings.py** — Pydantic Settings loading from env:
```python
class Settings(BaseSettings):
    database_url: str
    publisher_backend: str = "database"  # "database" | "smart_contract"
    log_level: str = "INFO"
```

**docker-compose.yml** — two services: `api` (FastAPI on port 8000) + `postgres` (port 5432). API depends on postgres. Uses `.env` file for config.

**Dockerfile** — multi-stage: install deps with UV, copy app, run with uvicorn.

**.pre-commit-config.yaml** — hooks: `black`, `flake8`, `mypy`, `pytest`, `end-of-file-fixer`, `trailing-whitespace`.

**pytest coverage config** in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
addopts = "--cov=app --cov-report=term-missing --cov-fail-under=90"

[tool.coverage.run]
source = ["app"]

[tool.coverage.report]
fail_under = 90
# 100% for calculations and eligibility enforced per-module
```

---

### Phase 2 — Domain Layer (TDD)

#### 2.1 `app/domain/errors.py`
Four domain exceptions (no inheritance from HTTPException).

#### 2.2 Asset models (`app/domain/asset/`)

`base.py`:
```python
class BaseAsset(BaseModel):
    external_id: str
    amount: Decimal
    is_eligible: bool
```

`educa.py` — extends BaseAsset with: `status`, `loan_status`, `outstanding_amount: Decimal`, `interest_rate_percentage: Optional[Decimal]`, `effective_date`, `reporting_date`, `student_id`, `school_id`, `days_past_due`, `country`

`payearly.py` — extends BaseAsset with: `status`, `outstanding_principal_amount: Decimal`, `total_principal_amount: Decimal`, `total_fee_amount: Decimal`, `created_at: datetime`, `due_date: date`, `days_past_due`, `receivable_currency`

`nomina.py` — extends BaseAsset with: `status`, `outstanding_amount: Decimal`, `fee_percentage: Decimal`, `fee_amount: Decimal`, `origination_date: date`, `maturity_date: str` (DD/MM/YYYY), `net_monthly_salary: Decimal`, `advance_amount: Decimal`, `repaid_amount: Decimal`

#### 2.3 `app/domain/facility/interfaces.py`
```python
class EligibilityPolicy(ABC):
    def check(self, asset: BaseAsset) -> tuple[bool, list[str]]: ...

class FacilityMapper(ABC):
    def map(self, raw: dict) -> BaseAsset: ...

class FacilityCalculator(ABC):
    def calculate(self, assets: list[dict], facility_id: str, correlation_id: str) -> CovenantReport: ...
```

#### 2.4 `app/domain/covenant/entities.py`
```python
class CovenantStatus(str, Enum):
    COMPLIANT = "COMPLIANT"
    BREACH = "BREACH"

class ExcludedAsset(BaseModel):
    external_id: str
    reasons: list[str]

class CovenantReport(BaseModel):
    report_id: UUID
    facility_id: str
    effective_rate: Decimal       # stored as percentage value, e.g. Decimal("19.43")
    status: CovenantStatus
    total_assets: int
    included_assets: list[str]
    excluded_assets: list[ExcludedAsset]
    computed_at: datetime
    correlation_id: str
```

#### 2.5 `app/domain/covenant/repository.py`
```python
class CovenantReportRepository(ABC):
    def save(self, report: CovenantReport) -> None: ...
    def find_by_id(self, report_id: UUID) -> Optional[CovenantReport]: ...
    def find_by_facility(self, facility_id: str) -> list[CovenantReport]: ...
```

#### 2.6 `app/domain/publishers/interface.py`
```python
class Publisher(ABC):
    def publish(self, report: CovenantReport) -> None: ...
```

---

### Phase 3 — Calculations (100% coverage, TDD)

All math uses `Decimal`. Never `float`. Round to 2dp with `ROUND_HALF_UP`.

#### Facility A — Educa Capital I

**EligibilityPolicy checks** (each failed check adds a reason string):
1. `status.lower() == "open"`
2. `is_eligible == True`
3. `loan_status == "current"`
4. `interest_rate_percentage is not None`

**Formula:**
```
Effective Rate = Σ(outstanding_amount_i × interest_rate_percentage_i) / Σ(outstanding_amount_i)
```
Threshold: `< Decimal("22.0")` → COMPLIANT, else BREACH

**EducaMapper** — handles inconsistent status casing ("open"/"Open"/"OPEN"), maps raw dict to `EducaAsset`. Raises `InvalidPortfolioData` on missing required fields.

#### Facility B — PayEarly US

**EligibilityPolicy checks:**
1. `status.lower() == "performing"`
2. `is_eligible == True`
3. `outstanding_principal_amount > 0`

**Formula:**
```
tenor_days_i = (due_date - created_at.date()).days
fee_yield_i = (total_fee_amount_i / total_principal_amount_i) × (365 / tenor_days_i)
Effective Rate = Σ(outstanding_principal_amount_i × fee_yield_i) / Σ(outstanding_principal_amount_i)
```
Threshold: `< Decimal("3.0")` → COMPLIANT, else BREACH

**PayEarlyMapper** — parses ISO 8601 datetime for `created_at`, date string for `due_date`.

#### Facility C — Nomina Express I

**EligibilityPolicy checks:**
1. `status.lower() == "active"`
2. `is_eligible == True`
3. `outstanding_amount > 0`

**Formula:**
```
repayment_months_i = months between origination_date and maturity_date
annualized_fee_i = fee_percentage_i × (12 / repayment_months_i)
Effective Rate = Σ(outstanding_amount_i × annualized_fee_i) / Σ(outstanding_amount_i)
```
Where `maturity_date` is in `DD/MM/YYYY` format — the mapper parses it.
Threshold: `< Decimal("5.0")` → COMPLIANT, else BREACH

**NominaMapper** — parses `DD/MM/YYYY` maturity_date, computes `repayment_months` as calendar month difference (relativedelta or manual arithmetic with Decimal).

---

### Phase 4 — Application Layer

**`app/application/registry.py`**
```python
class FacilityRegistry:
    _calculators: dict[str, FacilityCalculator]

    def register(self, facility_id: str, calculator: FacilityCalculator): ...
    def get(self, facility_id: str) -> FacilityCalculator:
        # raises FacilityNotSupported if not found
```

**`app/application/use_cases/calculate_covenant.py`**
```python
class CalculateCovenantUseCase:
    """
    Business context: Ingest raw portfolio JSON, run facility-specific eligibility
    and calculation, produce a CovenantReport, and publish it immutably.
    Assumptions: facility_id maps to a registered FacilityCalculator.
    """
    def __init__(self, registry, repository, publisher): ...
    def execute(self, command: CalculateCovenantCommand) -> CovenantReport: ...
```
Flow: `registry.get(facility_id)` → `calculator.calculate(assets, ...)` → `repository.save(report)` → `publisher.publish(report)` → return report

**`app/application/use_cases/get_covenant_report.py`**
Simple query use case — fetches by ID from repository.

---

### Phase 5 — Infrastructure Layer

**`app/infrastructure/database/models.py`** — SQLAlchemy ORM model:
```
covenant_reports: id (UUID PK), facility_id, effective_rate (Numeric(20,10)),
status, total_assets, included_assets (JSON), excluded_assets (JSON),
computed_at, correlation_id, published_at
```

**`app/infrastructure/repositories/postgres_covenant_report_repository.py`** — implements the domain interface using SQLAlchemy Session.

**`app/infrastructure/publishers/database_publisher.py`** — calls `repository.save()` and marks `published_at`. The immutability guarantee: published reports are never overwritten; each calculation creates a new row.

**`app/infrastructure/publishers/smart_contract_publisher.py`** — stub that logs intent but delegates to DB. Documents the extension point.

**Alembic migration** — creates `covenant_reports` table.

---

### Phase 6 — API Layer

**Three endpoints** in `app/interfaces/api/routers/covenants.py`:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/covenants/{facility_id}/calculate` | Ingest assets JSON, run calculation, return report |
| `GET` | `/api/v1/covenants/{facility_id}/reports/{report_id}` | Fetch a specific report |
| `GET` | `/api/v1/covenants/{facility_id}/reports` | List all reports for a facility |

`POST` body: `{ "assets": [...] }` — raw JSON array from originator.
`X-Correlation-ID` header accepted (auto-generated if absent).

**Response schema:**
```json
{
  "report_id": "uuid",
  "facility_id": "facility-a",
  "effective_rate": "19.43",
  "status": "COMPLIANT",
  "threshold": "22.00",
  "summary": { "total": 8, "included": 5, "excluded": 3 },
  "included_assets": ["EDU-STU-10001", ...],
  "excluded_assets": [{ "external_id": "EDU-STU-10003", "reasons": ["loan_status != current"] }],
  "computed_at": "2026-06-12T..."
}
```

**Exception handlers** in `exception_handlers.py` convert domain errors to HTTP:
- `FacilityNotSupported` → 404
- `InvalidPortfolioData` → 422
- `CovenantCalculationError` → 500
- `CovenantPublicationError` → 500

**DI wiring** in `app/interfaces/api/dependencies.py`:
- Registry is a singleton populated at startup with all three facility calculators
- Session scoped per-request
- Publisher selected based on `settings.publisher_backend`

---

### Phase 7 — Sample Data Files

Create `data/facility_a_educa_isa.json`, `data/facility_b_payearly_ewa.json`, `data/facility_c_nomina.json` with the exact data from the PDF.

These are used in integration tests and for manual verification.

**Pre-computed expected results** (for test assertions):

**Facility A — Educa** — Eligible: EDU-10001, 10002, 10004, 10005, 10007 (status=open/Open/OPEN, loan_status=current, is_eligible=true, rate not null). Excluded: 10003 (delinquent), 10006 (closed/written_off), 10008 (rate=null).
Formula: `Σ(outstanding × rate) / Σ(outstanding)` over eligible set.

**Facility B — PayEarly** — Eligible: status="performing"/"PERFORMING"/"Performing", is_eligible=true, outstanding_principal > 0.
Formula: fee_yield per asset annualized by tenor, then weighted average.

**Facility C — Nomina** — Eligible: status="active"/"ACTIVE", is_eligible=true, outstanding_amount > 0.
Formula: annualized fee weighted by outstanding.

---

### Phase 8 — Testing

**Unit tests** (`tests/unit/`):
- `test_educa_calculator.py` — test each eligibility rule independently, test formula with known inputs, test COMPLIANT/BREACH threshold boundary, test empty eligible set raises `CovenantCalculationError`
- `test_payearly_calculator.py` — same structure; test tenor_days computation, annualization
- `test_nomina_calculator.py` — same structure; test DD/MM/YYYY parsing, repayment_months computation
- `test_calculate_covenant_use_case.py` — mock registry, repository, publisher; verify orchestration
- `test_registry.py` — register/get/FacilityNotSupported

**Integration tests** (`tests/integration/`):
- `test_postgres_repository.py` — real PostgreSQL (pytest fixture spins up via docker or env var); save + find_by_id + find_by_facility
- `test_api_covenants.py` — FastAPI `TestClient`; POST with full Facility A/B/C sample data; assert status codes, response shape, COMPLIANT/BREACH result; GET by report_id; 404 on unknown facility

**Coverage enforcement:**
```toml
[tool.coverage.report]
fail_under = 90
exclude_lines = ["pragma: no cover", "if TYPE_CHECKING"]
```
Calculations module gets a per-file `# pragma: no branch` policy — the CI command runs `pytest --cov=app/domain/calculations --cov-fail-under=100` separately.

---

### Phase 9 — README

Sections:
1. **Overview** — what the platform does
2. **Architecture** — DDD layers, dependency rule diagram
3. **Facility Extensibility** — how Strategy Pattern makes adding a new facility a 3-file addition (mapper + eligibility + calculator, register in wiring)
4. **Covenant Model** — why immutability matters, how Publisher abstraction enables Smart Contract swap-in
5. **Trade-offs** — Decimal vs float, sync vs async API, DB vs Smart Contract, JSON storage for report assets
6. **Production Evolution** — async SQLAlchemy, Smart Contract publisher, event sourcing for audit trail
7. **Setup & Usage** — `docker compose up`, sample `curl` commands

---

## Verification

```bash
# Start the system
docker compose up --build

# Run full test suite
docker compose run api pytest --cov=app --cov-fail-under=90

# Static analysis
black --check .
flake8 .
mypy app

# Smoke test — Facility A
curl -X POST http://localhost:8000/api/v1/covenants/facility-a/calculate \
  -H "Content-Type: application/json" \
  -d @data/facility_a_educa_isa.json
# Expected: effective_rate ~19.43, status COMPLIANT (< 22%)

# Smoke test — Facility B
curl -X POST http://localhost:8000/api/v1/covenants/facility-b/calculate \
  -H "Content-Type: application/json" \
  -d @data/facility_b_payearly_ewa.json

# Smoke test — Facility C
curl -X POST http://localhost:8000/api/v1/covenants/facility-c/calculate \
  -H "Content-Type: application/json" \
  -d @data/facility_c_nomina.json
```
````


2. Add a new endpoint to can add assets by facility and store it on database.    
  This assets should be store with basic info on colummns and all asset save in 
  raw on json colum for debug. columns of "external_id" and facility must be a  
  unique together. Discard duplicates and notify when it has duplicates.    
3.Improve insert asserts by facility to have precalculate the covenant to can   
  get info on real time using the incremental aggregation pattern. To do this   
  follow the next instructions:                                                 
                                                                                
                                                                                
                                                                                
    * Create a new table on database facility_covenant_state to have            
  precaculate effective rate, covenant status, facility_id, last update,        
  accumulated denominator, accumulated numerator                                
    * Do row level locking when update data to avoid problems with concurtency  
  and race condition.                                                           
                                                                                
    * Lifecycle-Aware Formulas when isnert new data, and prepare system to      
  future can have updates, but not implement now.                               
      Calculate the individual components by facility:                          
       * facility_a:                                                            
         - asset_numerator = outstanding_amount * interest_rate_percentage      
         - asset_denominator = outstanding_amount                               
       * facility_b:                                                            
         - asset_numerator = outstanding_principal_amount * fee_yield (where    
  fee_yield = (total_fee_amount / total_principal_amount) * (365 / tenor_days)) 
         - asset_denominator = outstanding_principal_amount                     
       * facility_c:                                                            
         - asset_numerator = outstanding_amount * annualized_fee (where         
  annualized_fee = fee_percentage * (12 / repayment_months))                    
         - asset_denominator = outstanding_amount                               
    * Imporve AssetRecord with a new boolean of Eligibility Criteria and        
  reasons for exlcusion to can add on report when it is needed              

4. ❯ Improve IngestAssetsUseCase:                                                  
  * Move Ingestion to a new services.                                           
  * Move update coventant state to a function.      

5. Create a new endpoint to retrive actual state of facility.                                                                                                                                                                                                                                                                                                               
  It should return coventant state with summary, included assests and Excluded assets.                                                                                                                                                                                                                                                                                     
  It should not create a report.                             
                                        
6. review GetFacilityStateUseCase and IngestAssetsUseCase to validate with rules of project.    

7 fix.                                                                                                                                                                                                                                                                            

8. ❯ Plan:                                                                                                                                                                                                                                                                                                                                                                    
  1. Remove endpoint calculate_covenant, all calculatiosn are done with ingest assets.                                                                                                                                                                                                                                                                                     
  2. Create a new endpoint to create a Report or smart contract by facility.                                                                                                                                                                                                                                                                                               
   * It should be like smart contract but with postgreSQL.                                                                                                                                                                                                                                                                                                                 
   * Smart contract must be save                                                                                                                                                                                                                                                                                                                                           
   * Smart contract can retrive on any moment.                                                                                                                                                                                                                                                                                                                             
   * If no data changes and you want a new smart contract, it should return the already generate.                                                                                                                                                                                                                                                                          
   * You can generate a new smart contract when you need.                                                                                                                                                                                                                                                                                                                  
   * Smart contract must have a timestamp.                                                                                                                                                                                                                                                                                                                                 
   * Smart contract should save a audit hash. This hash use information of assests inside postgres to validate information are not maliciuos changes.                                                                                                                                                                                                                      
   * Audit hash must be verify on any moment by Capital provider and Asset Originator.                                                                                                                                                                                                                                                                                     
   * Prepare all code to can change postgres to a real smart contract with web. x
9. Endpoint verify is not working correctly by old report when new assests are inserted. Fix it to can verify old reports with the old data.                                                                                                                                                                                                                                
  Assume that, for now, old assets cannot modify only new assets can be insert.

10. review my uncommitted changes  

11. fix: 
  1. verify_report.py:99 — None passed to required Decimal fields in FacilityCovenantState                                                                                                                                                                                                                                                                                 
  CovenantReport.accumulated_numerator/denominator are Optional[Decimal] (default None). FacilityCovenantState declares them as required Decimal. For any report created before migration 0005 the call to _reconstruct_state produces a Pydantic ValidationError, crashing the verify endpoint with HTTP 500 instead of a clean error.                                    
                                                                                                                                                                                                                                                                                                                                                                           
  2. verify_report.py:81 — stored_hash: str receives None when audit_hash is absent                                                                                                                                                                                                                                                                                        
  If report.audit_hash is None, the use case skips the early-return guard (it was removed in the last edit), reaches stored_hash=report.audit_hash, and returns is_valid=False — a false tamper signal — plus likely a serialization error since VerifyReportResponse.stored_hash is typed str.                                                                            
                                                                                                                                                                                                                                                                                                                                                                           
  3. models.py:109-114 — Mapped[Optional[...]] contradicts nullable=False                                                                                                                                                                                                                                                                                                  
  audit_hash, accumulated_numerator, and accumulated_denominator are all Mapped[Optional[T]] but declared nullable=False. SQLAlchemy accepts None in Python without complaint and then raises IntegrityError at flush time. The type annotation actively misleads callers into thinking None is safe.  

audit_hash, accumulated_numerator, and accumulated_denominator must no be nullable

12. Change code of audit_hash, accumulated_numerator, and accumulated_denominator from CovenantReport to cannot be None

13. Remove CalculateCovenantCommand. It is not used, all calcualtions are done by IngestAssetsCommand

14. Remove calculate from FacilityCalculator. Remove from all implementations 

15. fix:                                                                                                                                                                                                                                                                                                                                                                     
   4. verify_report.py:64 — IDOR: facility_id parameter never cross-checked against report.facility_id                                                                                                                                                                                                                                                                     
                                                                                                                                                                                                                                                                                                                                                                           
    find_by_id fetches any report regardless of facility. If a caller passes facility-a with a report UUID belonging to facility-b, the use case queries facility-a assets, hashes them, and returns is_valid=False — a false tamper signal with no error. The fix: add if report.facility_id != facility_id: raise CovenantCalculationError(...) immediately after the    
                                                                                                                                                                                                                                                                                                                                                                           
    find_by_id call.                                                                                                                                                                                                                                                                                                                                          
                                                                                                                                                                                                                                                                                                                                                                           
    5. postgres_asset_repository.py:65 — Timezone stripping is wrong in PostgreSQL under non-UTC server TZ                                                                                                                                                                                                                                                                 
                                                                                                                                                                                                                                                                                                                                                                           
    at.replace(tzinfo=None) works on the SQLite test DB (which stores naive UTC) but in production PostgreSQL a naive datetime is interpreted in the server's local timezone. An asset ingested at 12:00 UTC with a US/Eastern PostgreSQL server could appear as 17:00 UTC, shifting the snapshot window by hours and causing legitimate reports to fail verification. The 
                                                                                                                                                                                                                                                                                                                                                                           
    tz-strip workaround belongs in the test fixture, not in production code.
16. review current diff from main branch   

17. export last report of review to a file review.md
18. fix the findings with th number 1  
18. fix the findings with th number 2
19. fix the findings with th number 3
20. fix the rest of findings
21. Review version of alembic and and new migrations if something miss
