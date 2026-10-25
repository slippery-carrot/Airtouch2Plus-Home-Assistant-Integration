# AirTouch 2+ Enhanced

A separately identifiable Home Assistant integration for Polyaire AirTouch 2+ controllers.

- **Domain:** `airtouch2plus_enhanced`
- **Entities:** climate, zone fan/damper, favourite select, console temperature sensors
- **Communications:** bundled modified `airtouch2` library incorporating aramshaw's reconnection and keep-alive work
- **Source:** https://github.com/slippery-carrot/Airtouch2Plus-Home-Assistant-Integration

For installation and migration details, see the [README](https://github.com/slippery-carrot/Airtouch2Plus-Home-Assistant-Integration/blob/feature/integration-rebrand/README.md). A full Home Assistant backup is recommended: the new domain creates new integration and device registrations rather than upgrading existing `airtouch2plus` entries in place.

Credits: [nathanvdh](https://github.com/nathanvdh), [aramshaw](https://github.com/aramshaw).
