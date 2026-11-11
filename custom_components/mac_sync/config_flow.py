"""Config flow for Mac Sync."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class MacSyncConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-step config flow; the Mac app pushes data to us."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            return self.async_create_entry(title="Mac Sync", data={})
        return self.async_show_form(step_id="user")
