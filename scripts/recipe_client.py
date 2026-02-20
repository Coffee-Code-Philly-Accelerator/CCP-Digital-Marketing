#!/usr/bin/env python3
"""
CCP Digital Marketing - Recipe Client

A Python client for executing Rube MCP recipes via the Composio API.

Recipes:
- Create Event on Luma (rcp_mXyFyALaEsQF)
- Create Event on Meetup (rcp_kHJoI1WmR3AR)
- Create Event on Partiful (rcp_bN7jRF5P_Kf0)
- Event Social Promotion (rcp_X65IirgPhwh3)
- Generic Social Post (rcp_PLACEHOLDER)

Usage:
    python recipe_client.py create-event --title "AI Workshop" --date "Jan 25, 2025" ...
    python recipe_client.py promote --title "AI Workshop" --url "https://lu.ma/abc123" ...
    python recipe_client.py full-workflow --title "AI Workshop" --date "Jan 25, 2025" ...
    python recipe_client.py social-post --topic "News" --content "Big announcement!" ...

Environment:
    COMPOSIO_API_KEY - Your Composio API key (required)
"""

import os
import sys
import json
import argparse
import time
from datetime import datetime
from typing import Optional, Dict, Any

try:
    import requests
except ImportError:
    print("Error: 'requests' package required. Install with: pip install requests")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass  # dotenv is optional


# =============================================================================
# Configuration
# =============================================================================

RECIPE_IDS = {
    "luma_create": "rcp_mXyFyALaEsQF",
    "meetup_create": "rcp_kHJoI1WmR3AR",
    "partiful_create": "rcp_bN7jRF5P_Kf0",
    "social_promotion": "rcp_X65IirgPhwh3",
    "social_post": "rcp_PLACEHOLDER",
}

EVENT_PLATFORMS = ["luma", "meetup", "partiful"]

COMPOSIO_API_BASE = os.environ.get(
    "CCP_COMPOSIO_API_BASE", "https://backend.composio.dev/api/v1"
)

# Keys that should be redacted in logs
SENSITIVE_KEYS = {"api_key", "password", "secret", "token", "credential", "auth"}


def redact_sensitive_data(data, sensitive_keys=SENSITIVE_KEYS):
    """
    Redact sensitive values from a dictionary for safe logging.

    Args:
        data: Dictionary to redact
        sensitive_keys: Set of key substrings to redact

    Returns:
        New dictionary with sensitive values replaced with "***REDACTED***"
    """
    if not isinstance(data, dict):
        return data

    redacted = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(sk in key_lower for sk in sensitive_keys):
            redacted[key] = "***REDACTED***"
        elif isinstance(value, dict):
            redacted[key] = redact_sensitive_data(value, sensitive_keys)
        else:
            redacted[key] = value
    return redacted


# =============================================================================
# API Client
# =============================================================================

class ComposioRecipeClient:
    """Client for executing Composio/Rube MCP recipes."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("COMPOSIO_API_KEY")
        if not self.api_key:
            raise ValueError(
                "COMPOSIO_API_KEY not found. Set it as an environment variable "
                "or pass it to the constructor."
            )
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def execute_recipe(
        self,
        recipe_id: str,
        input_data: Dict[str, Any],
        wait_for_completion: bool = True,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """
        Execute a recipe with the given input data.

        Args:
            recipe_id: The recipe ID (e.g., "rcp_mXyFyALaEsQF")
            input_data: Dictionary of input parameters
            wait_for_completion: Whether to poll until completion
            timeout: Maximum seconds to wait

        Returns:
            Recipe execution result
        """
        url = f"{COMPOSIO_API_BASE}/recipes/{recipe_id}/execute"

        print(f"[{self._timestamp()}] Executing recipe: {recipe_id}")
        print(f"[{self._timestamp()}] Input: {json.dumps(redact_sensitive_data(input_data), indent=2)}")

        try:
            response = self.session.post(url, json={"input_data": input_data})
            response.raise_for_status()
            result = response.json()

            if wait_for_completion and result.get("execution_id"):
                return self._poll_execution(result["execution_id"], timeout)

            return result

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else "unknown"
            # Truncate error details to avoid exposing sensitive API responses
            error_detail = (e.response.text[:500] + "...") if e.response and len(e.response.text) > 500 else (e.response.text if e.response else str(e))
            print(f"[{self._timestamp()}] HTTP Error: {status_code}")
            print(f"[{self._timestamp()}] Details: {error_detail}")
            return {"error": f"HTTP {status_code}", "details": error_detail}
        except requests.exceptions.RequestException as e:
            print(f"[{self._timestamp()}] Request error: {type(e).__name__}: {e}")
            return {"error": f"{type(e).__name__}: {e}"}
        except Exception as e:
            print(f"[{self._timestamp()}] Unexpected error: {type(e).__name__}: {e}")
            return {"error": str(e)}

    def _poll_execution(self, execution_id: str, timeout: int) -> Dict[str, Any]:
        """Poll for execution completion."""
        url = f"{COMPOSIO_API_BASE}/executions/{execution_id}"
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = self.session.get(url)
                response.raise_for_status()
                result = response.json()

                status = result.get("status", "unknown")
                print(f"[{self._timestamp()}] Status: {status}")

                if status in ("completed", "success", "finished"):
                    return result
                elif status in ("failed", "error"):
                    return result

                time.sleep(5)  # Poll every 5 seconds

            except requests.exceptions.RequestException as e:
                print(f"[{self._timestamp()}] Poll error: {type(e).__name__}: {e}")
                time.sleep(5)

        return {"error": "Timeout waiting for execution", "execution_id": execution_id}

    def get_recipe_details(self, recipe_id: str) -> Dict[str, Any]:
        """Get recipe metadata and schema."""
        url = f"{COMPOSIO_API_BASE}/recipes/{recipe_id}"
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"{type(e).__name__}: {e}"}

    @staticmethod
    def _timestamp() -> str:
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


# =============================================================================
# Recipe Wrappers
# =============================================================================

def create_event(
    client: ComposioRecipeClient,
    title: str,
    date: str,
    time: str,
    location: str,
    description: str,
    meetup_group_url: str = "",
    skip_platforms: str = "",
    provider: str = "hyperbrowser",
) -> Dict[str, Any]:
    """
    Create an event on Luma, Meetup, and Partiful (sequentially, per-platform recipes).

    Args:
        client: ComposioRecipeClient instance
        title: Event title
        date: Event date (e.g., "January 25, 2025")
        time: Event time with timezone (e.g., "6:00 PM EST")
        location: Venue or address
        description: Event description
        meetup_group_url: Meetup group URL (required for Meetup)
        skip_platforms: Comma-separated platforms to skip

    Returns:
        Dict with per-platform results
    """
    skip_set = {s.strip().lower() for s in skip_platforms.split(",") if s.strip()}
    results = {}

    for platform in EVENT_PLATFORMS:
        if platform in skip_set:
            print(f"\n--- Skipping {platform} (user requested) ---")
            results[platform] = {"status": "skipped"}
            continue

        print(f"\n--- Creating event on {platform} ---")

        input_data = {
            "event_title": title,
            "event_date": date,
            "event_time": time,
            "event_location": location,
            "event_description": description,
            "CCP_BROWSER_PROVIDER": provider,
        }

        # Add meetup-specific input
        if platform == "meetup" and meetup_group_url:
            input_data["meetup_group_url"] = meetup_group_url

        recipe_key = f"{platform}_create"
        result = client.execute_recipe(RECIPE_IDS[recipe_key], input_data)
        results[platform] = result

    return results


def promote_event(
    client: ComposioRecipeClient,
    title: str,
    date: str,
    time: str,
    location: str,
    description: str,
    event_url: str,
    discord_channel_id: str = "",
    facebook_page_id: str = "",
    skip_platforms: str = "",
) -> Dict[str, Any]:
    """
    Promote an event on social media platforms.

    Args:
        client: ComposioRecipeClient instance
        title: Event title
        date: Event date
        time: Event time
        location: Event location
        description: Event description
        event_url: Primary RSVP URL
        discord_channel_id: Discord channel ID (optional)
        facebook_page_id: Facebook page ID (optional)
        skip_platforms: Comma-separated platforms to skip

    Returns:
        Recipe execution result with post confirmations
    """
    input_data = {
        "event_title": title,
        "event_date": date,
        "event_time": time,
        "event_location": location,
        "event_description": description,
        "event_url": event_url,
        "discord_channel_id": discord_channel_id,
        "facebook_page_id": facebook_page_id,
        "skip_platforms": skip_platforms,
    }

    return client.execute_recipe(RECIPE_IDS["social_promotion"], input_data)


def full_workflow(
    client: ComposioRecipeClient,
    title: str,
    date: str,
    time: str,
    location: str,
    description: str,
    meetup_group_url: str = "",
    discord_channel_id: str = "",
    facebook_page_id: str = "",
    skip_platforms: str = "",
    provider: str = "hyperbrowser",
) -> Dict[str, Any]:
    """
    Run the full workflow: create event on all platforms + promote on social media.

    Args:
        client: ComposioRecipeClient instance
        title: Event title
        date: Event date
        time: Event time
        location: Event location
        description: Event description
        meetup_group_url: Meetup group URL
        discord_channel_id: Discord channel ID
        facebook_page_id: Facebook page ID
        skip_platforms: Comma-separated platforms to skip

    Returns:
        Combined results from both phases
    """
    print("\n" + "=" * 60)
    print("PHASE 1: Creating Events")
    print("=" * 60 + "\n")

    create_results = create_event(
        client=client,
        title=title,
        date=date,
        time=time,
        location=location,
        description=description,
        meetup_group_url=meetup_group_url,
        skip_platforms=skip_platforms,
        provider=provider,
    )

    # Extract primary event URL for promotion (prefer luma > meetup > partiful)
    event_url = ""
    for platform in EVENT_PLATFORMS:
        platform_result = create_results.get(platform, {})
        if isinstance(platform_result, dict):
            url = (
                platform_result.get("event_url")
                or platform_result.get(f"{platform}_url")
                or platform_result.get("url")
                or ""
            )
            if url:
                event_url = url
                break

    if not event_url:
        print("\nWarning: No event URL captured. Promotion will proceed without link.")

    print("\n" + "=" * 60)
    print("PHASE 2: Social Media Promotion")
    print("=" * 60 + "\n")

    promote_result = promote_event(
        client=client,
        title=title,
        date=date,
        time=time,
        location=location,
        description=description,
        event_url=event_url,
        discord_channel_id=discord_channel_id,
        facebook_page_id=facebook_page_id,
        skip_platforms=skip_platforms,
    )

    return {
        "event_creation": create_results,
        "social_promotion": promote_result,
        "primary_event_url": event_url,
    }


def post_to_social(
    client: ComposioRecipeClient,
    topic: str,
    content: str,
    url: str = "",
    image_url: str = "",
    image_prompt: str = "",
    tone: str = "",
    cta: str = "",
    hashtags: str = "",
    discord_channel_id: str = "",
    facebook_page_id: str = "",
    skip_platforms: str = "",
) -> Dict[str, Any]:
    """
    Post generic content to social media platforms.

    Args:
        client: ComposioRecipeClient instance
        topic: What the post is about
        content: Main message/body text
        url: Link to include in posts
        image_url: Reuse existing image (skips Gemini)
        image_prompt: Custom Gemini prompt for image generation
        tone: Style: engaging, professional, casual, excited, informative
        cta: Call-to-action text
        hashtags: Custom hashtags to include
        discord_channel_id: Discord channel ID
        facebook_page_id: Facebook page ID
        skip_platforms: Comma-separated platforms to skip

    Returns:
        Recipe execution result with post confirmations
    """
    input_data = {
        "topic": topic,
        "content": content,
        "url": url,
        "image_url": image_url,
        "image_prompt": image_prompt,
        "tone": tone,
        "cta": cta,
        "hashtags": hashtags,
        "discord_channel_id": discord_channel_id,
        "facebook_page_id": facebook_page_id,
        "skip_platforms": skip_platforms,
    }

    return client.execute_recipe(RECIPE_IDS["social_post"], input_data)


# =============================================================================
# CLI Interface
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="CCP Digital Marketing - Recipe Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create event on all platforms
  python recipe_client.py create-event \\
    --title "AI Workshop" \\
    --date "January 25, 2025" \\
    --time "6:00 PM EST" \\
    --location "The Station, Philadelphia" \\
    --description "Join us for a hands-on workshop..." \\
    --meetup-url "https://www.meetup.com/code-coffee-philly"

  # Promote an existing event
  python recipe_client.py promote \\
    --title "AI Workshop" \\
    --date "January 25, 2025" \\
    --time "6:00 PM EST" \\
    --location "Philadelphia" \\
    --description "Join us..." \\
    --event-url "https://lu.ma/abc123"

  # Full workflow (create + promote)
  python recipe_client.py full-workflow \\
    --title "AI Workshop" \\
    --date "January 25, 2025" \\
    --time "6:00 PM EST" \\
    --location "The Station, Philadelphia" \\
    --description "Join us..." \\
    --meetup-url "https://www.meetup.com/code-coffee-philly"

  # Generic social post (not event-specific)
  python recipe_client.py social-post \\
    --topic "New Partnership" \\
    --content "We're partnering with TechHub!" \\
    --url "https://example.com" \\
    --tone "excited"

  # Get recipe info
  python recipe_client.py info --recipe all

Recipes:
  luma_create       rcp_mXyFyALaEsQF  Create event on Luma
  meetup_create     rcp_kHJoI1WmR3AR  Create event on Meetup
  partiful_create   rcp_bN7jRF5P_Kf0  Create event on Partiful
  social_promotion  rcp_X65IirgPhwh3  Promote event on social media
  social_post       rcp_PLACEHOLDER   Generic social media post

Environment Variables:
  COMPOSIO_API_KEY    Your Composio API key (required)
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Common arguments
    def add_common_args(p):
        p.add_argument("--title", required=True, help="Event title")
        p.add_argument("--date", required=True, help="Event date (e.g., 'January 25, 2025')")
        p.add_argument("--time", required=True, help="Event time (e.g., '6:00 PM EST')")
        p.add_argument("--location", required=True, help="Event location/venue")
        p.add_argument("--description", required=True, help="Event description")

    # create-event command
    create_parser = subparsers.add_parser("create-event", help="Create event on platforms")
    add_common_args(create_parser)
    create_parser.add_argument("--meetup-url", default="", help="Meetup group URL")
    create_parser.add_argument("--skip", default="", help="Platforms to skip (e.g., 'meetup,partiful')")
    create_parser.add_argument("--provider", choices=["hyperbrowser", "browser_tool"], default="hyperbrowser", help="Browser automation provider")

    # promote command
    promote_parser = subparsers.add_parser("promote", help="Promote event on social media")
    add_common_args(promote_parser)
    promote_parser.add_argument("--event-url", required=True, help="Primary event RSVP URL")
    promote_parser.add_argument("--discord-channel", default="", help="Discord channel ID")
    promote_parser.add_argument("--facebook-page", default="", help="Facebook page ID")
    promote_parser.add_argument("--skip", default="", help="Platforms to skip")

    # full-workflow command
    full_parser = subparsers.add_parser("full-workflow", help="Create event + promote (full workflow)")
    add_common_args(full_parser)
    full_parser.add_argument("--meetup-url", default="", help="Meetup group URL")
    full_parser.add_argument("--discord-channel", default="", help="Discord channel ID")
    full_parser.add_argument("--facebook-page", default="", help="Facebook page ID")
    full_parser.add_argument("--skip", default="", help="Platforms to skip")
    full_parser.add_argument("--provider", choices=["hyperbrowser", "browser_tool"], default="hyperbrowser", help="Browser automation provider")

    # social-post command
    social_post_parser = subparsers.add_parser("social-post", help="Post generic content to social media")
    social_post_parser.add_argument("--topic", required=True, help="What the post is about")
    social_post_parser.add_argument("--content", required=True, help="Main message/body text")
    social_post_parser.add_argument("--url", default="", help="Link to include in posts")
    social_post_parser.add_argument("--image-url", default="", help="Reuse existing image URL (skips Gemini)")
    social_post_parser.add_argument("--image-prompt", default="", help="Custom Gemini prompt for image generation")
    social_post_parser.add_argument("--tone", default="", help="Style: engaging, professional, casual, excited, informative")
    social_post_parser.add_argument("--cta", default="", help="Call-to-action text")
    social_post_parser.add_argument("--hashtags", default="", help="Custom hashtags to include")
    social_post_parser.add_argument("--discord-channel", default="", help="Discord channel ID")
    social_post_parser.add_argument("--facebook-page", default="", help="Facebook page ID")
    social_post_parser.add_argument("--skip", default="", help="Platforms to skip")

    # info command
    info_parser = subparsers.add_parser("info", help="Get recipe information")
    info_parser.add_argument("--recipe", choices=["luma", "meetup", "partiful", "promote", "social-post", "all"], default="all")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize client
    try:
        client = ComposioRecipeClient()
    except ValueError as e:
        print(f"Error: {e}")
        print("\nSet your API key:")
        print("  export COMPOSIO_API_KEY='your-api-key'")
        sys.exit(1)

    # Execute command
    if args.command == "create-event":
        result = create_event(
            client=client,
            title=args.title,
            date=args.date,
            time=args.time,
            location=args.location,
            description=args.description,
            meetup_group_url=args.meetup_url,
            skip_platforms=args.skip,
            provider=args.provider,
        )
    elif args.command == "promote":
        result = promote_event(
            client=client,
            title=args.title,
            date=args.date,
            time=args.time,
            location=args.location,
            description=args.description,
            event_url=args.event_url,
            discord_channel_id=args.discord_channel,
            facebook_page_id=args.facebook_page,
            skip_platforms=args.skip,
        )
    elif args.command == "full-workflow":
        result = full_workflow(
            client=client,
            title=args.title,
            date=args.date,
            time=args.time,
            location=args.location,
            description=args.description,
            meetup_group_url=args.meetup_url,
            discord_channel_id=args.discord_channel,
            facebook_page_id=args.facebook_page,
            skip_platforms=args.skip,
            provider=args.provider,
        )
    elif args.command == "social-post":
        result = post_to_social(
            client=client,
            topic=args.topic,
            content=args.content,
            url=args.url,
            image_url=args.image_url,
            image_prompt=args.image_prompt,
            tone=args.tone,
            cta=args.cta,
            hashtags=args.hashtags,
            discord_channel_id=args.discord_channel,
            facebook_page_id=args.facebook_page,
            skip_platforms=args.skip,
        )
    elif args.command == "info":
        if args.recipe in ("luma", "all"):
            print("\n--- Luma Create Event Recipe ---")
            print(json.dumps(client.get_recipe_details(RECIPE_IDS["luma_create"]), indent=2))
        if args.recipe in ("meetup", "all"):
            print("\n--- Meetup Create Event Recipe ---")
            print(json.dumps(client.get_recipe_details(RECIPE_IDS["meetup_create"]), indent=2))
        if args.recipe in ("partiful", "all"):
            print("\n--- Partiful Create Event Recipe ---")
            print(json.dumps(client.get_recipe_details(RECIPE_IDS["partiful_create"]), indent=2))
        if args.recipe in ("promote", "all"):
            print("\n--- Social Promotion Recipe ---")
            print(json.dumps(client.get_recipe_details(RECIPE_IDS["social_promotion"]), indent=2))
        if args.recipe in ("social-post", "all"):
            print("\n--- Generic Social Post Recipe ---")
            print(json.dumps(client.get_recipe_details(RECIPE_IDS["social_post"]), indent=2))
        sys.exit(0)

    # Print result
    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
