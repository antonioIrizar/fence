# Fence — Covenant Calculation Platform

Automates covenant compliance for credit facilities: ingests portfolio data from asset originators, computes facility-specific effective interest rates, and publishes the results as immutable covenant reports.

---

## Your Reasoning and Assumptions

### Data Ingestion & Scaling
- **Assumptions on Payload Size:** The system exposes an API endpoint designed to ingest an array of assets. It is assumed that the batch size per request will remain within a reasonable threshold (up to a few hundred assets). If the data volume grows significantly, consumers can chunk the dataset into multiple sequential requests. For massive datasets, the design should evolve to support file uploads processed via asynchronous batch jobs.
- **Data Deduplication:** It is assumed that all ingested assets are new. The system does not currently support in-place updates. If a duplicate asset is detected, it is safely discarded, and the API returns a warning notification within the ingestion response.
- **Auditability:** Every asset is stored in its raw format inside a PostgreSQL database. This ensures future debuggability and serves as the source of truth for generating audit hashes.

### Real-Time Analytics & Aggregations
- **Incremental Aggregate Pattern:** To ensure metrics like the interest rate are available in real-time with zero query delay, calculations are pre-computed during the ingestion phase using an **Incremental Aggregate Pattern**. Instead of scanning the entire dataset on every read, metrics are updated incrementally as new assets arrive.
- **Formula Adjustment (Facility B):** During implementation, it was noted that to properly utilize `fee_yield` in the calculation, it needed to be converted into a percentage format. Therefore, the result was adjusted by multiplying by 100 to ensure mathematical correctness.

### Smart Contract & Report Generation
- **Idempotency & History:** The endpoint responsible for generating the smart contract or report is strictly idempotent. If a report has already been generated for the given context, the system fetches and returns the existing one instead of recreating it. (API has boolean to force to create a new) Furthermore, the architecture stores all Smart contracts report.
- **On-Chain Optimization (Audit Hash):** Uploading raw data for every single asset directly to the blockchain is highly inefficient, cost-prohibitive, and would quickly lead to chain bloat. To solve this, the architecture implements an **Audit Hash** mechanism. A verification hash is computed cryptographically from the asset data stored in PostgreSQL, and only this compact hash is anchored to the smart contract. 
- **Verification Endpoint:** An endpoint has been exposed to verify the integrity of the database against the smart contract hash. If a malicious actor or a system failure alters the asset data in PostgreSQL, the hashes will mismatch immediately. 

---

## How Your Design Handles the Variability Across Facilities

The core architecture strictly adheres to **Domain-Driven Design (DDD)** principles. To elegantly handle different business rules and calculation logic across various facilities, the **Strategy Pattern** was implemented. 

By decoupling the specific facility logic from the orchestration layer, adding a new facility type or modifying an existing one is entirely trivial. It only requires introducing a new strategy implementation that fulfills the domain interface, completely eliminating the risk of regression in existing facility workflows.

### Add new facility

Each facility has its own data model, status vocabulary, and rate formula. The **Strategy Pattern** isolates this variability:

| Abstraction | Purpose |
|---|---|
| `FacilityMapper` | Translates raw originator JSON → typed domain asset |
| `EligibilityPolicy` | Applies facility-specific include/exclude rules |
| `FacilityCalculator` | Orchestrates mapping → filtering → formula |

Adding a new facility requires only:

1. A new asset model (`app/domain/asset/facility_d.py`)
2. A new calculations module (`app/domain/calculations/facility_d.py`) with implement interface of mapper, policy, and calculator
3. One `registry.register("facility-d", FacilityDCalculator())` line in `dependencies.py`

No existing calculation logic is touched.

---

## How the Covenant Model Influenced Your Architecture

The Covenant Model acted as the primary driver for two major architectural patterns in this solution:
1. **The Audit Hash Approach:** The need to enforce covenants without overloading the blockchain led to pushing the raw asset storage off-chain (PostgreSQL) while maintaining cryptographic verification on-chain.
2. **Incremental Aggregate Pattern:** Covenant validation requires fast, reactive checks. Pre-computing the interest rate and other key metrics during ingestion ensures the system can evaluate covenant health instantly without performing heavy, blocking database aggregations at runtime.

---

## Trade-offs You Considered

1. **No Asset Updates/Recalculations:** The system currently treats assets as immutable. Implementing asset modifications would require managing deltas and establishing a historical snapshot ledger of assets so that old smart contracts can still be validated against the exact state of the data at their time of creation.
2. **Public API Exposure:** The API is currently exposed without security layers. In a production environment, an authentication layer (such as JWT/OAuth2) is mandatory.
3. **Lack of Rate Limiting:** There is currently no protection against API abuse or Distributed Denial of Service (DDoS) attacks.
4. **Covenant Threshold Behavior:** No automated workflows are currently triggered upon breaching a Covenant Threshold. In a real-world scenario, the system should immediately halt asset ingestion for that facility and trigger real-time alerts (e.g., webhooks, email notifications) to the client.
5. **No real smart contract:** It is simulate with PostgreSQL. Code is implement to can switch to use web3. You can see on file [smart_contract_publisher.py](app/infrastructure/publishers/smart_contract_publisher.py) a first implementation, but it is not finish and not testing.
---

## How You Would Evolve the Solution to Production-Ready

To transition this proof-of-concept into a secure, robust, and highly scalable production system, the following roadmap is proposed:

### 1. Security & Infrastructure
- **Authentication & Authorization:** Secure all endpoints using standard protocols (JWT, API Keys, or OAuth2).
- **Cloud Migration & High Availability:** Deploy the application to a cloud provider (e.g., AWS, GCP) utilizing a Load Balancer to distribute traffic across multi-availability zone clusters.
- **Rate Limiting:** Implement API throttling (e.g., token bucket algorithm via Redis) to prevent system abuse.

### 2. Observability & Monitoring
- **Application Performance Monitoring (APM):** Integrate observability tools such as Sentry for error tracking, and New Relic or Datadog for real-time performance metrics and traces.
- **Structured Logging:** Implement standardized, structured JSON logging to facilitate centralized log management and querying (e.g., ELK stack or Grafana Loki).

### 3. Data Architecture & Scalability
- **Dedicated Summary Analytics Database:** The summary report details which assets were included or excluded (along with exclusion reasons). Querying this from PostgreSQL at scale will introduce significant delays. This data should be pre-computed and stored in a read-optimized data store or a fast document-store database.
- **CQRS & Event Streaming Architecture:** Under high-throughput conditions, the system should pivot to a **Command Query Responsibility Segregation (CQRS)** pattern. Utilizing **Apache Kafka** as an event streaming backbone would allow asynchronous, decoupled processing of asset ingestion (Command side) and aggregation queries (Query side). Python frameworks tailored for this, such as **Faust (Kafka Streams)**, should be evaluated for processing data streams in real-time.
- **Production-Grade Smart Contract Integration:** Transition from the current mocked/isolated ledger state into a fully realized blockchain integration wrapper, utilizing a real Ethereum provider node. The current architecture has been cleanly abstracted to make this swap seamless.
- **Verify audit hash:** To achieve ultimate trustlessness, the recommended production flow would be to provide clients with the exact hashing formula. This empowers them to download the raw assets locally and verify the cryptographic proof independently within their own infrastructure.

## Setup and usage instructions

```bash
cp .env.example .env
docker compose up --build
```

The API starts at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

### Insert assets

```bash
# Facility A — Educa Capital I
curl -X POST http://localhost:8000/api/v1/covenants/facility-a/assets \
  -H "Content-Type: application/json" \
  -d @data/facility_a_educa_isa.json

# Facility B — PayEarly US
curl -X POST http://localhost:8000/api/v1/covenants/facility-b/assets \
  -H "Content-Type: application/json" \
  -d @data/facility_b_payearly_ewa.json

# Facility C — Nomina Express I
curl -X POST http://localhost:8000/api/v1/covenants/facility-c/assets \
  -H "Content-Type: application/json" \
  -d @data/facility_c_nomina.json
```

### Retrieve a current facility state
```bash
# Facility B — PayEarly US
curl -X 'GET' \
  'http://localhost:8000/api/v1/covenants/facility-b/state' \
  -H 'accept: application/json'
```
### Generate new a report (Smart contract)

```bash
# Facility B — PayEarly US
curl -X 'POST' \
  'http://localhost:8000/api/v1/covenants/facility-b/reports?force=true' \
  -H 'accept: application/json' \
  -d ''
```

### Retrieve a report

```bash
# Facility B — PayEarly US
curl http://localhost:8000/api/v1/covenants/facility-b/reports/{report_id}
curl http://localhost:8000/api/v1/covenants/facility-b/reports
```

### Verify a report (Smart contract)

```bash
# Facility B — PayEarly US
curl -X 'GET' \
  'http://localhost:8000/api/v1/covenants/facility-b/reports/{report_id}/verify' \
  -H 'accept: application/json'
```

---

## Testing

```bash
# Unit + integration (SQLite in-memory)
pytest --cov=app --cov-fail-under=90

# Via Docker
docker compose run api pytest
```

---

## IA transcript

I used Claude Code with Sonnet 4.6 effort Hight.

The file [prompts.md](prompts.md) contains all the prompts I used.

the file [full_transcript_calude_code.md](full_transcript_calude_code.md) contains the full transcript obtained from the project.
