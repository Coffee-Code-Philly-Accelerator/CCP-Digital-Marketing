# Troubleshooting Guide

Common issues and solutions for the CCP Digital Marketing automation system.

## Table of Contents

- [Event Creation Issues](#event-creation-issues)
- [Apostrophe Issues](#apostrophe-issues-syntaxerror)
- [Browser Task Polling Issues](#rube_execute_recipe-returns-no-output-for-browser-recipes)
- [Social Promotion Issues](#social-promotion-issues)
- [Connection Issues](#connection-issues)
- [AI Generation Issues](#ai-generation-issues)

---

## Event Creation Issues

### NEEDS_AUTH Status

**Symptom:** Browser task navigates to a login page instead of the create form

**Cause:** Browser session is not logged into the platform

**Solution:**
```mermaid
flowchart TD
    A[Auth Error] --> B[Open Composio Dashboard]
    B --> C[Check connected accounts]
    C --> D{Account connected?}
    D -->|No| E[Connect account in Composio]
    D -->|Yes| F[Re-authenticate / refresh connection]
    E --> G[Re-run recipe]
    F --> G
    G --> H{Still failing?}
    H -->|Yes| I[Try different browser session]
    H -->|No| J[Success!]
```

### Form Filling Fails

**Symptom:** Browser automation can't find form fields

**Cause:** Platform UI has changed

**Solution:**
1. Report the issue on GitHub
2. Use `skip_platforms` to exclude problematic platform
3. Create event manually on that platform

### Meetup Group Access Denied

**Symptom:** Can't create events on Meetup

**Cause:** Not an organizer of the Meetup group

**Solution:**
1. Verify you're an organizer/co-organizer
2. Check the `meetup_group_url` is correct (default: `https://www.meetup.com/code-coffee-philly`)
3. Ensure URL format is `https://www.meetup.com/your-group-name`

---

## Apostrophe Issues (SyntaxError)

**Symptom:** Recipe execution fails with a SyntaxError in Rube's env var injection

**Cause:** Straight apostrophes (`'`) in input strings conflict with Rube's Python string parsing

**Solution:** This is now handled automatically. All recipes convert straight apostrophes to curly quotes (\u2019) via `sanitize_input()`. If you still encounter this:
1. Check that you're using the latest recipe version
2. Re-upload recipes via `RUBE_CREATE_UPDATE_RECIPE`

---

## RUBE_EXECUTE_RECIPE Returns No Output for Browser Recipes

**Symptom:** `RUBE_EXECUTE_RECIPE` returns but the output is empty or doesn't contain event URLs

**Cause:** Event creation recipes use fire-and-forget pattern. They start a browser task and return immediately with a `task_id`. The actual event creation happens asynchronously.

**Solution:** After `RUBE_EXECUTE_RECIPE` returns, poll `BROWSER_TOOL_WATCH_TASK` using `RUBE_MULTI_EXECUTE_TOOL`:
1. Extract `task_id` from the recipe output
2. Call `RUBE_MULTI_EXECUTE_TOOL` with `tool_slug="BROWSER_TOOL_WATCH_TASK"` and `arguments={"taskId": "<task_id>"}`
3. Check `status` in the response: "started" (still running), "finished" (done), "stopped" (failed)
4. Poll every 10-15 seconds until finished or stopped

---

## Social Promotion Issues

### Twitter Post Fails

**Symptom:** `twitter_posted: "failed: ..."`

**Common Causes:**

| Error | Cause | Solution |
|-------|-------|----------|
| Rate limit exceeded | Too many posts | Wait 15 minutes |
| Duplicate content | Same tweet posted recently | Change content slightly |
| Authentication failed | Token expired | Re-authorize in Composio |

### LinkedIn Post Fails

**Symptom:** `linkedin_posted: "failed: ..."`

**Common Causes:**

| Error | Cause | Solution |
|-------|-------|----------|
| Invalid URN | Can't find user profile | Re-authorize LinkedIn |
| Access denied | Permissions revoked | Re-connect with posting permissions |
| Content too long | Exceeded character limit | Shorten description |

### Instagram Post Fails

**Symptom:** `instagram_posted: "failed: ..."`

**Requirements Check:**
```mermaid
flowchart TD
    A[Instagram Error] --> B{Business Account?}
    B -->|No| C[Convert to Business/Creator]
    B -->|Yes| D{Image URL Public?}
    D -->|No| E[Use publicly accessible URL]
    D -->|Yes| F{Connected via Facebook?}
    F -->|No| G[Connect through Facebook Business]
    F -->|Yes| H[Re-authorize permissions]
```

### Facebook Page Post Fails

**Symptom:** `facebook_posted: "failed: ..."`

**Common Issues:**

1. **No page_id provided:** Recipe needs your Facebook Page ID (or set `CCP_FACEBOOK_PAGE_ID` env var)
2. **Wrong permissions:** Need `pages_manage_posts` permission
3. **Page not connected:** Connect page in Composio

**Finding your Page ID:**
1. Go to your Facebook Page
2. Click "About"
3. Scroll to "Page ID" section

### Discord Message Fails

**Symptom:** `discord_posted: "failed: ..."`

**Common Issues:**

1. **Invalid channel_id:** Verify the channel ID is correct (or set `CCP_DISCORD_CHANNEL_ID` env var)
2. **Bot not in server:** Add the bot to your Discord server
3. **Missing permissions:** Bot needs "Send Messages" permission

**Getting Channel ID:**
1. Enable Developer Mode in Discord settings
2. Right-click channel -> "Copy ID"

---

## Connection Issues

### Composio Connection Expired

**Symptom:** API calls fail with authentication errors

**Solution:**
1. Go to [Composio Dashboard](https://composio.dev)
2. Navigate to Connections
3. Find the expired connection
4. Click "Reconnect" or "Refresh"

### Browser Session Expired

**Symptom:** Event creation recipe's browser task navigates to login page

**Solution:**
1. The browser automation uses persistent sessions
2. Sessions can expire after inactivity
3. Re-authenticate the platform connection in Composio
4. Re-run the recipe

### Multiple Account Confusion

**Symptom:** Posting to wrong account

**Solution:**
1. Check which accounts are connected in Composio
2. Disconnect unwanted accounts
3. Connect the correct account
4. Verify with a test post

---

## AI Generation Issues

### Image Generation Fails

**Symptom:** `image_url` is empty or image looks wrong

**Causes:**

| Issue | Solution |
|-------|----------|
| Gemini quota exceeded | Wait or upgrade plan |
| Inappropriate content detected | Modify event description |
| Network timeout | Retry the recipe |

### Description Generation Fails

**Symptom:** All platforms get the same generic description

**Cause:** LLM couldn't parse the prompt correctly

**Impact:** Recipe still works, just with less optimized content

**Solution:**
1. This is non-critical - recipe continues
2. Edit posts manually if needed
3. Report persistent issues

---

## Quick Fixes

### Reset Everything

If multiple things are broken:

```bash
# 1. Clear all Composio connections
# Go to Composio Dashboard -> Connections -> Remove all

# 2. Re-connect each service:
# - Twitter
# - LinkedIn
# - Instagram (via Facebook)
# - Facebook
# - Discord

# 3. Re-authenticate event platforms:
# - lu.ma
# - meetup.com
# - partiful.com

# 4. Test with a single platform first
```

### Skip Problematic Platforms

When you need to post urgently:

```python
# Skip event platforms with issues (use per-platform recipes and just skip the problematic one)
# For example, only run Luma and Partiful, skip Meetup entirely

# Skip social platforms with issues
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_X65IirgPhwh3",
    input_data={
        ...,
        "skip_platforms": "facebook,discord"  # Skip FB and Discord
    }
)
```

---

## Getting Help

### Report an Issue

1. Go to [GitHub Issues](https://github.com/Coffee-Code-Philly-Accelerator/CCP-Digital-Marketing/issues)
2. Include:
   - Recipe ID
   - Error message
   - Platform(s) affected
   - Steps to reproduce

### Composio Support

For API connection issues:
- [Composio Documentation](https://composio.dev/docs)
- [Composio Discord](https://discord.gg/composio)

### Platform-Specific Help

| Platform | Documentation |
|----------|--------------|
| Twitter | [Developer Portal](https://developer.twitter.com) |
| LinkedIn | [Marketing API](https://docs.microsoft.com/linkedin) |
| Instagram | [Graph API](https://developers.facebook.com/docs/instagram-api) |
| Facebook | [Graph API](https://developers.facebook.com/docs/graph-api) |
| Discord | [Developer Portal](https://discord.com/developers) |
