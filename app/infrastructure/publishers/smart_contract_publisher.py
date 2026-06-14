"""
Smart Contract Publisher — Web3 swap-in point.

This stub documents the exact interface a production Web3 implementation must
satisfy. When the team is ready to go on-chain:

  1. Install web3.py:  uv add web3
  2. Load the compiled ABI from artifacts/CovenantRegistry.json
  3. Replace the stub body of ``publish`` with the lines marked TODO below.
  4. Set PUBLISHER_BACKEND=smart_contract in the environment.

Contract interface (Solidity excerpt):
---------------------------------------
  interface ICovenantRegistry {
      /// Seal an auditable covenant record on-chain.
      /// @param facilityId   keccak256 of the facility identifier string.
      /// @param auditHash    SHA-256 of the canonical off-chain asset payload.
      /// @param effectiveRate Effective rate × 10**8 (e.g. 19.43% → 1943000000).
      /// @param status       0 = COMPLIANT, 1 = BREACH.
      /// @param timestamp    Unix epoch of report creation.
      function storeAuditRecord(
          bytes32 facilityId,
          bytes32 auditHash,
          uint256 effectiveRate,
          uint8   status,
          uint256 timestamp
      ) external returns (bytes32 txHash);

      /// Anyone can verify a previously stored record.
      function verifyAuditRecord(
          bytes32 facilityId,
          bytes32 auditHash
      ) external view returns (bool exists, uint256 storedAt);
  }

Event emitted by the contract:
  AuditRecordStored(
      bytes32 indexed facilityId,
      bytes32 indexed auditHash,
      uint256 effectiveRate,
      uint8   status,
      uint256 timestamp
  )

Verification flow for Capital Provider / Asset Originator:
  1. Call GET /api/v1/covenants/{facility_id}/reports/{report_id}/verify
     → receives stored_hash and computed_hash
  2. Call contract.functions.verifyAuditRecord(facilityId, stored_hash).call()
     → confirms the hash is on-chain (existence proof)
  3. Compare computed_hash == stored_hash to confirm data integrity
"""

import logging
from decimal import Decimal

from app.domain.covenant.entities import CovenantReport, CovenantStatus
from app.domain.publishers.interface import Publisher

logger = logging.getLogger(__name__)

_STATUS_UINT = {CovenantStatus.COMPLIANT: 0, CovenantStatus.BREACH: 1}
_RATE_SCALE = Decimal("1e8")


class SmartContractPublisher(Publisher):
    """
    Production swap-in for publishing covenant reports to an on-chain
    CovenantRegistry smart contract.

    Constructor would accept:
        web3: Web3          — connected node (e.g. Infura, Alchemy)
        contract_address: str
        private_key: str    — loaded from env, never hardcoded
        chain_id: int
    """

    def publish(self, report: CovenantReport) -> None:
        facility_id_bytes = report.facility_id.encode("utf-8").ljust(32, b"\x00")[:32]
        audit_hash_bytes = (
            bytes.fromhex(report.audit_hash) if report.audit_hash else b"\x00" * 32
        )
        rate_uint = int(
            (Decimal(str(report.effective_rate)) * _RATE_SCALE).to_integral_value()
        )
        status_uint = _STATUS_UINT[report.status]

        # TODO (Web3 implementation):
        #
        # contract = web3.eth.contract(
        #     address=Web3.to_checksum_address(self._contract_address),
        #     abi=COVENANT_REGISTRY_ABI,
        # )
        # tx = contract.functions.storeAuditRecord(
        #     facility_id_bytes,
        #     audit_hash_bytes,
        #     rate_uint,
        #     status_uint,
        #     int(report.computed_at.timestamp()),
        # ).build_transaction({
        #     "from": self._account.address,
        #     "nonce": web3.eth.get_transaction_count(self._account.address),
        #     "gas": 200_000,
        #     "maxFeePerGas": web3.eth.gas_price,
        # })
        # signed = web3.eth.account.sign_transaction(tx, self._private_key)
        # tx_hash = web3.eth.send_raw_transaction(signed.rawTransaction)
        # receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
        # tx_hash_hex = receipt.transactionHash.hex()
        # logger.info("on-chain tx confirmed", extra={"tx_hash": tx_hash_hex})

        logger.info(
            "SmartContractPublisher: would call storeAuditRecord (stub)",
            extra={
                "facility_id": report.facility_id,
                "report_id": str(report.report_id),
                "correlation_id": report.correlation_id,
                "audit_hash": report.audit_hash,
                "status": report.status.value,
                "effective_rate": str(report.effective_rate),
                "facility_id_bytes32": facility_id_bytes.hex(),
                "audit_hash_bytes32": audit_hash_bytes.hex(),
                "rate_uint": rate_uint,
                "status_uint": status_uint,
            },
        )
