# Changelog

## 1.0.1
- **Fix**: Switched base Docker image from Alpine (HA default) to `python:3.11-slim-bookworm` (Debian).
- **Reason**: Playwright requires `glibc` and is not compatible with Alpine Linux (`musl`). This resolves the `apt-get: not found` error during build.

## 1.0.0
- Initial release.
