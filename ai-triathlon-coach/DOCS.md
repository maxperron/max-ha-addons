# AI Triathlon Coach Configuration Guide

## Fitbit Configuration (Weight Sync)

To sync your weight from Fitbit to Garmin, you need to provide OAuth 2.0 credentials. Since this is a "headless" add-on running in Home Assistant, you must create your own "Personal" app in the Fitbit Developer Portal to authorize it.

### Step 1: Create a Fitbit App
1.  Go to [dev.fitbit.com/apps](https://dev.fitbit.com/apps/new) and log in.
2.  Click **Register a New App**.
3.  Fill in the details:
    *   **Application Name**: `Home Assistant AI Coach` (or similar)
    *   **Description**: `Personal weight sync for Home Assistant`
    *   **Application Website**: `http://localhost` (doesn't matter)
    *   **Organization**: `Personal`
    *   **Organization Website**: `http://localhost`
    *   **Terms of Service Url**: `http://localhost`
    *   **Privacy Policy Url**: `http://localhost`
    *   **OAuth 2.0 Application Type**: **Personal** (Crucial: Allows access to Intraday data and personal weight logs).
    *   **Redirect URL**: `http://localhost` (Crucial: You will catch the code here manually).
    *   **Access Type**: `Read & Write`
4.  Save. You will now have a **Client ID** and **Client Secret**.

### Step 2: Get Initial Refresh Token
You need to authenticate once to generate the initial token cycle. You can do this easily via the [Fitbit Web API Explorer](https://dev.fitbit.com/build/reference/web-api/explore/) OR manually:

#### Method A: Using Authorization URL
1.  Construct this URL (replace `YOUR_CLIENT_ID`):
    ```
    https://www.fitbit.com/oauth2/authorize?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=http%3A%2F%2Flocalhost&scope=weight%20profile
    ```
2.  Paste it into your browser. Log in and click "Allow".
3.  You will be redirected to `http://localhost/?code=YOUR_BIG_CODE#_=_`.
    *   Copy the `code` parameter (everything between `code=` and `#`).
4.  Exchange the code for a token using `curl`:
    ```bash
    # Replace CLIENT_ID and CLIENT_SECRET.
    # Replace AUTH_HEADER with the base64 encoded string of "CLIENT_ID:CLIENT_SECRET"
    # To get base64 on Mac/Linux: echo -n "clientId:clientSecret" | base64

    curl -X POST https://api.fitbit.com/oauth2/token \
      -H "Authorization: Basic YOUR_BASE64_AUTH_HEADER" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "clientId=YOUR_CLIENT_ID" \
      -d "grant_type=authorization_code" \
      -d "redirect_uri=http://localhost" \
      -d "code=YOUR_CODE_FROM_STEP_3"
    ```
5.  The response will assume a JSON containing `refresh_token`. **Copy this Refresh Token**.

### Step 3: Configure Add-on
Go to the **Configuration** tab in Home Assistant and enter:
*   `fitbit_client_id`: From Step 1.
*   `fitbit_client_secret`: From Step 1.
*   `fitbit_initial_refresh_token`: From Step 2.

The add-on will automatically manage token refreshing from this point on.
