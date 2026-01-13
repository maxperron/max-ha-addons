# Changelog

## 1.0.11
- **Fix**: Relaxed filtering for planned workouts to rely on `category="WORKOUT"` instead of presence of `type`, ensuring all future workouts are captured.
- **Fix**: Added debug logging for Intervals event processing.

- **Feature**: Full support for 7-day planned workout forecast using Intervals `/events` endpoint.
- **Fix**: Correctly separated history (Activities/Wellness) from future (Planned Workouts) to avoid mixed data confusion.
- **Fix**: Fixed issue where planned workout descriptions were missing.

## 1.0.9
- **Internal.icu Sync**: Added fetching of Wellness data (Fitness, Fatigue, Form, RestingHR, HRV).
- **Internal.icu Sync**: Now fetches planned workouts for the next 7 days.
- **Internal.icu Sync**: Improved description extraction to prioritize planned workout steps.
- **Fix**: Resolved `SyntaxError` in Intervals sync module preventing startup.

## 1.0.8
- **Fix**: Added explicit wait for successful login navigation before attempting to access Insights page to prevent `invalid state` errors.

## 1.0.7
- **Fix**: Updated LoseIt login selectors (`#email`, `#password`, `Log In` button) based on browser agent verification to resolve login failures.

## 1.0.6
- **Debug**: Added detailed step-by-step logging to LoseIt scraper to diagnose navigation failures.
- **Feature**: Enhanced CSV parser to map specific LoseIt export columns (Food Item, Meal, Macros) and generate unique IDs for safe upserts.

## 1.0.5
- **Feature**: Updated LoseIt sync to target specific "Daily Summary" insights page and trigger CSV export via "Export to spreadsheet" link.

## 1.0.4
- **Dependency**: Upgraded `garminconnect` library to `>=0.2.16` to fix login issues caused by recent Garmin API changes ("NoneType" error).

## 1.0.3
- **Debug**: Enhanced Garmin logging to print obscured email and full exception traceback for login failures.

## 1.0.2
- **Fix**: Resolved "NoneType is not subscriptable" error in Garmin Sync by improving error handling when login fails.
- **Fix**: Resolved "unsupported operand type" error in Intervals Sync by handling null values for duration/distance.
- **Fix**: Resolved "str object has no attribute get" in Google Sheets Sync by fixing credential parsing logic (handling strings vs dicts).

## 1.0.1
- **Fix**: Switched base Docker image from Alpine (HA default) to `python:3.11-slim-bookworm` (Debian).
- **Reason**: Playwright requires `glibc` and is not compatible with Alpine Linux (`musl`). This resolves the `apt-get: not found` error during build.

## 1.0.0
- Initial release.
