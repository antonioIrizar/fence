# Architecture Rules

## Mandatory Architecture

The entire codebase MUST follow Domain Driven Design (DDD).

No business logic may exist inside:

- FastAPI routes
- Database repositories
- Infrastructure adapters

Business logic belongs exclusively in the Domain layer.

---

## DDD Structure

```
app/
    domain/
        asset/
        
        facility/

        covenant/

        calculations/

    application/
        commands/
        queries/
        use_cases/
        registry.py   

    infrastructure/
        database/
        repositories/
        publishers/

    interfaces/
        api/ 

    interfaces/
        api/
            routers/
            schemas/

tests/
    unit/
    integration/
```

---

## Dependency Rule

```
Interfaces
    ↓
Application
    ↓
Domain
```

Infrastructure may depend on Domain.

Domain must NEVER depend on:

- FastAPI
- SQLAlchemy
- PostgreSQL
- Requests
- Web3
- Any infrastructure code

Domain must be pure Python only can use pydantic to improve.

---

## Facility Extensibility

Each facility must be implemented using the **Strategy Pattern**.

New facilities must be addable without modifying existing calculation logic.

Required abstractions:

- `FacilityCalculator`
- `EligibilityPolicy`
- `FacilityMapper`

Each facility provides its own implementation.

```
FacilityCalculator
├── EducaCalculator
├── PayEarlyCalculator
└── NominaCalculator
```

---

## Repository Pattern

Repositories must be defined as **interfaces in the Domain layer**.

Example interface:

```python
class CovenantReportRepository:
    ...
```

Infrastructure provides the concrete implementation:

```python
class PostgresCovenantReportRepository(CovenantReportRepository):
    ...
```

Application layer depends only on the interface, never on the implementation.

---

## API Design Rules

Routes may:

- Validate requests
- Call use cases
- Return responses

Routes may NOT:

- Execute business rules
- Perform calculations
- Access repositories directly

---

## Smart Contract Abstraction

Publishing must occur through a `Publisher` interface.

```
Publisher
├── DatabasePublisher
└── SmartContractPublisher
```

Application code must not know which implementation is active.
Wiring happens exclusively at the infrastructure/composition root level.

---

## Documentation Requirements

Every public class must document:

- Purpose
- Inputs
- Outputs

Every use case must document:

- Business context
- Assumptions

Architecture decisions belong in `README.md`.
