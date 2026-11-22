"""Config Flow: Lieblingsmannschaft auswählen."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import BBLApi, BBLApiError
from .const import CONF_TEAM_ID, CONF_TEAM_NAME, DOMAIN


class BBLConfigFlow(ConfigFlow, domain=DOMAIN):
    """Einrichtung über die Oberfläche."""

    VERSION = 1

    def __init__(self) -> None:
        self._teams: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            team_id = user_input[CONF_TEAM_ID]
            await self.async_set_unique_id(team_id)
            self._abort_if_unique_id_configured()
            name = self._teams.get(team_id, team_id)
            return self.async_create_entry(
                title=name,
                data={CONF_TEAM_ID: team_id, CONF_TEAM_NAME: name},
            )

        if not self._teams:
            try:
                self._teams = await BBLApi(async_get_clientsession(self.hass)).get_teams()
            except BBLApiError:
                errors["base"] = "cannot_connect"

        if errors:
            return self.async_show_form(
                step_id="user", data_schema=vol.Schema({}), errors=errors
            )

        options = [
            SelectOptionDict(value=team_id, label=name)
            for team_id, name in self._teams.items()
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_TEAM_ID): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
