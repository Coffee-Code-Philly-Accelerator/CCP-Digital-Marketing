"""
RECIPE: Event Social Promotion
RECIPE ID: rcp_zBzqs2LO-miP

FLOW: Event Details → Gemini Image → LLM Copy → Parallel Social Posting

VERSION HISTORY:
v2 (current): Added auto-discovery for LinkedIn URN and Instagram User ID, graceful degradation
v1: Initial version with hardcoded platform IDs

API LEARNINGS:
- TWITTER_CREATION_OF_A_POST: Simple text post, image via URL
- LINKEDIN_GET_CURRENT_USER_PROFILE: Returns 'sub' field for URN construction
- LINKEDIN_CREATE_LINKED_IN_POST: Requires author URN, commentary, visibility
- INSTAGRAM_USERS_GET_LOGGED_IN_USER_INFO: Returns 'id' for user
- INSTAGRAM_MEDIA_POST_MEDIA: Requires user_id, image_url, caption, media_type
- FACEBOOK_CREATE_PAGE_POST: Requires page_id, message
- DISCORD_SEND_MESSAGE: Requires channel_id, content

KNOWN ISSUES:
- Instagram requires Business/Creator account
- Facebook requires page_manage_posts permission
- Discord requires bot in server with send message permission
"""

import os
import re
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

print(f"[{datetime.utcnow().isoformat()}] Starting social media promotion workflow")

# Get inputs
event_title = os.environ.get("event_title")
event_date = os.environ.get("event_date")
event_time = os.environ.get("event_time")
event_location = os.environ.get("event_location")
event_description = os.environ.get("event_description")
event_url = os.environ.get("event_url", "")
discord_channel_id = os.environ.get("discord_channel_id", "")
facebook_page_id = os.environ.get("facebook_page_id", "")
skip_platforms_str = os.environ.get("skip_platforms", "")

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

# Step 1: Generate promotional image
print(f"[{datetime.utcnow().isoformat()}] Generating promotional image...")
image_prompt = f"Create a modern, eye-catching event promotional graphic for: {event_title}. Style: professional, vibrant colors, suitable for social media. Do not include any text in the image."

image_result, image_error = run_composio_tool("GEMINI_GENERATE_IMAGE", {
    "prompt": image_prompt,
    "model": "imagen-3.0-generate-002"
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
    try:
        json_match = re.search(r'\{[^{}]*\}', copy_response, re.DOTALL)
        if json_match:
            copies = json.loads(json_match.group())
        else:
            raise ValueError("No JSON found")
    except:
        default_copy = f"{event_title}\n\n{event_date} at {event_time}\n{event_location}\n\nRSVP: {event_url}"
        copies = {
            "twitter": default_copy[:280],
            "linkedin": default_copy,
            "instagram": default_copy,
            "facebook": default_copy,
            "discord": f"**{event_title}**\n\n{default_copy}"
        }

# Step 3: Post to each platform
def post_to_twitter():
    if "twitter" in skip_platforms:
        return "skipped"

    print(f"[{datetime.utcnow().isoformat()}] Posting to Twitter...")
    tweet_text = copies.get("twitter", event_title)[:280]
    if results["image_url"]:
        tweet_text = tweet_text[:250] + f"\n\n{results['image_url']}"

    tw_result, tw_error = run_composio_tool("TWITTER_CREATION_OF_A_POST", {
        "text": tweet_text
    })

    return "success" if not tw_error else f"failed: {tw_error}"

def post_to_linkedin():
    if "linkedin" in skip_platforms:
        return "skipped"

    print(f"[{datetime.utcnow().isoformat()}] Posting to LinkedIn...")

    # Auto-discover user URN
    profile_result, profile_error = run_composio_tool("LINKEDIN_GET_CURRENT_USER_PROFILE", {})
    if profile_error:
        return f"failed: Could not get profile - {profile_error}"

    profile_data = profile_result.get("data", {})
    if "data" in profile_data:
        profile_data = profile_data["data"]

    sub = profile_data.get("sub", "")
    if not sub:
        return "failed: Could not determine user URN"

    author_urn = f"urn:li:person:{sub}"

    li_text = copies.get("linkedin", event_description)
    if event_url:
        li_text += f"\n\nRSVP: {event_url}"

    li_result, li_error = run_composio_tool("LINKEDIN_CREATE_LINKED_IN_POST", {
        "author": author_urn,
        "commentary": li_text,
        "visibility": "PUBLIC"
    })

    return "success" if not li_error else f"failed: {li_error}"

def post_to_instagram():
    if "instagram" in skip_platforms:
        return "skipped"

    if not results["image_url"]:
        return "skipped: No image available"

    print(f"[{datetime.utcnow().isoformat()}] Posting to Instagram...")

    # Auto-discover user ID
    user_result, user_error = run_composio_tool("INSTAGRAM_USERS_GET_LOGGED_IN_USER_INFO", {})
    if user_error:
        return f"failed: Could not get user info - {user_error}"

    user_data = user_result.get("data", {})
    if "data" in user_data:
        user_data = user_data["data"]

    user_id = user_data.get("id", "")
    if not user_id:
        return "failed: Could not determine user ID"

    ig_caption = copies.get("instagram", event_description)

    ig_result, ig_error = run_composio_tool("INSTAGRAM_MEDIA_POST_MEDIA", {
        "user_id": user_id,
        "image_url": results["image_url"],
        "caption": ig_caption,
        "media_type": "IMAGE"
    })

    return "success" if not ig_error else f"failed: {ig_error}"

def post_to_facebook():
    if "facebook" in skip_platforms:
        return "skipped"

    if not facebook_page_id:
        return "skipped: No page ID provided"

    print(f"[{datetime.utcnow().isoformat()}] Posting to Facebook...")

    fb_message = copies.get("facebook", event_description)
    if event_url:
        fb_message += f"\n\nRSVP: {event_url}"

    fb_result, fb_error = run_composio_tool("FACEBOOK_CREATE_PAGE_POST", {
        "page_id": facebook_page_id,
        "message": fb_message
    })

    return "success" if not fb_error else f"failed: {fb_error}"

def post_to_discord():
    if "discord" in skip_platforms:
        return "skipped"

    if not discord_channel_id:
        return "skipped: No channel ID provided"

    print(f"[{datetime.utcnow().isoformat()}] Posting to Discord...")

    dc_content = copies.get("discord", f"**{event_title}**\n\n{event_description}")
    if event_url:
        dc_content += f"\n\nRSVP: {event_url}"

    dc_result, dc_error = run_composio_tool("DISCORD_SEND_MESSAGE", {
        "channel_id": discord_channel_id,
        "content": dc_content
    })

    return "success" if not dc_error else f"failed: {dc_error}"

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
