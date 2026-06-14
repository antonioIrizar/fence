# Testing Rules

## TDD Requirements

All production code must be written using Test Driven Development.

Required workflow — no exceptions:

1. Write a failing test
2. Run the test and confirm it fails
3. Implement the minimum code to make it pass
4. Refactor
5. Run the full test suite

No production code without a corresponding test.

---

## Coverage Requirements

| Scope                                          | Minimum Coverage |
|------------------------------------------------|-----------------|
| Overall project                                | 90%             |
| `calculations/`                                | 100%            |
| Covenant generation                            | 100%            |
| Eligibility validation                         | 100%            |

Build fails if any threshold is not met.

---

## Unit Tests

Test:

- Entities
- Value objects
- Domain services
- Calculators
- Eligibility rules

Unit tests must NEVER touch:

- Database
- Network
- Filesystem

All external dependencies must be mocked.

---

## Integration Tests

Test:

- Repositories
- API endpoints
- Persistence layer

Use a PostgreSQL test container.
Integration tests are isolated from production data.

---

## API Tests

Use `FastAPI TestClient`.

Validate:

- Request models
- Response models
- HTTP status codes
- Error handling and error response shape
