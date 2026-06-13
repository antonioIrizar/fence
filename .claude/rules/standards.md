# Standards

## Financial Calculation Rules

All financial calculations must:

- Use `Decimal` — never `float`
- Be deterministic
- Round explicitly
- Document the rounding strategy at the point of rounding

```python
# Correct
from decimal import Decimal
amount = Decimal("0.01")

# Never
amount = 0.01
```

Any calculation that uses `float` is a bug.

---

## Error Handling

Domain errors are defined in the Domain layer:

- `FacilityNotSupported`
- `InvalidPortfolioData`
- `CovenantCalculationError`
- `CovenantPublicationError`

Domain errors are converted to HTTP responses **only** at the API boundary.

Domain must never raise `HTTPException`.
Infrastructure must never swallow domain errors silently.

---

## Logging

Use structured logging throughout.

Required fields on every log entry:

- `facility_id`
- `covenant_id`
- `report_id`
- `correlation_id`

No `print` statements anywhere in the codebase.

---

## Configuration

All configuration via environment variables.
Use `Pydantic Settings` for loading and validation.
No hardcoded configuration values anywhere.

---

## Code Style

Mandatory tools — all must pass before merge:

```bash
black .
flake8 .
mypy app
```

Pre-commit hooks enforce this automatically:

- `black`
- `flake8`
- `mypy`
- `pytest`
- `end-of-file-fixer`
- `trailing-whitespace`

No commit may bypass hooks.

---

## Docker Rules

The application must run entirely through Docker Compose.

Required services:

- `api`
- `postgres`

```bash
docker compose up
```

Must start the complete system with no additional manual steps.
