import pytest

from app.application.registry import FacilityRegistry
from app.domain.errors import FacilityNotSupported
from app.domain.facility.interfaces import FacilityCalculator


class _FakeCalculator(FacilityCalculator):
    def calculate(  # type: ignore[override]
        self, raw_assets, facility_id, correlation_id
    ):
        raise NotImplementedError


class TestFacilityRegistry:
    def setup_method(self) -> None:
        self.registry = FacilityRegistry()
        self.calc = _FakeCalculator()

    def test_register_and_get(self) -> None:
        self.registry.register("facility-a", self.calc)
        assert self.registry.get("facility-a") is self.calc

    def test_get_unknown_facility_raises(self) -> None:
        with pytest.raises(FacilityNotSupported, match="facility-x"):
            self.registry.get("facility-x")

    def test_register_multiple_facilities(self) -> None:
        calc_b = _FakeCalculator()
        self.registry.register("facility-a", self.calc)
        self.registry.register("facility-b", calc_b)
        assert self.registry.get("facility-a") is self.calc
        assert self.registry.get("facility-b") is calc_b

    def test_overwrite_registration(self) -> None:
        calc2 = _FakeCalculator()
        self.registry.register("facility-a", self.calc)
        self.registry.register("facility-a", calc2)
        assert self.registry.get("facility-a") is calc2
