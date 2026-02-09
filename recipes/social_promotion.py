"""
RECIPE: Event Social Promotion
RECIPE ID: rcp_zBzqs2LO-miP

FLOW: Event Details → Gemini Image → LLM Copy → Parallel Social Posting

VERSION HISTORY:
v3 (current): Added optional image_url input to reuse existing image and skip Gemini generation
v2: Added auto-discovery for LinkedIn URN and Instagram User ID, graceful degradation
v1: Initial version with hardcoded platform IDs

API LEARNINGS:
- TWITTER_CREATION_OF_A_POST: Simple text post, image via URL
- LINKEDIN_GET_MY_INFO: Returns data.data with 'id' field (person URN suffix)
- LINKEDIN_CREATE_LINKED_IN_POST: Requires author URN, commentary, visibility
- INSTAGRAM_GET_USER_INFO: Returns 'id' for connected business account
- INSTAGRAM_CREATE_MEDIA_CONTAINER: Create media container with ig_user_id, image_url, caption
- INSTAGRAM_GET_POST_STATUS: Poll container status until FINISHED
- INSTAGRAM_CREATE_POST: Publish container with ig_user_id, creation_id
- FACEBOOK_CREATE_POST: Requires page_id, message
- DISCORDBOT_CREATE_MESSAGE: Requires channel_id, content

KNOWN ISSUES:
- Instagram requires Business/Creator account
- Facebook requires page_manage_posts permission
- Discord requires bot in server with send message permission
"""

import os
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# ============================================================================
# Mockable Interface for External Dependencies
# ============================================================================
# These functions are normally injected by the Composio runtime.
# Providing mock implementations enables local testing and unit tests.

try:
    # Check if run_composio_tool is available (injected by Composio runtime)
    run_composio_tool
except NameError:
    def run_composio_tool(tool_name, arguments):
        """Mock implementation for local testing"""
        print(f"[MOCK] run_composio_tool({tool_name}, {arguments})")
        return {"data": {"mock": True, "sub": "mock_user", "id": "mock_id"}}, None

try:
    # Check if invoke_llm is available (injected by Composio runtime)
    invoke_llm
except NameError:
    def invoke_llm(prompt):
        """Mock implementation for local testing"""
        print(f"[MOCK] invoke_llm(prompt length={len(prompt)})")
        return '{"twitter": "mock", "linkedin": "mock", "instagram": "mock", "facebook": "mock", "discord": "mock"}', None

print(f"[{datetime.utcnow().isoformat()}] Starting social media promotion workflow")


def sanitize_input(text, max_len=2000):
    """
    Sanitize user input to prevent prompt injection attacks.

    Args:
        text: Input text to sanitize
        max_len: Maximum allowed length (default 2000)

    Returns:
        Sanitized string safe for inclusion in LLM prompts
    """
    if not text:
        return ""
    # Convert to string if needed
    text = str(text)
    # Remove control characters except newlines and tabs
    text = ''.join(char for char in text if char >= ' ' or char in '\n\t')
    # Replace common prompt injection delimiters
    text = text.replace("```", "'''")
    text = text.replace("---", "___")
    text = text.replace("'", "\u2019")  # curly apostrophe avoids Rube SyntaxError
    # Truncate to max length
    return text[:max_len]


def extract_json_from_text(text):
    """
    Robustly extract JSON object from LLM response text.

    Handles cases where JSON is embedded in explanatory text,
    has nested structures, or spans multiple lines.

    Args:
        text: String that may contain a JSON object

    Returns:
        Parsed dict if found, empty dict otherwise
    """
    if not text:
        return {}

    # Try to find JSON by matching outermost braces
    start = text.find('{')
    if start == -1:
        return {}

    # Find matching closing brace by counting depth
    depth = 0
    for i, char in enumerate(text[start:], start):
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return {}

    return {}

# Get inputs and sanitize user-provided content
event_title = sanitize_input(os.environ.get("event_title"), max_len=200)
event_date = sanitize_input(os.environ.get("event_date"), max_len=100)
event_time = sanitize_input(os.environ.get("event_time"), max_len=100)
event_location = sanitize_input(os.environ.get("event_location"), max_len=500)
event_description = sanitize_input(os.environ.get("event_description"), max_len=5000)
event_url = os.environ.get("event_url", "")  # URL not sanitized - passed through
discord_channel_id = os.environ.get("discord_channel_id", "") or os.environ.get("CCP_DISCORD_CHANNEL_ID", "")
facebook_page_id = os.environ.get("facebook_page_id", "") or os.environ.get("CCP_FACEBOOK_PAGE_ID", "")
skip_platforms_str = os.environ.get("skip_platforms", "")
existing_image_url = os.environ.get("image_url", "")

# Validate required inputs
if not all([event_title, event_date, event_time, event_location, event_description]):
    raise ValueError("Missing required inputs")

skip_platforms = [p.strip().lower() for p in skip_platforms_str.split(",") if p.strip()]

# Results tracking
results = {
    "twitter_posted": "skipped",
    "linkedin_posted": "skipped",
    "instagram_posted": "skipped",
    "facebook_posted": "skipped",
    "discord_posted": "skipped",
    "image_url": "",
    "summary": ""
}

# Step 1: Generate promotional image (or reuse provided one)
if existing_image_url:
    results["image_url"] = existing_image_url
    print(f"[{datetime.utcnow().isoformat()}] Using provided image: {results['image_url']}")
else:
    print(f"[{datetime.utcnow().isoformat()}] Generating promotional image...")
    image_prompt = f"Create a modern, eye-catching event promotional graphic for: {event_title}. Style: professional, vibrant colors, suitable for social media. Do not include any text in the image."

    image_result, image_error = run_composio_tool("GEMINI_GENERATE_IMAGE", {
        "prompt": image_prompt,
        "model": "gemini-2.5-flash-image"
    })

    if not image_error:
        image_data = image_result.get("data", {})
        if "data" in image_data:
            image_data = image_data["data"]
        results["image_url"] = image_data.get("publicUrl", "")
        print(f"[{datetime.utcnow().isoformat()}] Image generated: {results['image_url']}")
    else:
        print(f"[{datetime.utcnow().isoformat()}] Image generation failed: {image_error}")

# Step 2: Generate platform-specific copy
print(f"[{datetime.utcnow().isoformat()}] Generating platform-specific copy...")
copy_prompt = f"""Generate 5 platform-specific social media posts for this event:

Event: {event_title}
Date: {event_date} at {event_time}
Location: {event_location}
Description: {event_description}
RSVP Link: {event_url}

Return JSON with keys: twitter, linkedin, instagram, facebook, discord

Guidelines:
- Twitter: Concise, hashtags, under 280 chars
- LinkedIn: Professional, detailed, industry-focused
- Instagram: Engaging, emoji-friendly, hashtags
- Facebook: Conversational, community-focused
- Discord: Markdown formatting, casual tone
"""

copy_response, copy_error = invoke_llm(copy_prompt)
if copy_error:
    print(f"[{datetime.utcnow().isoformat()}] Copy generation failed, using defaults")
    default_copy = f"{event_title}\n\n{event_date} at {event_time}\n{event_location}\n\nRSVP: {event_url}"
    copies = {
        "twitter": default_copy[:280],
        "linkedin": default_copy,
        "instagram": default_copy,
        "facebook": default_copy,
        "discord": f"**{event_title}**\n\n{default_copy}"
    }
else:
    copies = extract_json_from_text(copy_response)
    required_keys = ["twitter", "linkedin", "instagram", "facebook", "discord"]
    if not copies or not all(k in copies for k in required_keys):
        print(f"[{datetime.utcnow().isoformat()}] JSON extraction incomplete, using default copy")
        default_copy = f"{event_title}\n\n{event_date} at {event_time}\n{event_location}\n\nRSVP: {event_url}"
        copies = {
            "twitter": default_copy[:280],
            "linkedin": default_copy,
            "instagram": default_copy,
            "facebook": default_copy,
            "discord": f"**{event_title}**\n\n{default_copy}"
        }

# Step 3: Post to each platform using generic posting function

def extract_data(result):
    """Extract data from Composio's double-nested response format"""
    if not result:
        return {}
    data = result.get("data", {})
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    return data if isinstance(data, dict) else {}


def post_to_platform(name, tool_name, payload, prereq_check=None):
    """
    Generic function to post to any social platform.

    Args:
        name: Platform name (for logging and skip check)
        tool_name: Composio tool slug
        payload: Dict of arguments for the tool
        prereq_check: Optional callable that returns (success, skip_reason) tuple

    Returns:
        Status string: "success", "skipped", "skipped: <reason>", or "failed: <error>"
    """
    if name in skip_platforms:
        return "skipped"

    if prereq_check:
        success, reason = prereq_check()
        if not success:
            return f"skipped: {reason}" if reason else "skipped"

    print(f"[{datetime.utcnow().isoformat()}] Posting to {name.title()}...")

    result, error = run_composio_tool(tool_name, payload)
    return "success" if not error else f"failed: {error}"


def post_to_twitter():
    """Post event to Twitter"""
    tweet_text = copies.get("twitter", event_title)[:280]
    if results["image_url"]:
        tweet_text = tweet_text[:250] + f"\n\n{results['image_url']}"

    return post_to_platform("twitter", "TWITTER_CREATION_OF_A_POST", {"text": tweet_text})


def post_to_linkedin():
    """Post event to LinkedIn with auto-discovered user URN"""
    if "linkedin" in skip_platforms:
        return "skipped"

    print(f"[{datetime.utcnow().isoformat()}] Posting to LinkedIn...")

    # Auto-discover user URN
    profile_result, profile_error = run_composio_tool("LINKEDIN_GET_MY_INFO", {})
    if profile_error:
        return f"failed: Could not get profile - {profile_error}"

    profile_data = extract_data(profile_result)
    li_id = profile_data.get("id", "")
    if not li_id:
        return "failed: Could not determine user URN"

    author_urn = li_id if li_id.startswith("urn:li:") else f"urn:li:person:{li_id}"

    li_text = copies.get("linkedin", event_description)
    if event_url:
        li_text += f"\n\nRSVP: {event_url}"

    result, error = run_composio_tool("LINKEDIN_CREATE_LINKED_IN_POST", {
        "author": author_urn,
        "commentary": li_text,
        "visibility": "PUBLIC"
    })
    return "success" if not error else f"failed: {error}"


def post_to_instagram():
    """Post event to Instagram with auto-discovered user ID"""
    if "instagram" in skip_platforms:
        return "skipped"

    if not results["image_url"]:
        return "skipped: No image available"

    print(f"[{datetime.utcnow().isoformat()}] Posting to Instagram...")

    # Auto-discover user ID
    user_result, user_error = run_composio_tool("INSTAGRAM_GET_USER_INFO", {})
    if user_error:
        return f"failed: Could not get user info - {user_error}"

    user_data = extract_data(user_result)
    ig_user_id = str(user_data.get("id", ""))
    if not ig_user_id:
        return "failed: Could not determine user ID"

    # 3-step Instagram posting: create container, poll status, publish
    container_result, container_error = run_composio_tool("INSTAGRAM_CREATE_MEDIA_CONTAINER", {
        "ig_user_id": ig_user_id,
        "image_url": results["image_url"],
        "caption": copies.get("instagram", event_description)
    })
    if container_error:
        return f"failed: Container creation - {container_error}"

    container_data = extract_data(container_result)
    creation_id = container_data.get("id", "")
    if not creation_id:
        return "failed: No container ID returned"

    import time
    for _ in range(30):
        time.sleep(5)
        status_result, _ = run_composio_tool("INSTAGRAM_GET_POST_STATUS", {
            "ig_user_id": ig_user_id, "creation_id": creation_id
        })
        if status_result:
            sd = extract_data(status_result)
            if sd.get("status_code") == "FINISHED":
                pub_result, pub_error = run_composio_tool("INSTAGRAM_CREATE_POST", {
                    "ig_user_id": ig_user_id, "creation_id": creation_id
                })
                return "success" if not pub_error else f"failed: Publish - {pub_error}"
            elif sd.get("status_code") == "ERROR":
                return "failed: Media processing error"

    return "failed: Media processing timeout"


def post_to_facebook():
    """Post event to Facebook page"""
    def check_page_id():
        return (bool(facebook_page_id), "No page ID provided" if not facebook_page_id else None)

    fb_message = copies.get("facebook", event_description)
    if event_url:
        fb_message += f"\n\nRSVP: {event_url}"

    return post_to_platform(
        "facebook",
        "FACEBOOK_CREATE_POST",
        {"page_id": facebook_page_id, "message": fb_message},
        prereq_check=check_page_id
    )


def post_to_discord():
    """Post event to Discord channel"""
    def check_channel_id():
        return (bool(discord_channel_id), "No channel ID provided" if not discord_channel_id else None)

    dc_content = copies.get("discord", f"**{event_title}**\n\n{event_description}")
    if event_url:
        dc_content += f"\n\nRSVP: {event_url}"

    return post_to_platform(
        "discord",
        "DISCORDBOT_CREATE_MESSAGE",
        {"channel_id": discord_channel_id, "content": dc_content},
        prereq_check=check_channel_id
    )

# Execute posts in parallel
with ThreadPoolExecutor(max_workers=5) as executor:
    twitter_future = executor.submit(post_to_twitter)
    linkedin_future = executor.submit(post_to_linkedin)
    instagram_future = executor.submit(post_to_instagram)
    facebook_future = executor.submit(post_to_facebook)
    discord_future = executor.submit(post_to_discord)

    results["twitter_posted"] = twitter_future.result()
    results["linkedin_posted"] = linkedin_future.result()
    results["instagram_posted"] = instagram_future.result()
    results["facebook_posted"] = facebook_future.result()
    results["discord_posted"] = discord_future.result()

# Build summary
success_count = sum(1 for status in [
    results["twitter_posted"],
    results["linkedin_posted"],
    results["instagram_posted"],
    results["facebook_posted"],
    results["discord_posted"]
] if status == "success")

results["summary"] = f"Posted to {success_count}/5 platforms"

print(f"[{datetime.utcnow().isoformat()}] Workflow complete: {results['summary']}")
print(f"Twitter: {results['twitter_posted']}")
print(f"LinkedIn: {results['linkedin_posted']}")
print(f"Instagram: {results['instagram_posted']}")
print(f"Facebook: {results['facebook_posted']}")
print(f"Discord: {results['discord_posted']}")

output = results
output
