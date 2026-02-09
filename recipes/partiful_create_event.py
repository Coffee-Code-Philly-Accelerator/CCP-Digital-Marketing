"""
RECIPE: Create Event on Partiful
RECIPE ID: rcp_bN7jRF5P_Kf0

FLOW: Input → BROWSER_TOOL_CREATE_TASK → WatchTask → Event URL

VERSION HISTORY:
v2 (current): Rewritten to use BROWSER_TOOL_CREATE_TASK - single AI browser agent call
v1: State machine with BROWSER_TOOL_NAVIGATE/PERFORM_WEB_TASK/FETCH_WEBPAGE (timed out due to ~10 sequential calls)

API LEARNINGS:
- BROWSER_TOOL_CREATE_TASK: AI agent autonomously handles multi-step browser workflows
- BROWSER_TOOL_WATCH_TASK: Poll for task completion, returns status/output/current_url
- BROWSER_TOOL_GET_SESSION: Get liveUrl to watch browser in real-time
- Partiful create URL: https://partiful.com/create
- Partiful shows share/invite modal after creation - must be dismissed
- Partiful does NOT support recurring events
- Success URL pattern: partiful.com/e/

KNOWN ISSUES:
- Session expiry requires re-login via Composio connected accounts
- 2FA cannot be automated
- Share modal must be dismissed to reach the event page
"""

import os
import time
from datetime import datetime

print(f"[{datetime.utcnow().isoformat()}] Starting Partiful event creation")

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
task_description = f"""Create a new event on Partiful with these exact details:

1. Find the event title field (may say 'Untitled Event' or similar), click it, clear any existing text, and type: {event_title}
2. Click the date field or 'When' section and select: {event_date}
3. Find the time field and enter: {event_time}
4. Click the location field or 'Where' section, type: {event_location}, and select from suggestions or press Enter
5. Click the description or details field and type: {event_description}
6. Click the 'Save', 'Publish', or 'Create' button to create the event
7. IMPORTANT: After creation, a share/invite modal will likely appear. Dismiss it by clicking the X button, 'Skip', 'Maybe later', or clicking outside the modal.
8. Wait for the page to show the created event

IMPORTANT: After publishing, the URL should change to partiful.com/e/something. If a share modal blocks the view, dismiss it first."""

print(f"[{datetime.utcnow().isoformat()}] Creating browser task...")
task_result, task_error = run_composio_tool("BROWSER_TOOL_CREATE_TASK", {
    "task": task_description,
    "startUrl": "https://partiful.com/create"
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
        # Check success URL pattern: partiful.com/e/
        if current_url and "partiful.com/e/" in current_url.lower():
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
    "platform": "partiful",
    "status": status,
    "event_url": event_url,
    "image_url": "",
    "error": error_msg,
    "live_url": live_url,
}

print(f"[{datetime.utcnow().isoformat()}] Complete: status={status}, event_url={event_url}")

output
