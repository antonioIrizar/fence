import hashlib
import json
from decimal import Decimal

from app.domain.asset.record import AssetRecord
from app.domain.covenant.state import FacilityCovenantState


def compute_asset_hash(
    facility_id: str,
    assets: list[AssetRecord],
    state: FacilityCovenantState,
) -> str:
    """
    Deterministic SHA-256 fingerprint of a facility's data at a point in time.

    Covers: every asset's financial fields, eligibility verdict, contribution
    components, ingestion timestamp, plus the covenant state's accumulated
    totals and computed rate. Sorting assets by external_id makes the output
    independent of query order.

    Capital Providers and Asset Originators call verify_report to re-run this
    computation against live data and compare with the stored hash. Any
    discrepancy proves post-report tampering.
    """
    sorted_assets = sorted(assets, key=lambda a: a.external_id)

    payload: dict[str, object] = {
        "facility_id": facility_id,
        "covenant_state": {
            "effective_rate": str(Decimal(str(state.effective_rate)).normalize()),
            "covenant_status": state.covenant_status.value,
            "accumulated_numerator": str(
                Decimal(str(state.accumulated_numerator)).normalize()
            ),
            "accumulated_denominator": str(
                Decimal(str(state.accumulated_denominator)).normalize()
            ),
        },
        "assets": [
            {
                "external_id": a.external_id,
                "amount": str(Decimal(str(a.amount)).normalize()),
                "is_eligible_asset": a.is_eligible_asset,
                "exclusion_reasons": sorted(a.exclusion_reasons),
                "contribution_numerator": (
                    str(Decimal(str(a.contribution_numerator)).normalize())
                    if a.contribution_numerator is not None
                    else None
                ),
                "contribution_denominator": (
                    str(Decimal(str(a.contribution_denominator)).normalize())
                    if a.contribution_denominator is not None
                    else None
                ),
                "ingested_at": a.ingested_at.isoformat(),
            }
            for a in sorted_assets
        ],
    }

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
