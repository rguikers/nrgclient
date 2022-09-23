"""
Support for Azure IoT Hub.
"""
from datetime import timedelta
from email.policy import default
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import (
    async_track_state_change,
    async_track_time_interval,
)
from homeassistant.const import MATCH_ALL
from homeassistant.core import callback
from homeassistant.util import slugify
from .pnp_helper import create_reported_properties, create_telemetry

REQUIREMENTS = ["azure-iot-device"]

DOMAIN = "nrg_client"

ATTR_NAME = "name"
DEFAULT_NAME = "NRG Client"

SEND_CALLBACKS = 0

_LOGGER = logging.getLogger(__name__)
CONF_LOG_LEVEL = "log_level"

CONF_CONNECTSTRING = "connectstring"
CONF_INTERVAL = "interval"
CONF_TELEMETRY = "telemetry"
CONF_SPEC = "spec"

CONF_SOLAR = "solar"
CONF_SOLAR_YIELD = "solar_yield"
CONF_SOLAR_STATE = "solar_state"
CONF_SOLAR_SPEC_CAPACITY_PER_PANEL = "solar_spec_capacity_per_panel"
CONF_SOLAR_SPEC_PANEL_AMOUNT = "solar_spec_panel_amount"
CONF_SOLAR_SPEC_PANEL_AREA = "solar_spec_panel_area"
CONF_SOLAR_SPEC_PANEL_AZIMUTH = "solar_spec_panel_azimuth"
CONF_SOLAR_SPEC_PANEL_TILT = "solar_spec_panel_tilt"
CONF_BATTERY = "battery"
CONF_BATTERY_CURRENT_CHARGE_RATE = "battery_current_charge_rate"
CONF_BATTERY_CURRENT_DISCHARGE_RATE = "battery_current_discharge_rate"
CONF_BATTERY_CHARGE_LEVEL = "battery_charge_level"
CONF_BATTERY_SPEC_SIZE = "battery_spec_size"
CONF_BATTERY_SPEC_EFFICIENCY = "battery_spec_efficiency"
CONF_BATTERY_SPEC_DISCHARGE_RATE = "battery_spec_discharge_rate"
CONF_BATTERY_SPEC_CHARGE_RATE = "battery_spec_charge_rate"
CONF_SMARTMETER = "smartmeter"
CONF_SMARTMETER_TOTAL_FEEDOUT = "smartmeter_total_feedout"
CONF_SMARTMETER_TOTAL_FEEDIN = "smartmeter_total_feedin"
CONF_SMARTMETER_CURRENT_FEEDOUT = "smartmeter_current_feedout"
CONF_SMARTMETER_CURRENT_FEEDIN = "smartmetercurrentl_feedin"
CONF_SMARTMETER_TOTAL_GASCONSUMPTION = "smartmeter_total_gas_consumption"
CONF_SMARTMETER_CURRENT_GASCONSUMPTION = "smartmeter_current_gas_consumption"

CONF_SMARTMETER_SPEC_TYPE = "smartmeter_spec_type"
CONF_SMARTMETER_SPEC_VERSION = "smartmeter_spec_version"

CONF_THERMOSTAT = "thermostat"
CONF_THERMOSTAT_TEMPERATURE = "thermostat_temperature"
CONF_THERMOSTAT_SETPOINT_TEMP = "thermostat_setpoint_temp"
# client = {}

# Kolla scripts.py
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CONNECTSTRING): cv.string,
                vol.Required(CONF_INTERVAL, default=30): cv.positive_int,
                vol.Optional(CONF_LOG_LEVEL, default=0): cv.positive_int,
                vol.Optional(CONF_SOLAR): vol.Schema(
                    {
                        CONF_TELEMETRY: vol.Schema(
                            {
                                vol.Optional(CONF_SOLAR_YIELD): cv.string,
                            }
                        ),
                        CONF_SPEC: vol.Schema(
                            {
                                vol.Optional(CONF_SOLAR_SPEC_PANEL_AMOUNT): cv.string,
                                vol.Optional(CONF_SOLAR_SPEC_PANEL_AREA): cv.string,
                                vol.Optional(
                                    CONF_SOLAR_SPEC_CAPACITY_PER_PANEL
                                ): cv.string,
                                vol.Optional(CONF_SOLAR_SPEC_PANEL_AZIMUTH): cv.string,
                                vol.Optional(CONF_SOLAR_SPEC_PANEL_TILT): cv.string,
                            }
                        ),
                    }
                ),
                CONF_BATTERY: vol.Schema(
                    {
                        CONF_TELEMETRY: vol.Schema(
                            {
                                vol.Optional(CONF_BATTERY_CHARGE_LEVEL): cv.string,
                                vol.Optional(
                                    CONF_BATTERY_CURRENT_CHARGE_RATE
                                ): cv.string,
                                vol.Optional(
                                    CONF_BATTERY_CURRENT_DISCHARGE_RATE
                                ): cv.string,
                            }
                        ),
                        CONF_SPEC: vol.Schema(
                            {
                                vol.Optional(CONF_BATTERY_SPEC_CHARGE_RATE): cv.string,
                                vol.Optional(
                                    CONF_BATTERY_SPEC_DISCHARGE_RATE
                                ): cv.string,
                                vol.Optional(CONF_BATTERY_SPEC_EFFICIENCY): cv.string,
                                vol.Optional(CONF_BATTERY_SPEC_SIZE): cv.string,
                            }
                        ),
                    }
                ),
                CONF_SMARTMETER: vol.Schema(
                    {
                        CONF_TELEMETRY: vol.Schema(
                            {
                                vol.Optional(CONF_SMARTMETER_CURRENT_FEEDIN): cv.string,
                                vol.Optional(
                                    CONF_SMARTMETER_CURRENT_FEEDOUT
                                ): cv.string,
                                vol.Optional(CONF_SMARTMETER_TOTAL_FEEDIN): cv.string,
                                vol.Optional(CONF_SMARTMETER_TOTAL_FEEDOUT): cv.string,
                                vol.Optional(
                                    CONF_SMARTMETER_CURRENT_GASCONSUMPTION
                                ): cv.string,
                                vol.Optional(
                                    CONF_SMARTMETER_TOTAL_GASCONSUMPTION
                                ): cv.string,
                            }
                        ),
                        CONF_SPEC: vol.Schema(
                            {
                                vol.Optional(CONF_SMARTMETER_SPEC_TYPE): cv.string,
                                vol.Optional(CONF_SMARTMETER_SPEC_VERSION): cv.string,
                            }
                        ),
                    }
                ),
                CONF_THERMOSTAT: vol.Schema(
                    {
                        CONF_TELEMETRY: vol.Schema(
                            {
                                vol.Optional(CONF_THERMOSTAT_TEMPERATURE): cv.string,
                                vol.Optional(CONF_THERMOSTAT_SETPOINT_TEMP): cv.string,
                            }
                        )
                    }
                ),
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""
    from azure.iot.device.aio import IoTHubDeviceClient
    from azure.iot.device import Message
    import asyncio
    import uuid

    async def nrg_client_init(config):

        conn = config[DOMAIN].get(CONF_CONNECTSTRING)
        # _LOGGER.info("Device connection using connection string {}".format(conn))
        device_client = IoTHubDeviceClient.create_from_connection_string(conn)
        # Connect the client.
        # client = await device_client.connect()
        return device_client

    async def _push_specs(client):
        _LOGGER.debug("Pushing specs")
        if CONF_BATTERY in config[DOMAIN]:
            if CONF_SPEC in config[DOMAIN][CONF_BATTERY]:
                # create spec reading
                battery_patch = create_reported_properties(
                    "battery",
                    chargeRate=config[DOMAIN][CONF_BATTERY][CONF_SPEC][
                        CONF_BATTERY_SPEC_CHARGE_RATE
                    ],
                    dischargeRate=config[DOMAIN][CONF_BATTERY][CONF_SPEC][
                        CONF_BATTERY_SPEC_DISCHARGE_RATE
                    ],
                    efficiency=config[DOMAIN][CONF_BATTERY][CONF_SPEC][
                        CONF_BATTERY_SPEC_EFFICIENCY
                    ],
                    size=config[DOMAIN][CONF_BATTERY][CONF_SPEC][
                        CONF_BATTERY_SPEC_SIZE
                    ],
                )
                await client.patch_twin_reported_properties(battery_patch)
        if CONF_SOLAR in config[DOMAIN]:
            if CONF_SPEC in config[DOMAIN][CONF_SOLAR]:
                # create spec reading
                solar_patch = create_reported_properties(
                    "solar",
                    capacityPerPanel=config[DOMAIN][CONF_SOLAR][CONF_SPEC][
                        CONF_SOLAR_SPEC_CAPACITY_PER_PANEL
                    ],
                    panelArea=config[DOMAIN][CONF_SOLAR][CONF_SPEC][
                        CONF_SOLAR_SPEC_PANEL_AREA
                    ],
                    panelAzimuth=config[DOMAIN][CONF_SOLAR][CONF_SPEC][
                        CONF_SOLAR_SPEC_PANEL_AZIMUTH
                    ],
                    panelTilt=config[DOMAIN][CONF_SOLAR][CONF_SPEC][
                        CONF_SOLAR_SPEC_PANEL_TILT
                    ],
                )
                await client.patch_twin_reported_properties(solar_patch)
        if CONF_SMARTMETER in config[DOMAIN]:
            if CONF_SPEC in config[DOMAIN][CONF_SMARTMETER]:
                # create spec reading
                smartmeter_patch = create_reported_properties(
                    "smartmeter",
                    type=config[DOMAIN][CONF_SMARTMETER][CONF_SPEC][
                        CONF_SMARTMETER_SPEC_TYPE
                    ],
                    version=config[DOMAIN][CONF_SMARTMETER][CONF_SPEC][
                        CONF_SMARTMETER_SPEC_VERSION
                    ],
                )
                await client.patch_twin_reported_properties(smartmeter_patch)

    async def _add_sensor_state(msg, element, sensor):
        sensor_state = hass.states.get(sensor)
        if sensor_state:
            msg[element] = sensor_state.state

    async def _push_telemetry(now):
        # push telemetry
        # connect client

        client = await nrg_client_init(config)
        _LOGGER.debug("Pushing telemetry")

        # battery
        if CONF_BATTERY in config[DOMAIN]:
            battery_msg = {}
            await _add_sensor_state(
                battery_msg,
                "currentChargeRate",
                config[DOMAIN][CONF_BATTERY][CONF_TELEMETRY][
                    CONF_BATTERY_CURRENT_CHARGE_RATE
                ],
            )
            await _add_sensor_state(
                battery_msg,
                "currentDischargeRate",
                config[DOMAIN][CONF_BATTERY][CONF_TELEMETRY][
                    CONF_BATTERY_CURRENT_DISCHARGE_RATE
                ],
            )
            await _add_sensor_state(
                battery_msg,
                "chargeLevel",
                config[DOMAIN][CONF_BATTERY][CONF_TELEMETRY][CONF_BATTERY_CHARGE_LEVEL],
            )

            patch = create_telemetry(
                battery_msg,
                "battery",
            )
            await client.send_message(patch)
        if CONF_SOLAR in config[DOMAIN]:
            solar_msg = {}
            await _add_sensor_state(
                solar_msg,
                "yield",
                config[DOMAIN][CONF_SOLAR][CONF_TELEMETRY][CONF_SOLAR_YIELD],
            )
            patch = create_telemetry(
                solar_msg,
                "solar",
            )
            await client.send_message(patch)
        if CONF_SMARTMETER in config[DOMAIN]:
            smartmeter_msg = {}
            await _add_sensor_state(
                smartmeter_msg,
                "totalFeedOut",
                config[DOMAIN][CONF_SMARTMETER][CONF_TELEMETRY][
                    CONF_SMARTMETER_TOTAL_FEEDOUT
                ],
            )
            await _add_sensor_state(
                smartmeter_msg,
                "totalFeedIn",
                config[DOMAIN][CONF_SMARTMETER][CONF_TELEMETRY][
                    CONF_SMARTMETER_TOTAL_FEEDIN
                ],
            )
            await _add_sensor_state(
                smartmeter_msg,
                "currentFeedOut",
                config[DOMAIN][CONF_SMARTMETER][CONF_TELEMETRY][
                    CONF_SMARTMETER_CURRENT_FEEDOUT
                ],
            )
            await _add_sensor_state(
                smartmeter_msg,
                "currentFeedIn",
                config[DOMAIN][CONF_SMARTMETER][CONF_TELEMETRY][
                    CONF_SMARTMETER_CURRENT_FEEDIN
                ],
            )
            await _add_sensor_state(
                smartmeter_msg,
                "totalGasConsumption",
                config[DOMAIN][CONF_SMARTMETER][CONF_TELEMETRY][
                    CONF_SMARTMETER_TOTAL_GASCONSUMPTION
                ],
            )
            await _add_sensor_state(
                smartmeter_msg,
                "currentGasConsumption",
                config[DOMAIN][CONF_SMARTMETER][CONF_TELEMETRY][
                    CONF_SMARTMETER_CURRENT_GASCONSUMPTION
                ],
            )
            patch = create_telemetry(
                smartmeter_msg,
                "smartmeter",
            )
            await client.send_message(patch)
        if CONF_THERMOSTAT in config[DOMAIN]:
            thermostat_msg = {}
            await _add_sensor_state(
                thermostat_msg,
                "temperature",
                config[DOMAIN][CONF_THERMOSTAT][CONF_TELEMETRY][
                    CONF_THERMOSTAT_TEMPERATURE
                ],
            )
            await _add_sensor_state(
                thermostat_msg,
                "setPointTemp",
                config[DOMAIN][CONF_THERMOSTAT][CONF_TELEMETRY][
                    CONF_THERMOSTAT_SETPOINT_TEMP
                ],
            )
            patch = create_telemetry(
                thermostat_msg,
                "thermostat",
            )
            await client.send_message(patch)

        # disconnect client
        await client.disconnect()

    # # Initialize devices
    client = await nrg_client_init(config)
    await _push_specs(client)
    await client.disconnect()
    async_track_time_interval(
        hass, _push_telemetry, timedelta(seconds=config[DOMAIN][CONF_INTERVAL])
    )
    # Return boolean to indicate that initialization was successfully.
    _LOGGER.info("NRG Client started")
    return True
