"""
RECIPE: Create Event on All Platforms
RECIPE ID: rcp_xvediVZu8BzW
RECIPE URL: https://rube.app/recipes/fa1a7dd7-05d1-4155-803a-a2448f6fc1b2

FLOW: Input → Gemini Image → LLM Descriptions → Browser Automation (Luma, Meetup, Partiful) → Event URLs

VERSION HISTORY:
v2 (current): Added 2FA detection, skip_platforms option, better auth state checking
v1: Initial version - sequential browser automation for 3 platforms

API LEARNINGS:
- BROWSER_TOOL_NAVIGATE: Returns pageSnapshot in markdown format
- BROWSER_TOOL_PERFORM_WEB_TASK: AI agent fills forms based on natural language prompt
- BROWSER_TOOL_FETCH_WEBPAGE: Gets current page state without navigation
- GEMINI_GENERATE_IMAGE: Returns publicUrl for generated image
- Luma create URL: https://lu.ma/create
- Partiful create URL: https://partiful.com/create
- Meetup requires group-specific URL: {group_url}/events/create/

KNOWN ISSUES:
- Session expiry may require re-login
- 2FA interrupts require manual intervention - recipe reports NEEDS_AUTH
- UI changes may break form filling prompts
"""

import os
import re
import json
from datetime import datetime

print(f"[{datetime.utcnow().isoformat()}] Starting unified event creation workflow")

# Get inputs
event_title = os.environ.get("event_title")
event_date = os.environ.get("event_date")
event_time = os.environ.get("event_time")
event_location = os.environ.get("event_location")
event_description = os.environ.get("event_description")
meetup_group_url = os.environ.get("meetup_group_url", "")
platforms_str = os.environ.get("platforms", "luma,meetup,partiful")
skip_platforms_str = os.environ.get("skip_platforms", "")

# Validate required inputs
if not all([event_title, event_date, event_time, event_location, event_description]):
    raise ValueError("Missing required inputs: event_title, event_date, event_time, event_location, event_description")

platforms = [p.strip().lower() for p in platforms_str.split(",") if p.strip()]
skip_platforms = [p.strip().lower() for p in skip_platforms_str.split(",") if p.strip()]
active_platforms = [p for p in platforms if p not in skip_platforms]

print(f"[{datetime.utcnow().isoformat()}] Creating event on platforms: {active_platforms}")
if skip_platforms:
    print(f"[{datetime.utcnow().isoformat()}] Skipping platforms: {skip_platforms}")

# Auth detection patterns
AUTH_PATTERNS = [
    "sign in", "log in", "login", "sign up", "create account",
    "enter your email", "enter your password", "verification code",
    "2fa", "two-factor", "authenticate", "verify your"
]

def check_needs_auth(page_content):
    """Check if page indicates auth is needed"""
    content_lower = page_content.lower()
    for pattern in AUTH_PATTERNS:
        if pattern in content_lower:
            return True
    return False

def check_is_form_page(page_content, platform):
    """Check if we're on the actual form page"""
    content_lower = page_content.lower()
    if platform == "luma":
        return "event title" in content_lower or "create event" in content_lower
    elif platform == "meetup":
        return "event details" in content_lower or "what's your event" in content_lower
    elif platform == "partiful":
        return "untitled event" in content_lower or "event title" in content_lower
    return False

# Step 1: Generate promotional image
print(f"[{datetime.utcnow().isoformat()}] Generating promotional image via Gemini...")
image_prompt = f"Create a modern, eye-catching event promotional graphic for: {event_title}. Style: professional, vibrant colors, suitable for social media. Include visual elements suggesting: {event_location}. Do not include any text in the image."

image_result, image_error = run_composio_tool("GEMINI_GENERATE_IMAGE", {
    "prompt": image_prompt,
    "model": "imagen-3.0-generate-002"
})

if image_error:
    print(f"[{datetime.utcnow().isoformat()}] Image generation failed: {image_error}")
    image_url = ""
else:
    image_data = image_result.get("data", {})
    if "data" in image_data:
        image_data = image_data["data"]
    image_url = image_data.get("publicUrl", "")
    print(f"[{datetime.utcnow().isoformat()}] Image generated: {image_url}")

# Step 2: Generate platform-specific descriptions
print(f"[{datetime.utcnow().isoformat()}] Generating platform-optimized descriptions...")
desc_prompt = f"""Generate 3 platform-specific event descriptions based on this info:
Title: {event_title}
Date: {event_date} at {event_time}
Location: {event_location}
Original Description: {event_description}

Return JSON with keys: luma, meetup, partiful
Each should be optimized for that platform's audience and format.
Luma: Professional, concise
Meetup: Community-focused, detailed
Partiful: Fun, casual, emoji-friendly"""

desc_response, desc_error = invoke_llm(desc_prompt)
if desc_error:
    print(f"[{datetime.utcnow().isoformat()}] Description generation failed, using original")
    descriptions = {"luma": event_description, "meetup": event_description, "partiful": event_description}
else:
    try:
        json_match = re.search(r'\{[^{}]*\}', desc_response, re.DOTALL)
        if json_match:
            descriptions = json.loads(json_match.group())
        else:
            descriptions = {"luma": event_description, "meetup": event_description, "partiful": event_description}
    except:
        descriptions = {"luma": event_description, "meetup": event_description, "partiful": event_description}

print(f"[{datetime.utcnow().isoformat()}] Descriptions ready for all platforms")

# Results tracking
results = {
    "luma_url": "",
    "meetup_url": "",
    "partiful_url": "",
    "image_url": image_url,
    "statuses": {},
    "needs_auth_platforms": []
}

# Step 3: Create event on each platform
def create_on_luma():
    print(f"[{datetime.utcnow().isoformat()}] Creating event on Luma...")

    nav_result, nav_error = run_composio_tool("BROWSER_TOOL_NAVIGATE", {
        "url": "https://lu.ma/create"
    })

    if nav_error:
        return {"status": "FAILED", "error": nav_error, "url": ""}

    page_data = nav_result.get("data", {})
    if "data" in page_data:
        page_data = page_data["data"]
    page_snapshot = page_data.get("pageSnapshot", "")

    if check_needs_auth(page_snapshot) and not check_is_form_page(page_snapshot, "luma"):
        return {"status": "NEEDS_AUTH", "error": "Login required for Luma - please log in via browser and retry", "url": ""}

    form_prompt = f"""Fill out the event creation form with these details:
- Event Title: {event_title}
- Date: {event_date}
- Time: {event_time}
- Location: {event_location}
- Description: {descriptions.get('luma', event_description)}

After filling all fields, click the Publish or Create Event button."""

    task_result, task_error = run_composio_tool("BROWSER_TOOL_PERFORM_WEB_TASK", {
        "prompt": form_prompt
    })

    if task_error:
        return {"status": "FAILED", "error": task_error, "url": ""}

    task_data = task_result.get("data", {})
    if "data" in task_data:
        task_data = task_data["data"]
    extracted_url = task_data.get("navigatedUrl", "")

    if "lu.ma/" in extracted_url and extracted_url != "https://lu.ma/create":
        return {"status": "PUBLISHED", "error": "", "url": extracted_url}

    return {"status": "NEEDS_REVIEW", "error": "Could not confirm publication - check browser", "url": ""}

def create_on_meetup():
    print(f"[{datetime.utcnow().isoformat()}] Creating event on Meetup...")

    if not meetup_group_url:
        return {"status": "SKIPPED", "error": "No Meetup group URL provided", "url": ""}

    create_url = meetup_group_url.rstrip("/") + "/events/create/"

    nav_result, nav_error = run_composio_tool("BROWSER_TOOL_NAVIGATE", {
        "url": create_url
    })

    if nav_error:
        return {"status": "FAILED", "error": nav_error, "url": ""}

    page_data = nav_result.get("data", {})
    if "data" in page_data:
        page_data = page_data["data"]
    page_snapshot = page_data.get("pageSnapshot", "")

    if check_needs_auth(page_snapshot) and not check_is_form_page(page_snapshot, "meetup"):
        return {"status": "NEEDS_AUTH", "error": "Login required for Meetup - please log in via browser and retry", "url": ""}

    form_prompt = f"""Fill out the Meetup event creation form with these details:
- Event Title: {event_title}
- Date: {event_date}
- Time: {event_time}
- Venue/Location: {event_location}
- Description: {descriptions.get('meetup', event_description)}

After filling all fields, click Publish or Schedule Event button."""

    task_result, task_error = run_composio_tool("BROWSER_TOOL_PERFORM_WEB_TASK", {
        "prompt": form_prompt
    })

    if task_error:
        return {"status": "FAILED", "error": task_error, "url": ""}

    task_data = task_result.get("data", {})
    if "data" in task_data:
        task_data = task_data["data"]
    extracted_url = task_data.get("navigatedUrl", "")

    if "meetup.com" in extracted_url and "/events/" in extracted_url:
        return {"status": "PUBLISHED", "error": "", "url": extracted_url}

    return {"status": "NEEDS_REVIEW", "error": "Could not confirm publication - check browser", "url": ""}

def create_on_partiful():
    print(f"[{datetime.utcnow().isoformat()}] Creating event on Partiful...")

    nav_result, nav_error = run_composio_tool("BROWSER_TOOL_NAVIGATE", {
        "url": "https://partiful.com/create"
    })

    if nav_error:
        return {"status": "FAILED", "error": nav_error, "url": ""}

    page_data = nav_result.get("data", {})
    if "data" in page_data:
        page_data = page_data["data"]
    page_snapshot = page_data.get("pageSnapshot", "")

    if check_needs_auth(page_snapshot) and not check_is_form_page(page_snapshot, "partiful"):
        return {"status": "NEEDS_AUTH", "error": "Login required for Partiful - please log in via browser and retry", "url": ""}

    form_prompt = f"""Fill out the Partiful event creation form with these details:
- Event Title: {event_title}
- Date: {event_date}
- Time: {event_time}
- Location: {event_location}
- Description: {descriptions.get('partiful', event_description)}

After filling all fields, click Save or Publish button to create the event."""

    task_result, task_error = run_composio_tool("BROWSER_TOOL_PERFORM_WEB_TASK", {
        "prompt": form_prompt
    })

    if task_error:
        return {"status": "FAILED", "error": task_error, "url": ""}

    task_data = task_result.get("data", {})
    if "data" in task_data:
        task_data = task_data["data"]
    extracted_url = task_data.get("navigatedUrl", "")

    if "partiful.com/e/" in extracted_url:
        return {"status": "PUBLISHED", "error": "", "url": extracted_url}

    return {"status": "NEEDS_REVIEW", "error": "Could not confirm publication - check browser", "url": ""}

# Execute for each platform
if "luma" in active_platforms:
    luma_result = create_on_luma()
    results["luma_url"] = luma_result.get("url", "")
    results["statuses"]["luma"] = luma_result
    if luma_result["status"] == "NEEDS_AUTH":
        results["needs_auth_platforms"].append("luma")
    print(f"[{datetime.utcnow().isoformat()}] Luma: {luma_result['status']}")

if "meetup" in active_platforms:
    meetup_result = create_on_meetup()
    results["meetup_url"] = meetup_result.get("url", "")
    results["statuses"]["meetup"] = meetup_result
    if meetup_result["status"] == "NEEDS_AUTH":
        results["needs_auth_platforms"].append("meetup")
    print(f"[{datetime.utcnow().isoformat()}] Meetup: {meetup_result['status']}")

if "partiful" in active_platforms:
    partiful_result = create_on_partiful()
    results["partiful_url"] = partiful_result.get("url", "")
    results["statuses"]["partiful"] = partiful_result
    if partiful_result["status"] == "NEEDS_AUTH":
        results["needs_auth_platforms"].append("partiful")
    print(f"[{datetime.utcnow().isoformat()}] Partiful: {partiful_result['status']}")

# Build summary
status_parts = []
for platform, status_info in results.get("statuses", {}).items():
    status_parts.append(f"{platform.title()}: {status_info.get('status', 'UNKNOWN')}")

results["status_summary"] = " | ".join(status_parts)
needs_auth_str = ",".join(results["needs_auth_platforms"]) if results["needs_auth_platforms"] else "none"

print(f"[{datetime.utcnow().isoformat()}] Workflow complete: {results['status_summary']}")
if results["needs_auth_platforms"]:
    print(f"[{datetime.utcnow().isoformat()}] ACTION REQUIRED: Log in to these platforms and re-run: {needs_auth_str}")

output = {
    "luma_url": results["luma_url"],
    "meetup_url": results["meetup_url"],
    "partiful_url": results["partiful_url"],
    "image_url": results["image_url"],
    "status_summary": results["status_summary"],
    "needs_auth": needs_auth_str
}
output
