# Changelog

## 0.4.0
- **Major UI Refactor**: Introduced sidebar navigation and dedicated "Settings" view.
- **Transactions Management**: Added full support for creating, listing, and filtering transactions.
- **Import & Rules**: Added CSV file upload and rule-based auto-categorization.
- **Enhanced Categories**: Improved category tree view with collapsible nodes.

## 0.3.1

- Fixed database migration issue (automatically adds missing `parent_id` column to existing databases).

## 0.3.0

- Added **Subcategories** support (nested categories).
- Added **Database Seeding** (auto-populates default categories like Food, Housing, etc.).
- Added **Edit/Rename** feature for Members, Accounts, and Categories.

## 0.2.0

- Added **Shared Accounts** support (Family/Joint accounts).
- Added **Categories Management** (Create/Delete categories).

## 0.1.10

- Fixed broken HTML syntax in "Add Member" button.

## 0.1.9

- Fixed API calls failing in Ingress by using relative paths (e.g., `users/` instead of `/users/`).

## 0.1.8

- Fixed background visibility by enforcing full screen height (`min-h-screen`).
- Applied explicit Tailwind radial gradient for verified "premium" aesthetic.

## 0.1.7

- Enhanced visual aesthetics with a premium radial gradient background.

## 0.1.6

- Aggressively fixed UI contrast using explicit Tailwind classes for dark mode inputs.

## 0.1.5

- Improved UI contrast and dark mode support (Fix "black on black" issues).

## 0.1.4

- Fixed `ModuleNotFoundError` by including all application files.
- Added Management UI for Family Members and Accounts.

## 0.1.3

- Added `sqlmodel` database support.
- Added API endpoints for `Users` and `Accounts`.

## 0.1.2

- Fixed Docker build error by allowing system package breaking (PEP 668).

## 0.1.1

- Switched to `run.sh` for reliable startup.
- Fixed 503 Service Unavailable error.

## 0.1.0

- Added Web UI with FastAPI.
- Added Home Assistant Ingress support.

## 0.0.1

- Initial release with Hello World python script.
