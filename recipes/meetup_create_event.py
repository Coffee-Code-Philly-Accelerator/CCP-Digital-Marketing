"""
RECIPE: Create Event on Meetup
RECIPE ID: rcp_kHJoI1WmR3AR

FLOW: Input → Provider dispatch (Hyperbrowser or BROWSER_TOOL) → GET_SESSION → Return task_id + live_url

VERSION HISTORY:
v4 (current): Hyperbrowser migration - dual provider support with persistent auth profiles.
v3: Fire-and-forget pattern - starts task, returns immediately. Caller polls via BROWSER_TOOL_WATCH_TASK.
v2: Added polling loop but still exceeded 4-min Rube timeout
v1: State machine with BROWSER_TOOL_NAVIGATE/PERFORM_WEB_TASK/FETCH_WEBPAGE (timed out due to ~10 sequential calls)

API LEARNINGS:
- HYPERBROWSER_START_BROWSER_USE_TASK: Returns {jobId, sessionId}, uses persistent profile for auth
- HYPERBROWSER_GET_SESSION_DETAILS: Returns {liveUrl} for real-time browser watching
- HYPERBROWSER_GET_BROWSER_USE_TASK_STATUS: Poll with task_id for status (replaces BROWSER_TOOL_WATCH_TASK)
- BROWSER_TOOL_CREATE_TASK: Returns {watch_task_id, browser_session_id} (not taskId/sessionId)
- BROWSER_TOOL_GET_SESSION: Returns {liveUrl} for real-time browser watching
- BROWSER_TOOL_WATCH_TASK: Poll with taskId for status/output/current_url (caller responsibility)
- Rube timeout is 4 minutes; polling loops exceed this, so recipe returns immediately
- Meetup requires group-specific URL: {group_url}/events/create/
- Meetup has aggressive anti-bot detection - task instructions include explicit waits
- Success URL pattern: meetup.com + /events/ (not /create)
- Input strings with apostrophes cause SyntaxError in Rube env var injection

KNOWN ISSUES:
- Session expiry requires re-login via Composio connected accounts (browser_tool) or profile re-auth (hyperbrowser)
- 2FA cannot be automated
- Anti-bot detection can interfere; explicit delays in task instructions help
- Stealth mode especially important for Meetup
"""

import os
from datetime import datetime


def sanitize_input(text, max_len=2000):
    """Sanitize user input for safe inclusion in browser task descriptions."""
    if not text:
        return ""
    text = str(text)
    text = "".join(char for char in text if char >= " " or char in "\n\t")
    text = text.replace("```", "'''")
    text = text.replace("---", "___")
    text = text.replace("'", "\u2019")  # curly apostrophe avoids Rube SyntaxError
    return text[:max_len]


try:
    run_composio_tool
except NameError:

    def run_composio_tool(tool_name, arguments):
        """Mock implementation for local testing"""
        print(f"[MOCK] run_composio_tool({tool_name}, {arguments})")
        if tool_name == "BROWSER_TOOL_CREATE_TASK":
            return {"data": {"watch_task_id": "mock_task_123", "browser_session_id": "mock_session_456"}}, None
        if tool_name == "BROWSER_TOOL_GET_SESSION":
            return {"data": {"liveUrl": "https://mock-live-url.example.com"}}, None
        if tool_name == "HYPERBROWSER_START_BROWSER_USE_TASK":
            return {"data": {"jobId": "mock_hb_task_123", "sessionId": "mock_hb_session_456"}}, None
        if tool_name == "HYPERBROWSER_GET_SESSION_DETAILS":
            return {"data": {"liveUrl": "https://mock-hb-live-url.example.com"}}, None
        return {"data": {}}, None


print(f"[{datetime.utcnow().isoformat()}] Starting Meetup event creation")

MEETUP_GROUP_URL = os.environ.get("meetup_group_url", "https://www.meetup.com/code-coffee-philly")
CREATE_URL = f"{MEETUP_GROUP_URL}/events/create/"

# Inputs
event_title = sanitize_input(os.environ.get("event_title"), max_len=200)
event_date = sanitize_input(os.environ.get("event_date"), max_len=100)
event_time = sanitize_input(os.environ.get("event_time"), max_len=100)
event_location = sanitize_input(os.environ.get("event_location"), max_len=500)
event_description = sanitize_input(os.environ.get("event_description"), max_len=5000)
event_image_url = os.environ.get("event_image_url", "")

if not all([event_title, event_date, event_time, event_location, event_description]):
    raise ValueError("Missing required inputs: event_title, event_date, event_time, event_location, event_description")

browser_provider = os.environ.get("CCP_BROWSER_PROVIDER", "hyperbrowser").lower()
profile_id = os.environ.get("CCP_MEETUP_PROFILE_ID", "")
hb_llm = os.environ.get("CCP_HYPERBROWSER_LLM", "claude-sonnet-4-20250514")
hb_max_steps = int(os.environ.get("CCP_HYPERBROWSER_MAX_STEPS", "25"))
hb_stealth = os.environ.get("CCP_HYPERBROWSER_USE_STEALTH", "true").lower() == "true"


def extract_data(result):
    if not result:
        return {}
    data = result.get("data", {})
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    return data if isinstance(data, dict) else {}


# Step 1: Create browser automation task
base_steps = f"""Create a new event on Meetup for the Coffee Code Philly Accelerator group. Fill in the event creation form with these exact details:

1. Find the event title/name field, click it, and type: {event_title}. Wait 2 seconds.
2. Find and click the date field or date picker, then select: {event_date}. Wait 2 seconds.
3. Find the start time field, click it, and enter: {event_time}. Wait 2 seconds.
4. Find the venue/location field, click it, type: {event_location}, and select from suggestions or press Enter. Wait 2 seconds.
5. Find the description or 'about this event' field, click it, and type: {event_description}. Wait 2 seconds."""

image_steps = ""
if event_image_url:
    image_steps = f"""
6. BEFORE publishing, upload a featured photo: Find the 'Featured photo' section or 'Add a photo' button. Wait 2 seconds. Look for an option to import from URL or paste a link, and use this URL: {event_image_url}
   If there is no URL import option, skip the image upload and continue to publish.
   Wait 2 seconds after the image uploads."""

publish_step = 7 if event_image_url else 6
task_description = (
    base_steps
    + image_steps
    + f"""
{publish_step}. Click the 'Publish' or 'Schedule Event' or 'Create Event' button. Wait for the page to navigate.

IMPORTANT: Wait 2 seconds between each action to avoid triggering Meetup's anti-bot detection.
IMPORTANT: After clicking Publish, wait for the URL to change from /create to the new event URL before finishing."""
)

print(f"[{datetime.utcnow().isoformat()}] Creating browser task for {CREATE_URL} (provider: {browser_provider})...")

if browser_provider == "hyperbrowser":
    full_task = f"Navigate to {CREATE_URL} and then:\n\n" + task_description
    session_options = {"useStealth": hb_stealth, "acceptCookies": True}
    if profile_id:
        session_options["profile"] = {"id": profile_id, "persistChanges": True}
    task_result, task_error = run_composio_tool(
        "HYPERBROWSER_START_BROWSER_USE_TASK",
        {
            "task": full_task,
            "sessionOptions": session_options,
            "llm": hb_llm,
            "maxSteps": hb_max_steps,
            "useVision": True,
        },
    )
else:
    task_result, task_error = run_composio_tool(
        "BROWSER_TOOL_CREATE_TASK",
        {
            "task": task_description,
            "startUrl": CREATE_URL,
        },
    )

if task_error:
    raise Exception(f"Failed to create browser task: {task_error}")

task_data = extract_data(task_result)

if browser_provider == "hyperbrowser":
    task_id = task_data.get("jobId", task_data.get("taskId", ""))
    session_id = task_data.get("sessionId", "")
else:
    task_id = task_data.get("taskId", task_data.get("watch_task_id", ""))
    session_id = task_data.get("sessionId", task_data.get("browser_session_id", ""))

if not task_id:
    raise Exception(f"No task ID returned. Full response: {task_data}")

print(f"[{datetime.utcnow().isoformat()}] Task created: {task_id}, session: {session_id}")

# Step 2: Get live URL for user to watch
live_url = ""
if session_id:
    if browser_provider == "hyperbrowser" and session_id:
        session_result, _ = run_composio_tool("HYPERBROWSER_GET_SESSION_DETAILS", {"id": session_id})
    else:
        session_result, _ = run_composio_tool("BROWSER_TOOL_GET_SESSION", {"sessionId": session_id})
    if session_result:
        session_data = extract_data(session_result)
        live_url = session_data.get("liveUrl", "")
        if live_url:
            print(f"[{datetime.utcnow().isoformat()}] Watch live: {live_url}")

poll_tool = (
    "HYPERBROWSER_GET_BROWSER_USE_TASK_STATUS" if browser_provider == "hyperbrowser" else "BROWSER_TOOL_WATCH_TASK"
)
poll_args_key = "task_id" if browser_provider == "hyperbrowser" else "taskId"

# Return immediately - caller is responsible for polling
output = {
    "platform": "meetup",
    "status": "running",
    "task_id": task_id,
    "session_id": session_id,
    "live_url": live_url,
    "event_url": "",
    "error": None,
    "success_url_pattern": "meetup.com/*/events/* (not /create)",
    "provider": browser_provider,
    "poll_tool": poll_tool,
    "poll_args_key": poll_args_key,
    "event_image_url": event_image_url,
}

print(f"[{datetime.utcnow().isoformat()}] Task started. Caller should poll {poll_tool} with {poll_args_key}={task_id}")

output
