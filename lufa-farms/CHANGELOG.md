# Changelog

## 0.2.8

- Fix: Implemented manual loading of S6 environment variables in Python. This bypasses the need for `with-contenv` (which causes errors) while still ensuring `SUPERVISOR_TOKEN` is available.

## 0.2.7

- Fix: Added fallback check for `HASSIO_TOKEN` if `SUPERVISOR_TOKEN` is missing.
- Debug: Added logging of environment variable keys to diagnose configuration issues.

## 0.2.6

- Fix: Restored `init: false` in `config.yaml`. This resolves the "s6-overlay-suexec: fatal: can only run as pid 1" error by preventing Supervisor from interfering with the base image's S6 init system.

## 0.2.5

- Fix: Removed `with-contenv` from startup script to resolve "pid 1" errors and environment variable loading issues.
- Note: This version relies on standard Docker environment variable injection (requires `hassio_api: true` from v0.2.4).

## 0.2.4

- Fix: Added `hassio_api: true` and `homeassistant_api: true` to `config.yaml` to ensure `SUPERVISOR_TOKEN` is injected.

## 0.2.3

- Fix: Switched to using `run.sh` with `with-contenv` to correctly load `SUPERVISOR_TOKEN` and MQTT service environment variables.

## 0.2.2

- Fix: Updated MQTT client to fetch configuration directly from Supervisor API (`http://supervisor/services/mqtt`). This fixes the "No MQTT configuration found" error when using auto-discovery.

## 0.2.1

- Fix: Missing `mqtt_client.py` in Docker image causing ModuleNotFoundError.

## 0.2.0

- **Feature**: Migrated to MQTT Discovery. The add-on now creates a "Lufa Farms" device in Home Assistant with all sensors grouped under it.
- **Feature**: Automatic MQTT configuration via Home Assistant Services (`mqtt:want`).
- **Breaking Change**: Removed direct Supervisor API sensor publishing. Requires MQTT broker.

## 0.1.3

- Fix: Missing import of `LufaClient` in `run.py` causing NameError.

## 0.1.2

- Fix: Switched to installing `requests` and `beautifulsoup4` via APK (`py3-requests`, `py3-beautifulsoup4`) to resolve PEP 668 build errors.

## 0.1.1

- Fix: Install `python3` and `pip3` in Dockerfile to fix build error.
- Fix: Ensure `client.py` is included in the build.
- Updated to remove `image` configuration to force local build.

## 0.1.0

- Initial release of the Lufa Farms Home Assistant Add-on.
- Features:
  - Automatic Order ID detection.
  - Sensors for Order Status, ETA, Stops Before, and Order Amount.
  - Native Home Assistant Supervisor API integration.
