# Gemini Station

A persistent terminal for the Google Gemini CLI in Home Assistant.

## Features
- **Persistent Login**: Credentials stored in `/data` survive restarts.
- **Web Interface**: Full terminal access via Home Assistant Ingress.
- **Pre-installed**: Includes `python3`, `pip`, `node`, `npm`, and `@google/gemini-cli`.

## Installation
1. Navigate to the add-on store headers.
2. Click "Check for updates".
3. Install "Gemini Station".
4. Start the add-on.
5. Click "Open Web UI".

## Usage
In the terminal, run:
```bash
gemini login
```
Follow the instructions. Your login will be saved.

To chat:
```bash
gemini "Hello, how are you?"
```
