from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.components.smartthings.const import DOMAIN as ST_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from pysmartthings import DeviceEvent

DOMAIN = "smartthing_extra"

CAP_TIMER = "samsungce.countDownTimer"
CAP_HEAT = "samsungce.surfaceResidualHeat"
TIMER_ATTRS = ("startValue", "currentValue", "status")
HEAT_ATTR = "surfaceResidualHeat"


def _find_smartthings_entry(hass: HomeAssistant) -> ConfigEntry | None:
    for entry in hass.config_entries.async_entries(ST_DOMAIN):
        if entry.state == ConfigEntryState.LOADED:
            return entry
    return None


def _iter_cooktop_components(device: Any):
    status = getattr(device, "status", {}) or {}
    for component, component_status in status.items():
        if not component.startswith("burner-"):
            continue
        if CAP_TIMER in component_status or CAP_HEAT in component_status:
            yield component, component_status


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    st_entry = _find_smartthings_entry(hass)
    if st_entry is None or not st_entry.runtime_data:
        return

    entities: list[SensorEntity] = []
    client = st_entry.runtime_data.client

    for device in st_entry.runtime_data.devices:
        device_info = getattr(device, "device", None)
        label = getattr(device_info, "label", "") or getattr(device_info, "name", "") or ""
        device_type = getattr(device_info, "device_type_name", "") or ""
        if "cooktop" not in f"{label} {device_type}".lower():
            continue

        for component, component_status in _iter_cooktop_components(device):
            timer = component_status.get(CAP_TIMER, {})
            heat = component_status.get(CAP_HEAT, {})
            zone = int(component.split("-")[-1])

            if timer:
                entities.append(
                    SmartThingsExtraSensor(
                        client,
                        device,
                        component,
                        zone,
                        CAP_TIMER,
                        "currentValue",
                        SensorEntityDescription(
                            key=f"{component}_timer_remaining",
                            name=f"Zona {zone} timer residuo",
                            native_unit_of_measurement="min",
                            icon="mdi:timer-sand",
                        ),
                    )
                )
                entities.append(
                    SmartThingsExtraSensor(
                        client,
                        device,
                        component,
                        zone,
                        CAP_TIMER,
                        "startValue",
                        SensorEntityDescription(
                            key=f"{component}_timer_set",
                            name=f"Zona {zone} timer impostato",
                            native_unit_of_measurement="min",
                            icon="mdi:timer-cog-outline",
                        ),
                    )
                )
                entities.append(
                    SmartThingsExtraSensor(
                        client,
                        device,
                        component,
                        zone,
                        CAP_TIMER,
                        "status",
                        SensorEntityDescription(
                            key=f"{component}_timer_status",
                            name=f"Zona {zone} stato timer",
                            icon="mdi:timer-outline",
                        ),
                    )
                )

            if heat:
                entities.append(
                    SmartThingsExtraSensor(
                        client,
                        device,
                        component,
                        zone,
                        CAP_HEAT,
                        HEAT_ATTR,
                        SensorEntityDescription(
                            key=f"{component}_residual_heat",
                            name=f"Zona {zone} calore residuo",
                            icon="mdi:heat-wave",
                        ),
                    )
                )

    async_add_entities(entities)


class SmartThingsExtraSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        client: Any,
        device: Any,
        component: str,
        zone: int,
        capability: str,
        attribute: str,
        description: SensorEntityDescription,
    ) -> None:
        self.entity_description = description
        self._client = client
        self._device = device
        self._component = component
        self._capability = capability
        self._attribute = attribute
        self._attr_unique_id = (
            f"{device.device.device_id}_{component}_{capability}_{attribute}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(ST_DOMAIN, device.device.device_id)}
        )
        self._attr_native_value = self._read_value()

    def _read_value(self) -> Any:
        try:
            value = self._device.status[self._component][self._capability][
                self._attribute
            ].value
        except (KeyError, TypeError, AttributeError):
            return None
        return value

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._client.add_device_capability_event_listener(
                self._device.device.device_id,
                self._component,
                self._capability,
                self._handle_event,
            )
        )

    @callback
    def _handle_event(self, event: DeviceEvent) -> None:
        if event.attribute != self._attribute:
            return
        self._attr_native_value = event.value
        self.async_write_ha_state()
