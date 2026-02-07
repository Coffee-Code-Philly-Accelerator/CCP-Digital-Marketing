#!/usr/bin/env python3
"""
CCP Digital Marketing - Recipe Client

A Python client for executing Rube MCP recipes via the Composio API.

Recipes:
- Create Event on All Platforms (rcp_xvediVZu8BzW)
- Event Social Promotion (rcp_zBzqs2LO-miP)

Usage:
    python recipe_client.py create-event --title "AI Workshop" --date "Jan 25, 2025" ...
    python recipe_client.py promote --title "AI Workshop" --url "https://lu.ma/abc123" ...
    python recipe_client.py full-workflow --title "AI Workshop" --date "Jan 25, 2025" ...

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
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


# =============================================================================
# Configuration
# =============================================================================

RECIPE_IDS = {
    "create_event": "rcp_xvediVZu8BzW",
    "social_promotion": "rcp_zBzqs2LO-miP",
}

COMPOSIO_API_BASE = "https://backend.composio.dev/api/v1"

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
            recipe_id: The recipe ID (e.g., "rcp_xvediVZu8BzW")
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
    platforms: str = "luma,meetup,partiful",
    skip_platforms: str = "",
) -> Dict[str, Any]:
    """
    Create an event on Luma, Meetup, and Partiful.

    Args:
        client: ComposioRecipeClient instance
        title: Event title
        date: Event date (e.g., "January 25, 2025")
        time: Event time with timezone (e.g., "6:00 PM EST")
        location: Venue or address
        description: Event description
        meetup_group_url: Meetup group URL (required for Meetup)
        platforms: Comma-separated platforms to create on
        skip_platforms: Comma-separated platforms to skip

    Returns:
        Recipe execution result with event URLs
    """
    input_data = {
        "event_title": title,
        "event_date": date,
        "event_time": time,
        "event_location": location,
        "event_description": description,
        "meetup_group_url": meetup_group_url,
        "platforms": platforms,
        "skip_platforms": skip_platforms,
    }

    return client.execute_recipe(RECIPE_IDS["create_event"], input_data)


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
) -> Dict[str, Any]:
    """
    Run the full workflow: create event + promote on social media.

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

    Returns:
        Combined results from both recipes
    """
    print("\n" + "=" * 60)
    print("PHASE 1: Creating Events")
    print("=" * 60 + "\n")

    create_result = create_event(
        client=client,
        title=title,
        date=date,
        time=time,
        location=location,
        description=description,
        meetup_group_url=meetup_group_url,
    )

    # Extract primary event URL for promotion
    event_url = (
        create_result.get("luma_url")
        or create_result.get("meetup_url")
        or create_result.get("partiful_url")
        or ""
    )

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
    )

    return {
        "event_creation": create_result,
        "social_promotion": promote_result,
        "primary_event_url": event_url,
    }


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
    --meetup-url "https://meetup.com/coffee-code-philly"

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
    --meetup-url "https://meetup.com/coffee-code-philly"

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
    create_parser.add_argument("--platforms", default="luma,meetup,partiful", help="Platforms to create on")
    create_parser.add_argument("--skip", default="", help="Platforms to skip")

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

    # info command
    info_parser = subparsers.add_parser("info", help="Get recipe information")
    info_parser.add_argument("--recipe", choices=["create", "promote", "all"], default="all")

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
            platforms=args.platforms,
            skip_platforms=args.skip,
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
        )
    elif args.command == "info":
        if args.recipe in ("create", "all"):
            print("\n--- Create Event Recipe ---")
            print(json.dumps(client.get_recipe_details(RECIPE_IDS["create_event"]), indent=2))
        if args.recipe in ("promote", "all"):
            print("\n--- Social Promotion Recipe ---")
            print(json.dumps(client.get_recipe_details(RECIPE_IDS["social_promotion"]), indent=2))
        sys.exit(0)

    # Print result
    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
