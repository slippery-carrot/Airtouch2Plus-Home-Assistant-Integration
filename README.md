# AirTouch 2+ Enhanced

An independently named Home Assistant custom integration for Polyaire AirTouch 2+ systems, maintained at [slippery-carrot/Airtouch2Plus-Home-Assistant-Integration](https://github.com/slippery-carrot/Airtouch2Plus-Home-Assistant-Integration).

Based on [aramshaw's reliability-focused fork](https://github.com/aramshaw/homeassistant-airtouch2plus) of [nathanvdh's original integration](https://github.com/nathanvdh/homeassistant-airtouch2plus).

## Features

- Climate control (operating mode, setpoint and fan speed)
- AirTouch zone dampers exposed as fan entities
- AirTouch favourites exposed as a select entity
- Console temperature sensors
- TCP connection status and current-session uptime diagnostics (no extra controller polling)
- Bundled modified `airtouch2` library with status acknowledgements, periodic keep-alive status polls, and reconnect handling
- HA entities report unavailable during detected controller disconnections

## Installation (development branch)

1. Back up Home Assistant before replacing an existing AirTouch integration.
2. Add `https://github.com/slippery-carrot/Airtouch2Plus-Home-Assistant-Integration` to HACS as a custom **Integration** repository.
3. For this unreleased change, choose branch `feature/integration-rebrand` if your HACS version allows selecting a branch; otherwise manually copy the `custom_components/airtouch2plus_enhanced` folder from that branch into Home Assistant's `config/custom_components`.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration**, search for **AirTouch 2+ Enhanced**, and enter the controller IP address.

The integration is installed at `custom_components/airtouch2plus_enhanced` with domain `airtouch2plus_enhanced`.

**Migration:** This is deliberately a *different integration*, not an in-place upgrade from `airtouch2plus`. Existing config entries and entity-registry associations do not automatically move. Check the new entity IDs before changing any dashboards or damper-control automations. To avoid conflicting sessions, do not leave both integrations active during testing.

## Connection diagnostics (development)

The AirTouch device exposes **TCP connection** (connected/disconnected) and **TCP connection uptime** (duration in seconds, refreshed once per minute). The uptime resets if the connection is lost and starts again after reconnecting, including following an integration restart. The connectivity state reflects the library's socket tracking; it is not yet a proof that application-level status responses are arriving. A frozen or half-open connection may still appear connected until a network error is detected.

## Development and acknowledgements

This rebrand retains existing controller-protocol code and entity unique-ID patterns, while changing the Home Assistant integration identity. Please report problems to [this repository's issues](https://github.com/slippery-carrot/Airtouch2Plus-Home-Assistant-Integration/issues).

Original integration by [nathanvdh](https://github.com/nathanvdh). TCP reliability work, favourites and console temperatures by [aramshaw](https://github.com/aramshaw).
