# Changelog

## 0.6.1
- **Import**: Added support for Mastercard CSV format (headerless).

## 0.6.0
- **Trips**: You can now create Trips in Settings and assign transactions to them!
  - **Manage Trips**: Create/Delete trips in Settings.
  - **Assign**: Assign a trip directly from the transaction table (inline) or use Bulk Actions.
  - **Filter**: Filter your transaction list to see expenses for a specific trip.

## 0.5.2
- **Fix**: Critical fix for database migration. Ensuring "Family Expense" column is correctly added to the database.
- **Improved**: Added error alerts in the UI if an action fails, helping troubleshoot issues.

## 0.5.1
- **Fix**: Resolved issue where toggling "Family Expense" or editing categories didn't save correctly.
- **UI**: Shared accounts now strictly labeled "Shared Account" instead of "No Owner".
- **API**: Improved backend to support partial updates for better performance and reliability.

## 0.5.0
- **Family Tagging**: Identify transactions as "Family" expenses with a simple toggle in the table.
- **Shared Accounts**: Mark accounts as "Shared" to automatically tag all imported transactions as Family expenses.
- **Bulk Family Tagging**: Select multiple transactions to mark them as Family or Personal in one go.

## 0.4.4
- **Searchable Inline Edit**: Replaced the native category select in the table with a powerful searchable dropdown.
- **Improved Rule Logic**: Rules are now checked for duplicates before creation.
- **Auto-Apply Rules**: Creating a new rule retroactively applies it to all matching past transactions.
- **Smart Prompts**: Better prompts handling rule creation when editing categories inline.

## 0.4.3
- **Bulk Actions**: Added ability to delete multiple transactions at once.
- **UI Improvements**: Category dropdowns (Filter and Inline) now showing full hierarchy.
- **Inline Editing**: Can now change transaction category directly from the table.
- **Smart Rules**: Prompts to create an auto-categorization rule when manually categorizing a transaction.
- **Fix**: Improved hierarchy visualization in bulk category picker.

## 0.4.2
- **Transactions UI**: Removed manual add form (import focused). Added bulk categorization with checkboxes and a searchable, hierarchical category dropdown.
- **Import Fix**: Improved CSV parsing to support 'details' column for descriptions.
- **Bug Fix**: Fixed visibility issues in Settings page by properly initializing UI state.

## 0.4.1
- **Fix**: Added missing `python-multipart` dependency required for file uploads.

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
