# CLAUDE.md

## Project Overview

This project implements Fence's covenant calculation platform.

The system ingests portfolio data from multiple facilities, applies facility-specific covenant
calculations, generates covenant reports, and publishes covenant results to an immutable store
(database or smart contract abstraction).

The goal is not only correctness but also auditability, extensibility, and deterministic
financial calculations.

---

## Technology Stack

| Layer              | Tool                          |
|--------------------|-------------------------------|
| Runtime            | Python 3.11                   |
| API                | FastAPI                       |
| Validation         | Pydantic v2                   |
| Dependency Mgmt    | UV                            |
| Testing            | Pytest, pytest-cov, pytest-mock |
| Static Analysis    | Mypy, Flake8, Black           |
| Pre-commit         | pre-commit                    |
| Containerization   | Docker, Docker Compose        |
| Persistence        | PostgreSQL                    |

---

## Additional Rules

Detailed rules are in `.claude/rules/`. Always read the relevant file before starting a task:

- **Architecture, DDD, patterns** → `.claude/rules/architecture.md`
- **Testing strategy, TDD, coverage** → `.claude/rules/testing.md`
- **Financial calculations, errors, logging, code style** → `.claude/rules/standards.md`

---

## Definition of Done

A task is complete **only** if all of the following are true:

- [ ] Tests written first (TDD)
- [ ] All tests passing
- [ ] Coverage thresholds maintained
- [ ] `black .` passes
- [ ] `flake8 .` passes
- [ ] `mypy app` passes
- [ ] Docker build passes
- [ ] Documentation updated

If any item is not checked, the task is **incomplete**.
