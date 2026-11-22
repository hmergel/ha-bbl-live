"""Basisklasse für BBL-Entitäten."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BASE_URL, CONF_TEAM_NAME, DOMAIN
from .coordinator import BBLCoordinator


class BBLEntity(CoordinatorEntity[BBLCoordinator]):
    """Gemeinsame Geräte-Infos für alle Entitäten einer Mannschaft."""

    _attr_has_entity_name = True
    _attr_attribution = "Daten: easycredit-bbl.de"

    def __init__(self, coordinator: BBLCoordinator, key: str) -> None:
        super().__init__(coordinator)
        team_id = coordinator.team_id
        self._attr_unique_id = f"{team_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, team_id)},
            name=coordinator.config_entry.data.get(CONF_TEAM_NAME, f"BBL {team_id}"),
            manufacturer="easyCredit Basketball Bundesliga",
            model="BBL-Mannschaft",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"{BASE_URL}/teams/{team_id}",
        )
