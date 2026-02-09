"""
RECIPE: Create Event on Luma
RECIPE ID: rcp_mXyFyALaEsQF

FLOW: Input → BROWSER_TOOL_CREATE_TASK → WatchTask → Event URL

VERSION HISTORY:
v2 (current): Rewritten to use BROWSER_TOOL_CREATE_TASK - single AI browser agent call
v1: State machine with BROWSER_TOOL_NAVIGATE/PERFORM_WEB_TASK/FETCH_WEBPAGE (timed out due to ~10 sequential calls)

API LEARNINGS:
- BROWSER_TOOL_CREATE_TASK: AI agent autonomously handles multi-step browser workflows
- BROWSER_TOOL_WATCH_TASK: Poll for task completion, returns status/output/current_url
- BROWSER_TOOL_GET_SESSION: Get liveUrl to watch browser in real-time
- Luma create URL: https://lu.ma/create
- Luma React date picker needs explicit wait instructions
- Success URL pattern: lu.ma/ (not /create or /home)

KNOWN ISSUES:
- Session expiry requires re-login via Composio connected accounts
- 2FA cannot be automated
- React date picker can be finicky - task instructions include explicit waits
"""

import os
import time
from datetime import datetime

print(f"[{datetime.utcnow().isoformat()}] Starting Luma event creation")

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
task_description = f"""Create a new event on Luma (lu.ma) with these exact details:

1. Find the event title field (may say 'Event Title' or 'Untitled Event'), click it, clear any existing text, and type exactly: {event_title}
2. Click the date field to open the date picker and select: {event_date}. Wait 2 seconds after selecting for the React date picker to update.
3. Find and click the time field, then enter: {event_time}
4. Click the location/venue field, type: {event_location}, and select from the dropdown suggestions or press Enter
5. Click the description field (may say 'Add a description'), and type: {event_description}
6. Click the 'Publish' or 'Create Event' button to publish the event
7. If a share modal or popup appears after publishing, dismiss it by clicking X, Skip, or outside the modal
8. Wait for the page to navigate to the new event page

IMPORTANT: After clicking Publish, wait for the URL to change from lu.ma/create to the new event URL before finishing. The final URL should look like lu.ma/something (not /create or /home)."""

print(f"[{datetime.utcnow().isoformat()}] Creating browser task...")
task_result, task_error = run_composio_tool("BROWSER_TOOL_CREATE_TASK", {
    "task": task_description,
    "startUrl": "https://lu.ma/create"
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
        # Check success URL pattern: lu.ma/ but not /create or /home
        if current_url and "lu.ma/" in current_url.lower() and "/create" not in current_url.lower() and "/home" not in current_url.lower():
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
    "platform": "luma",
    "status": status,
    "event_url": event_url,
    "image_url": "",
    "error": error_msg,
    "live_url": live_url,
}

print(f"[{datetime.utcnow().isoformat()}] Complete: status={status}, event_url={event_url}")

output
