# auth-setup

Set up Hyperbrowser persistent auth profiles for event creation platforms.

## Invocation

This skill is triggered when the user wants to:
- "Set up auth for Luma"
- "Set up auth for Meetup"
- "Set up auth for Partiful"
- "Set up browser auth"
- "Re-authenticate Luma/Meetup/Partiful"

## Required Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `platform` | string | Platform to authenticate: "luma", "meetup", or "partiful" |

## Optional Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `profile_id` | string | (empty) | Existing Hyperbrowser profile ID for re-authentication |

## Login URLs

| Platform | Login URL |
|----------|-----------|
| Luma | `https://lu.ma/signin` |
| Meetup | `https://www.meetup.com/login/` |
| Partiful | `https://partiful.com/login` |

## Execution

This is an **interactive** skill — NOT a fire-and-forget recipe. Execute the following steps directly via Rube MCP tools.

### Step 1: Create or Reuse Profile

**If no `profile_id` provided** (new setup):
```
RUBE_MULTI_EXECUTE_TOOL(
    tool_slug="HYPERBROWSER_CREATE_PROFILE",
    arguments={}
)
```
Save the returned profile `id` — this is the persistent profile UUID.

**If `profile_id` provided** (re-auth): Skip this step, use the existing profile ID.

### Step 2: Create Session with Persistent Profile

```
RUBE_MULTI_EXECUTE_TOOL(
    tool_slug="HYPERBROWSER_CREATE_SESSION",
    arguments={
        "profile": {"id": "<profile_id>", "persistChanges": true},
        "useStealth": true,
        "acceptCookies": true,
        "timeoutMinutes": 10
    }
)
```

Save the returned `sessionId` and `liveUrl`.

### Step 3: Navigate to Login Page

```
RUBE_MULTI_EXECUTE_TOOL(
    tool_slug="HYPERBROWSER_START_BROWSER_USE_TASK",
    arguments={
        "task": "Navigate to <login_url> and wait for the page to fully load",
        "sessionId": "<sessionId from Step 2>",
        "maxSteps": 3,
        "keepBrowserOpen": true
    }
)
```

### Step 4: User Action

Present the `liveUrl` to the user:

> **Open this URL to log in manually:**
> `<liveUrl>`
>
> Complete the Google OAuth login in the browser window. The session will persist your cookies for future event creation.
>
> When done, save this profile ID to your `.env` file:
> ```
> CCP_{PLATFORM}_PROFILE_ID=<profile_id>
> ```

Wait for the user to confirm they have logged in.

## Re-Authentication

If a platform's browser session expires (NEEDS_AUTH status during event creation):
1. Run this skill again with the existing `profile_id`
2. The same profile is reused — just re-login via the liveUrl
3. No need to update the `.env` file (profile ID unchanged)

## Platform Notes

- **Google OAuth**: All three platforms use Google OAuth for login, which cannot be automated
- **Session Persistence**: Hyperbrowser profiles save cookies across sessions, so login is typically one-time
- **Stealth Mode**: Enabled by default to avoid bot detection (especially important for Meetup)
- **Timeout**: Session stays open for 10 minutes to allow manual login
- **Prerequisites**: Hyperbrowser must be connected via `RUBE_MANAGE_CONNECTIONS(toolkits=["hyperbrowser"])`
