"""
RECIPE: Create Event on Meetup
RECIPE ID: rcp_kHJoI1WmR3AR

FLOW: Input → BROWSER_TOOL_CREATE_TASK → WatchTask → Event URL

VERSION HISTORY:
v2 (current): Rewritten to use BROWSER_TOOL_CREATE_TASK - single AI browser agent call
v1: State machine with BROWSER_TOOL_NAVIGATE/PERFORM_WEB_TASK/FETCH_WEBPAGE (timed out due to ~10 sequential calls)

API LEARNINGS:
- BROWSER_TOOL_CREATE_TASK: AI agent autonomously handles multi-step browser workflows
- BROWSER_TOOL_WATCH_TASK: Poll for task completion, returns status/output/current_url
- BROWSER_TOOL_GET_SESSION: Get liveUrl to watch browser in real-time
- Meetup requires group-specific URL: {group_url}/events/create/
- Meetup has aggressive anti-bot detection - task instructions include explicit waits
- Success URL pattern: meetup.com + /events/ (not /create)

KNOWN ISSUES:
- Session expiry requires re-login via Composio connected accounts
- 2FA cannot be automated
- Anti-bot detection can interfere; explicit delays in task instructions help
"""

import os
import time
from datetime import datetime

print(f"[{datetime.utcnow().isoformat()}] Starting Meetup event creation")

MEETUP_GROUP_URL = "https://www.meetup.com/coffee-code-philly-accelerator"
CREATE_URL = f"{MEETUP_GROUP_URL}/events/create/"

# Inputs
event_title = os.environ.get("event_title", "")
event_date = os.environ.get("event_date", "")
event_time = os.environ.get("event_time", "")
event_location = os.environ.get("event_location", "")
event_description = os.environ.get("event_description", "")

if not all([event_title, event_date, event_time, event_location, event_description]):
    raise ValueError("Missing required inputs: event_title, event_date, event_time, event_location, event_description")


def extract_data(result):
    if not result:
        return {}
    data = result.get("data", {})
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    return data if isinstance(data, dict) else {}


# Step 1: Create browser automation task
task_description = f"""Create a new event on Meetup for the Coffee Code Philly Accelerator group. Fill in the event creation form with these exact details:

1. Find the event title/name field, click it, and type: {event_title}. Wait 2 seconds.
2. Find and click the date field or date picker, then select: {event_date}. Wait 2 seconds.
3. Find the start time field, click it, and enter: {event_time}. Wait 2 seconds.
4. Find the venue/location field, click it, type: {event_location}, and select from suggestions or press Enter. Wait 2 seconds.
5. Find the description or 'about this event' field, click it, and type: {event_description}. Wait 2 seconds.
6. Click the 'Publish' or 'Schedule Event' or 'Create Event' button. Wait for the page to navigate.

IMPORTANT: Wait 2 seconds between each action to avoid triggering Meetup's anti-bot detection.
IMPORTANT: After clicking Publish, wait for the URL to change from /create to the new event URL before finishing."""

print(f"[{datetime.utcnow().isoformat()}] Creating browser task for {CREATE_URL}...")
task_result, task_error = run_composio_tool("BROWSER_TOOL_CREATE_TASK", {
    "task": task_description,
    "startUrl": CREATE_URL
})

if task_error:
    raise Exception(f"Failed to create browser task: {task_error}")

task_data = extract_data(task_result)
task_id = task_data.get("taskId", "")
session_id = task_data.get("sessionId", task_data.get("browser_session_id", ""))

if not task_id:
    raise Exception(f"No taskId returned. Full response: {task_data}")

print(f"[{datetime.utcnow().isoformat()}] Task created: {task_id}, session: {session_id}")

# Step 2: Get live URL for user to watch
live_url = ""
if session_id:
    session_result, _ = run_composio_tool("BROWSER_TOOL_GET_SESSION", {"sessionId": session_id})
    if session_result:
        session_data = extract_data(session_result)
        live_url = session_data.get("liveUrl", "")
        if live_url:
            print(f"[{datetime.utcnow().isoformat()}] Watch live: {live_url}")

# Step 3: Poll for completion (5s intervals, up to 3 minutes)
event_url = ""
status = "failed"
error_msg = None

for i in range(36):
    time.sleep(5)
    watch_result, watch_error = run_composio_tool("BROWSER_TOOL_WATCH_TASK", {"taskId": task_id})
    if watch_error:
        print(f"[{datetime.utcnow().isoformat()}] Watch error: {watch_error}")
        continue

    watch_data = extract_data(watch_result)
    task_status = watch_data.get("status", "")
    current_url = watch_data.get("current_url", "")

    print(f"[{datetime.utcnow().isoformat()}] Poll {i+1}: status={task_status}, url={current_url}")

    if task_status == "finished":
        is_success = watch_data.get("is_success", False)
        # Check success URL pattern: meetup.com + /events/ but not /create
        if current_url and "meetup.com" in current_url.lower() and "/events/" in current_url.lower() and "/create" not in current_url.lower():
            event_url = current_url
            status = "done"
        elif is_success:
            event_url = current_url or ""
            status = "done"
        else:
            status = "needs_review"
            error_msg = watch_data.get("output", "Task finished but could not confirm event creation")
        break
    elif task_status == "stopped":
        status = "failed"
        error_msg = "Browser task was stopped"
        break

if status == "failed" and not error_msg:
    error_msg = "Timed out waiting for browser task to complete"

output = {
    "platform": "meetup",
    "status": status,
    "event_url": event_url,
    "image_url": "",
    "error": error_msg,
    "live_url": live_url,
}

print(f"[{datetime.utcnow().isoformat()}] Complete: status={status}, event_url={event_url}")

output
