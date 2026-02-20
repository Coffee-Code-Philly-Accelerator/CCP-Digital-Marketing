"""
RECIPE: Generic Social Post
RECIPE ID: rcp_PLACEHOLDER

FLOW: Topic + Content > Gemini Image > LLM Copy > Sequential Social Posting

VERSION HISTORY:
v1 (current): Initial version - generic social posting (not event-specific)

API LEARNINGS:
- Same platform APIs as social_promotion.py (event recipe)
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
- Twitter temporarily removed pending connection restoration
- All run_composio_tool calls must use string literals (not variables) for Rube validator
"""

import os
import json
import time
from datetime import datetime

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
        return '{"twitter": "mock tweet", "linkedin": "mock linkedin post", "instagram": "mock instagram caption", "facebook": "mock facebook post", "discord": "mock discord message"}', None

print(f"[{datetime.utcnow().isoformat()}] Starting generic social post workflow")


def sanitize_input(text, max_len=2000):
    if not text:
        return ""
    text = str(text)
    text = "".join(char for char in text if char >= " " or char in "\n\t")
    text = text.replace("```", "'''")
    text = text.replace("---", "___")
    return text[:max_len]


def extract_json_from_text(text):
    if not text:
        return {}
    start = text.find("{")
    if start == -1:
        return {}
    depth = 0
    for i, char in enumerate(text[start:], start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


def extract_data(result):
    if not result:
        return {}
    data = result.get("data", {})
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    return data if isinstance(data, dict) else {}


# ============================================================================
# Inputs
# ============================================================================

topic = sanitize_input(os.environ.get("topic"), max_len=200)
content = sanitize_input(os.environ.get("content"), max_len=5000)
url = os.environ.get("url", "")
cta = sanitize_input(os.environ.get("cta"), max_len=200)
existing_image_url = os.environ.get("image_url", "")
image_prompt_override = sanitize_input(os.environ.get("image_prompt"), max_len=500)
tone = sanitize_input(os.environ.get("tone"), max_len=50) or "engaging"
hashtags = sanitize_input(os.environ.get("hashtags"), max_len=500)
discord_channel_id = os.environ.get("discord_channel_id", "") or os.environ.get("CCP_DISCORD_CHANNEL_ID", "")
facebook_page_id = os.environ.get("facebook_page_id", "") or os.environ.get("CCP_FACEBOOK_PAGE_ID", "")
skip_platforms_str = os.environ.get("skip_platforms", "")

if not all([topic, content]):
    raise ValueError("Missing required inputs: topic and content are required")

skip_platforms = [p.strip().lower() for p in skip_platforms_str.split(",") if p.strip()]

results = {
    "twitter_posted": "skipped: connection not available",
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
    if image_prompt_override:
        image_prompt = image_prompt_override
    else:
        image_prompt = f"Create a modern, eye-catching social media graphic about: {topic}. Style: {tone}, vibrant colors, suitable for social media. Do not include any text in the image."

    image_result, image_error = run_composio_tool("GEMINI_GENERATE_IMAGE", {
        "prompt": image_prompt,
        "model": "gemini-2.5-flash-image"
    })

    if not image_error:
        image_data = extract_data(image_result)
        results["image_url"] = image_data.get("publicUrl", "")
        print(f"[{datetime.utcnow().isoformat()}] Image generated: {results['image_url']}")
    else:
        print(f"[{datetime.utcnow().isoformat()}] Image generation failed: {image_error}")

# Step 2: Generate platform-specific copy
print(f"[{datetime.utcnow().isoformat()}] Generating platform-specific copy...")

copy_prompt = f"""Generate 5 platform-specific social media posts about this topic:

Topic: {topic}
Content: {content}
"""

if url:
    copy_prompt += f"Link: {url}\n"
if cta:
    copy_prompt += f"Call to action: {cta}\n"
if hashtags:
    copy_prompt += f"Hashtags to include: {hashtags}\n"

copy_prompt += f"""Tone: {tone}

Return JSON with keys: twitter, linkedin, instagram, facebook, discord

Guidelines:
- Twitter: Concise, hashtags, under 280 chars
- LinkedIn: Professional, detailed, industry-focused
- Instagram: Engaging, emoji-friendly, hashtags
- Facebook: Conversational, community-focused
- Discord: Markdown formatting, casual tone
- If a link was provided, include it naturally in each post
- If a call to action was provided, incorporate it
"""

copy_response, copy_error = invoke_llm(copy_prompt)
if copy_error:
    print(f"[{datetime.utcnow().isoformat()}] Copy generation failed, using defaults")
    default_copy = f"{topic}\n\n{content}"
    if url:
        default_copy += f"\n\n{url}"
    copies = {
        "twitter": default_copy[:280],
        "linkedin": default_copy,
        "instagram": default_copy,
        "facebook": default_copy,
        "discord": f"**{topic}**\n\n{default_copy}"
    }
else:
    copies = extract_json_from_text(copy_response)
    required_keys = ["twitter", "linkedin", "instagram", "facebook", "discord"]
    if not copies or not all(k in copies for k in required_keys):
        print(f"[{datetime.utcnow().isoformat()}] JSON extraction incomplete, using default copy")
        default_copy = f"{topic}\n\n{content}"
        if url:
            default_copy += f"\n\n{url}"
        copies = {
            "twitter": default_copy[:280],
            "linkedin": default_copy,
            "instagram": default_copy,
            "facebook": default_copy,
            "discord": f"**{topic}**\n\n{default_copy}"
        }


# Step 3: Post to each platform
# NOTE: All run_composio_tool calls must use string literals (not variables)
# because the Rube recipe validator requires static tool name resolution.


def post_to_linkedin():
    if "linkedin" in skip_platforms:
        return "skipped"
    print(f"[{datetime.utcnow().isoformat()}] Posting to LinkedIn...")
    profile_result, profile_error = run_composio_tool("LINKEDIN_GET_MY_INFO", {})
    if profile_error:
        return f"failed: Could not get profile - {profile_error}"
    profile_data = extract_data(profile_result)
    li_id = profile_data.get("id", "")
    if not li_id:
        return "failed: Could not determine user URN"
    author_urn = li_id if li_id.startswith("urn:li:") else f"urn:li:person:{li_id}"
    li_text = copies.get("linkedin", content)
    if url:
        li_text += f"\n\n{url}"
    result, error = run_composio_tool("LINKEDIN_CREATE_LINKED_IN_POST", {
        "author": author_urn,
        "commentary": li_text,
        "visibility": "PUBLIC"
    })
    return "success" if not error else f"failed: {error}"


def post_to_instagram():
    if "instagram" in skip_platforms:
        return "skipped"
    if not results["image_url"]:
        return "skipped: No image available"
    print(f"[{datetime.utcnow().isoformat()}] Posting to Instagram...")
    user_result, user_error = run_composio_tool("INSTAGRAM_GET_USER_INFO", {})
    if user_error:
        return f"failed: Could not get user info - {user_error}"
    user_data = extract_data(user_result)
    ig_user_id = str(user_data.get("id", ""))
    if not ig_user_id:
        return "failed: Could not determine user ID"
    container_result, container_error = run_composio_tool("INSTAGRAM_CREATE_MEDIA_CONTAINER", {
        "ig_user_id": ig_user_id,
        "image_url": results["image_url"],
        "caption": copies.get("instagram", content)
    })
    if container_error:
        return f"failed: Container creation - {container_error}"
    container_data = extract_data(container_result)
    creation_id = container_data.get("id", "")
    if not creation_id:
        return "failed: No container ID returned"
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
    if "facebook" in skip_platforms:
        return "skipped"
    if not facebook_page_id:
        return "skipped: No page ID provided"
    print(f"[{datetime.utcnow().isoformat()}] Posting to Facebook...")
    fb_message = copies.get("facebook", content)
    if url:
        fb_message += f"\n\n{url}"
    result, error = run_composio_tool("FACEBOOK_CREATE_POST", {
        "page_id": facebook_page_id,
        "message": fb_message
    })
    return "success" if not error else f"failed: {error}"


def post_to_discord():
    if "discord" in skip_platforms:
        return "skipped"
    if not discord_channel_id:
        return "skipped: No channel ID provided"
    print(f"[{datetime.utcnow().isoformat()}] Posting to Discord...")
    dc_content = copies.get("discord", f"**{topic}**\n\n{content}")
    if url:
        dc_content += f"\n\n{url}"
    result, error = run_composio_tool("DISCORDBOT_CREATE_MESSAGE", {
        "channel_id": discord_channel_id,
        "content": dc_content
    })
    return "success" if not error else f"failed: {error}"


# Execute posts sequentially (ThreadPoolExecutor not supported in Rube runtime)
# Twitter skipped until connection is restored
results["linkedin_posted"] = post_to_linkedin()
results["instagram_posted"] = post_to_instagram()
results["facebook_posted"] = post_to_facebook()
results["discord_posted"] = post_to_discord()

# Build summary
success_count = sum(1 for s in [
    results["twitter_posted"],
    results["linkedin_posted"],
    results["instagram_posted"],
    results["facebook_posted"],
    results["discord_posted"]
] if s == "success")

results["summary"] = f"Posted to {success_count}/5 platforms"

print(f"[{datetime.utcnow().isoformat()}] Workflow complete: {results['summary']}")
print(f"Twitter: {results['twitter_posted']}")
print(f"LinkedIn: {results['linkedin_posted']}")
print(f"Instagram: {results['instagram_posted']}")
print(f"Facebook: {results['facebook_posted']}")
print(f"Discord: {results['discord_posted']}")

output = results
output
