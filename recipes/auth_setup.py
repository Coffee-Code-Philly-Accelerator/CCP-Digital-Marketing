"""
Hyperbrowser Auth Setup - Reference Script

Documents the Hyperbrowser persistent auth profile setup flow.
NOT a Rube recipe - this is a standalone reference script.

FLOW:
  1. HYPERBROWSER_CREATE_PROFILE - Create a persistent browser profile
  2. HYPERBROWSER_CREATE_SESSION - Open session with the new profile
  3. HYPERBROWSER_START_BROWSER_USE_TASK - AI agent navigates to login page for manual auth

If profile_id is provided, skip step 1 (re-auth flow using existing profile).

Login URLs:
  - Luma: https://lu.ma/signin
  - Meetup: https://www.meetup.com/login/
  - Partiful: https://partiful.com/login

Usage:
  # New profile setup
  python auth_setup.py --platform luma

  # Re-auth existing profile
  python auth_setup.py --platform luma --profile-id prof_abc123
"""

from datetime import datetime

LOGIN_URLS = {
    "luma": "https://lu.ma/signin",
    "meetup": "https://www.meetup.com/login/",
    "partiful": "https://partiful.com/login",
}


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
        if tool_name == "HYPERBROWSER_CREATE_PROFILE":
            return {"data": {"id": "mock_profile_001", "name": arguments.get("name", "mock")}}, None
        if tool_name == "HYPERBROWSER_CREATE_SESSION":
            return {"data": {"id": "mock_session_001", "liveUrl": "https://mock-hb-live-url.example.com"}}, None
        if tool_name == "HYPERBROWSER_START_BROWSER_USE_TASK":
            return {"data": {"jobId": "mock_hb_task_001", "sessionId": "mock_session_001"}}, None
        if tool_name == "HYPERBROWSER_GET_SESSION_DETAILS":
            return {"data": {"id": "mock_session_001", "liveUrl": "https://mock-hb-live-url.example.com"}}, None
        return {"data": {}}, None


def extract_data(result):
    if not result:
        return {}
    data = result.get("data", {})
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    return data if isinstance(data, dict) else {}


def auth_setup(platform, profile_id=None):
    """
    Set up or re-authenticate a Hyperbrowser persistent profile for a platform.

    Args:
        platform: One of 'luma', 'meetup', 'partiful'
        profile_id: Existing profile ID (skip creation if provided)

    Returns:
        Dict with profile_id, session_id, live_url for manual login
    """
    platform = sanitize_input(platform, max_len=50).lower()
    if platform not in LOGIN_URLS:
        raise ValueError(f"Unknown platform: {platform}. Must be one of: {', '.join(LOGIN_URLS.keys())}")

    login_url = LOGIN_URLS[platform]
    print(f"[{datetime.utcnow().isoformat()}] Starting auth setup for {platform}")

    # Step 1: Create profile (skip if profile_id provided)
    if profile_id:
        print(f"[{datetime.utcnow().isoformat()}] Using existing profile: {profile_id}")
    else:
        print(f"[{datetime.utcnow().isoformat()}] Creating new Hyperbrowser profile for {platform}...")
        profile_result, profile_error = run_composio_tool(
            "HYPERBROWSER_CREATE_PROFILE",
            {
                "name": f"ccp-{platform}-auth",
            },
        )
        if profile_error:
            raise Exception(f"Failed to create profile: {profile_error}")

        profile_data = extract_data(profile_result)
        profile_id = profile_data.get("id", "")
        if not profile_id:
            raise Exception(f"No profile ID returned. Full response: {profile_data}")
        print(f"[{datetime.utcnow().isoformat()}] Profile created: {profile_id}")

    # Step 2: Create session with the profile
    print(f"[{datetime.utcnow().isoformat()}] Creating session with profile {profile_id}...")
    session_result, session_error = run_composio_tool(
        "HYPERBROWSER_CREATE_SESSION",
        {
            "profile": {"id": profile_id, "persistChanges": True},
            "useStealth": True,
            "acceptCookies": True,
        },
    )
    if session_error:
        raise Exception(f"Failed to create session: {session_error}")

    session_data = extract_data(session_result)
    session_id = session_data.get("id", "")
    live_url = session_data.get("liveUrl", "")

    if not session_id:
        raise Exception(f"No session ID returned. Full response: {session_data}")
    print(f"[{datetime.utcnow().isoformat()}] Session created: {session_id}")

    # Step 3: Start browser task to navigate to login page
    print(f"[{datetime.utcnow().isoformat()}] Launching browser agent to navigate to {login_url}...")
    task_result, task_error = run_composio_tool(
        "HYPERBROWSER_START_BROWSER_USE_TASK",
        {
            "task": f"Navigate to {login_url} and wait. The user will complete the login manually.",
            "sessionOptions": {
                "profile": {"id": profile_id, "persistChanges": True},
                "useStealth": True,
                "acceptCookies": True,
            },
            "llm": "claude-sonnet-4-20250514",
            "maxSteps": 5,
            "useVision": True,
        },
    )
    if task_error:
        raise Exception(f"Failed to start browser task: {task_error}")

    task_data = extract_data(task_result)
    task_id = task_data.get("jobId", task_data.get("taskId", ""))

    # Get live URL if not already available
    if not live_url and session_id:
        session_detail_result, _ = run_composio_tool("HYPERBROWSER_GET_SESSION_DETAILS", {"id": session_id})
        if session_detail_result:
            detail_data = extract_data(session_detail_result)
            live_url = detail_data.get("liveUrl", "")

    if live_url:
        print(f"[{datetime.utcnow().isoformat()}] Live URL (open to complete login): {live_url}")

    result = {
        "platform": platform,
        "profile_id": profile_id,
        "session_id": session_id,
        "task_id": task_id,
        "live_url": live_url,
        "login_url": login_url,
        "instructions": f"Open the live URL to manually complete {platform} login. The profile will persist auth cookies for future use.",
    }

    print(f"\n{'=' * 60}")
    print(f"Auth Setup Complete for {platform}")
    print(f"{'=' * 60}")
    print(f"Profile ID: {profile_id}")
    print(f"Session ID: {session_id}")
    print(f"Live URL:   {live_url}")
    print("\nOpen the live URL in your browser to complete login.")
    print(f"Set CCP_{platform.upper()}_PROFILE_ID={profile_id} for future recipe runs.")

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hyperbrowser Auth Setup")
    parser.add_argument(
        "--platform", required=True, choices=["luma", "meetup", "partiful"], help="Platform to set up auth for"
    )
    parser.add_argument("--profile-id", default="", help="Existing profile ID (skip creation)")
    args = parser.parse_args()

    result = auth_setup(args.platform, profile_id=args.profile_id or None)
    print(f"\nResult: {result}")
