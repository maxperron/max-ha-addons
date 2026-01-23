# Changelog

## 1.0.67
- **Fix**: Updated Aria weight parsing to use Little Endian (`<I`) instead of Big Endian, matching the protocol details from reliable sources (Wayne Piekarski's blog).

## 1.0.66
- **Fix**: Aria handler now reads `request.get_data()` *before* any other request properties to prevent Flask's form parser from consuming the binary stream due to misleading Content-Type headers.

## 1.0.65
- **Fix**: Adjusted Aria handler to read raw request body if `dump` file is missing (handles Aria sending x-www-form-urlencoded with binary body).

## 1.0.64
- **Fix**: Resolved startup crash caused by duplicate route definition in `main.py`.

## 1.0.63
- **Changed**: Removed Fitbit data forwarding (user request). Aria data is now *only* sent to Garmin.

## 1.0.62
- **Feature**: Implemented full support for Aria scale data. Packets are parsed (weight in grams at 0x36) and uploaded to Garmin.
- **Feature**: Added forwarding of scale data to Fitbit servers to maintain official history.

## 1.0.61
- **Debug**: Enhanced Aria logging to print raw bytes (`repr`) of the request body to diagnose data format.

## 1.0.60
- **Fix**: Added unbuffered output flag (`python -u`) to `run.sh` to ensure logs appear in real-time.

## 1.0.59
- **Feature**: Added web server on port 8000 to receive Fitbit Aria scale data.
- **Dependency**: Added Flask to support the web server.

## 1.0.58
- Fixed Garmin Readiness and Training Status extraction logic (handling lists and nested keys).

## 1.0.57
- Refined Garmin Hydration sync.
- Added debug logging for Training Readiness and Training Status to diagnose empty values.

## 1.0.56
- Fix Google Sheets Date formatting (enforced `USER_ENTERED`).
- Add Garmin Training Readiness, Training Status, and Hydration sync.

## 1.0.55
- Reordered Intervals sync to process Wellness data BEFORE Activities.
- added logging to `get_activities`.

## 1.0.54
- Add extensive debug logging to `gsheets_sync.py` to trace missing columns issue.

## 1.0.53
- Add `Intervals_Form` (Absolute) metric to Google Sheets sync.
- Refine Intervals wellness data mapping.

## 1.0.52
- **Fix**: Updated Garmin sync to fetch Weight from `get_body_composition` endpoint instead of `user_summary` (which was returning None).
- **Fix**: Logic added to handle body composition response (grams to kg conversion) and fallback.

## 1.0.51
- **Fix**: Changed default value for missing Garmin data (Weight, HR, Sleep) from empty string (`""`) to `None`. This prevents the sync from overwriting existing data (e.g. from other sources) with blank values during the merge process.

## 1.0.50
- **Fix**: Upgraded `garminconnect` library to `>=0.2.24` to resolve login `AssertionError` caused by Garmin API changes (profile dict structure).

## 1.0.49
- **Changed**: Upgraded `garminconnect` library to `0.2.16` to support weight upload (`add_body_composition`).
- **Feature**: Added extensive debug logging for Garmin, Intervals, and Google Sheets sync to diagnose missing data.

## 1.0.48
- **Fix**: Resolved SyntaxError in `garmin_sync.py`.

## 1.0.47
- **Fix**: Resolved "duplicate labels" error in Workout Details sync by switching to incremental merge strategy.
- **Fix**: Handled missing `add_body_composition` method in Garmin library to prevent crashes during weight sync.

## 1.0.46
- **Changed**: Fixed Pandas FutureWarning regarding downcasting.
- **Changed**: Defaulted Garmin weight to converted Lbs (from KG).
- **Changed**: Removed unused columns from Daily Summary sync (Body Battery, Calories, HRV Status).
- **Feature**: Updates Intervals.icu sync to include Fitness, Fatigue, and Form %.
- **Fix**: Fixed date formatting in Google Sheets to be YYYY-MM-DD.

## 1.0.45
- **Feature**: Implemented **Incremental Sync** for Nutrition Log.
  - The add-on now fetches only the **Current Day's** data from Cronometer (instead of full history) to optimize performance.
  - Existing sheet history is preserved; new daily data is merged in (overwriting previous entries for the same day to handle updates/deletions).
- **Fix**: Resolved "text format" date issue in Google Sheets by setting `value_input_option='USER_ENTERED'`.
- **Fix**: Updated Cronometer export logic to use `https://cronometer.com/export` with explicit parameters (`type=servings`, `start`, `end`) instead of a direct file download URL. This ensures complete data retrieval and resolves 404 errors.
- **Improvement**: Added visual log separator and startup banner to `main.py` for better log readability on restart.
  - Added `userCode` field to login payload.
  - Improved CSRF token extraction regex and added detailed debug logging.
  - Updated success check to handle schema-less JSON redirect responses (`{"redirect": "..."}`).
  - **Fix**: Corrected export URL case sensitivity (`servings.csv` vs `Servings.csv`) to resolve 404 errors.

## 1.0.35
- **Fix**: Resolved Cronometer login failure by correctly extracting and submitting the `anticsrf` token from the login page.

## 1.0.34
- **Feature**: Added Cronometer integration for nutrition logging. Data is exported internally via CSV and synced to the `Nutrition_Log` sheet.
- **Config**: Added `cronometer_username` and `cronometer_password` options.
- **Data**: New `Nutrition_Log` sheet with columns: `Food_Item`, `Meal_Name`, `Quantity`, `Units`, `Calories`, `Fat`, `Protein`, `Carbohydrates`, `Last_Fetched_At`.
- **Docs**: Added Cronometer configuration section to `DOCS.md`.

## 1.0.33
- **Removal**: Removed Fitbit Hydration sync feature as per user request (moved to a different application).
- **Docs**: Reverted the required Fitbit scopes to just `weight profile`.

## 1.0.32
- **Fix**: Updated `get_hydration_data` to use the direct Garmin endpoint `/usersummary-service/usersummary/hydration/daily/{date}`, as the library wrapper was consistently returning 0.

## 1.0.31
- **Fix**: Improved robustness of Fitbit water unit detection. If the unit name is missing in the API response (returning `None`), the system now correctly falls back to a magnitude-based heuristic to determine if the value is in ounces or milliliters.

## 1.0.30
- **Fix**: Improved Fitbit water unit detection to handle variations like "Fluid Ounce", ensuring correct conversion to ml.

## 1.0.29
- **Fix**: Resolved `NameError` in `garmin_sync.py` by correctly importing `datetime`.

## 1.0.28
- **Fix**: Added missing `timestampLocal` field to the Garmin hydration API payload, resolving the 400 Bad Request error.

## 1.0.27
- **Fix**: Implemented direct API call for Garmin hydration sync (`/usersummary-service/usersummary/hydration/log`) as the library wrapper method `add_hydration` was missing.

## 1.0.26
- **Fix**: Implemented auto-recovery from 403 Forbidden errors. If the add-on encounters a scope error (like missing nutrition access), it will automatically attempt to use the `initial_refresh_token` from the configuration to re-authenticate, ensuring config updates take effect immediately.

## 1.0.25
- **Docs**: Updated documentation to include the required `nutrition` scope in the Fitbit authorization URL. This prevents 403 Forbidden errors when fetching water logs.

## 1.0.24
- **Fix**: Resolves `AttributeError` by correctly adding the missing `get_water_log` method to `FitbitSync` class.

## 1.0.23
- **Feature**: Added Fitbit to Garmin Hydration sync.
- **Logic**: Uses a "Delta" sync strategy: Fetches daily total from Fitbit, compares with Garmin's current total, and adds the difference to Garmin. Supports `ml`, `oz`, and `cups` conversion.

## 1.0.22
- **Fix**: Resolved SyntaxError in `main.py` caused by a duplicate `else` block.

## 1.0.21
- **Fix**: Removed lbs->kg conversion for Fitbit sync (user source is already kg).
- **Fix**: Fixed `Garmin.add_body_composition` call by supplying the required `timestamp` argument extracted from the Fitbit log.

## 1.0.20
- **Config**: Updated configuration schema to remove `loseit` options and properly expose `fitbit` options in the Home Assistant UI.
- **Docs**: Added `DOCS.md` with detailed instructions on generating Fitbit OAuth credentials and initial refresh token.

## 1.0.19
- **Feature**: Added Fitbit to Garmin weight sync. Fetches weight from Fitbit (assuming lbs) and uploads to Garmin (converted to kg) automatically.
- **Config**: Added Fitbit OAuth credentials to configuration.

## 1.0.18
- **Removed**: Removed LoseIt integration and all associated scraping logic.
- **Optimization**: Removed `playwright` dependency, significantly reducing the add-on image size.

## 1.0.17
- **Fix**: Updated Google Sheets write operation to strictly use `range_name='A1'` to prevent compatibility issues with `gspread` versions.
- **Fix**: Added more explicit logging for sync operations.

- **Fix**: Restored missing sync methods (`sync_daily_summary`, `sync_nutrition_log`, `sync_workout_details`) that were accidentally removed in v1.0.14.

- **Fix**: Fixed a bug where new data columns (like Intervals wellness) were not being added to existing rows if the columns didn't already exist in the sheet frame.

- **Fix**: Resolved duplicate date issue in `Daily_Summary` by normalizing existing Google Sheet dates to the full format before merging.
- **Fix**: Improved `Daily_Summary` sync to merge data (update columns) for the same date instead of replacing rows, ensuring derived columns or data from other sources are preserved.

- **Feature**: Unified date format to "Wednesday January 14 2026" across all synced sheets.
- **Improved**: LoseIt sync now runs on the same schedule interval as other services, instead of 6x less frequently.

## 1.0.12
- **Feature**: Added `Weight` syncing from Intervals.icu (wellness), prioritizing it over Garmin data if available.

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
