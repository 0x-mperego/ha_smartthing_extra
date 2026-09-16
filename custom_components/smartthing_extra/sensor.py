from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.components.smartthings.const import DOMAIN as ST_DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from pysmartthings import DeviceEvent

CAP_TIMER = "samsungce.countDownTimer"
CAP_HEAT = "samsungce.surfaceResidualHeat"
HEAT_ATTR = "surfaceResidualHeat"


def _find_smartthings_entry(hass: HomeAssistant) -> ConfigEntry | None:
    for entry in hass.config_entries.async_entries(ST_DOMAIN):
        if entry.state == ConfigEntryState.LOADED:
            return entry
    return None


def _key(value: Any) -> str:
    return getattr(value, "value", value)


def _find_key(mapping: dict[Any, Any], wanted: str) -> Any | None:
    return next((key for key in mapping if _key(key) == wanted), None)


def _iter_cooktop_components(device: Any):
    status = getattr(device, "status", {}) or {}
    for component, component_status in status.items():
        if not component.startswith("burner-"):
            continue
        if _find_key(component_status, CAP_TIMER) is not None or _find_key(component_status, CAP_HEAT) is not None:
            yield component, component_status


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    st_entry = _find_smartthings_entry(hass)
    if st_entry is None or not st_entry.runtime_data:
        return

    entities: list[SensorEntity] = []
    client = st_entry.runtime_data.client

    for device in st_entry.runtime_data.devices.values():
        device_info = getattr(device, "device", None)
        label = getattr(device_info, "label", "") or getattr(device_info, "name", "") or ""
        device_type = getattr(device_info, "device_type_name", "") or ""
        model = getattr(device_info, "model", "") or ""
        if "cooktop" not in f"{label} {device_type} {model}".lower() and model != "NZ64B5066KK":
            continue

        for component, component_status in _iter_cooktop_components(device):
            timer_key = _find_key(component_status, CAP_TIMER)
            heat_key = _find_key(component_status, CAP_HEAT)
            zone = int(component.split("-")[-1])

            if timer_key is not None:
                timer = component_status[timer_key]
                for attribute, suffix, name, icon, unit in (
                    ("currentValue", "timer_remaining", "timer residuo", "mdi:timer-sand", "min"),
                    ("startValue", "timer_set", "timer impostato", "mdi:timer-cog-outline", "min"),
                    ("status", "timer_status", "stato timer", "mdi:timer-outline", None),
                ):
                    attribute_key = _find_key(timer, attribute)
                    if attribute_key is not None:
                        entities.append(
                            SmartThingsExtraSensor(
                                client, device, component, timer_key, attribute_key,
                                SensorEntityDescription(
                                    key=f"{component}_{suffix}",
                                    name=f"Zona {zone} {name}",
                                    native_unit_of_measurement=unit,
                                    icon=icon,
                                ),
                            )
                        )

            if heat_key is not None:
                heat = component_status[heat_key]
                attribute_key = _find_key(heat, HEAT_ATTR)
                if attribute_key is not None:
                    entities.append(
                        SmartThingsExtraSensor(
                            client, device, component, heat_key, attribute_key,
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
        capability: Any,
        attribute: Any,
        description: SensorEntityDescription,
    ) -> None:
        self.entity_description = description
        self._client = client
        self._device = device
        self._component = component
        self._capability = capability
        self._attribute = attribute
        self._attr_unique_id = f"{device.device.device_id}_{component}_{_key(capability)}_{_key(attribute)}"
        self._attr_device_info = DeviceInfo(identifiers={(ST_DOMAIN, device.device.device_id)})
        self._attr_available = device.online
        self._attr_native_value = self._read_value()

    def _read_value(self) -> Any:
        try:
            return self._device.status[self._component][self._capability][self._attribute].value
        except (KeyError, TypeError, AttributeError):
            return None

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
        if _key(event.attribute) != _key(self._attribute):
            return
        self._attr_native_value = event.value
        self.async_write_ha_state()
