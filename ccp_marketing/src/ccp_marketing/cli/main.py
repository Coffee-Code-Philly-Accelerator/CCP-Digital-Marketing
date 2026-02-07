"""CLI application for CCP Marketing."""

import json
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ccp_marketing.core.client import ComposioClient
from ccp_marketing.core.config import Config
from ccp_marketing.core.exceptions import CCPMarketingError
from ccp_marketing.models.event import EventData
from ccp_marketing.workflows import EventCreationWorkflow, SocialPromotionWorkflow, FullWorkflow

app = typer.Typer(
    name="ccp-marketing",
    help="CCP Digital Marketing - Event creation and social media promotion",
    no_args_is_help=True,
)

console = Console()


def get_client() -> ComposioClient:
    """Get or create a Composio client."""
    try:
        config = Config.from_env()
        config.validate()
        return ComposioClient(config)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("\n[yellow]Set your API key:[/yellow]")
        console.print("  export COMPOSIO_API_KEY='your-api-key'")
        raise typer.Exit(1)


def print_result(result: dict, title: str = "Result") -> None:
    """Print result as formatted JSON."""
    console.print(Panel(
        json.dumps(result, indent=2, default=str),
        title=title,
        border_style="green",
    ))


@app.command("create-event")
def create_event(
    title: str = typer.Option(..., "--title", "-t", help="Event title"),
    date: str = typer.Option(..., "--date", "-d", help="Event date (e.g., 'January 25, 2025')"),
    time: str = typer.Option(..., "--time", help="Event time (e.g., '6:00 PM EST')"),
    location: str = typer.Option(..., "--location", "-l", help="Event location/venue"),
    description: str = typer.Option(..., "--description", help="Event description"),
    meetup_url: str = typer.Option("", "--meetup-url", "-m", help="Meetup group URL"),
    platforms: str = typer.Option(
        "luma,meetup,partiful",
        "--platforms",
        "-p",
        help="Comma-separated platforms to create on",
    ),
    skip: str = typer.Option("", "--skip", "-s", help="Comma-separated platforms to skip"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Create an event on Luma, Meetup, and/or Partiful."""
    client = get_client()

    event_data = EventData(
        title=title,
        date=date,
        time=time,
        location=location,
        description=description,
    )

    # Validate
    errors = event_data.validate()
    if errors:
        console.print("[red]Validation errors:[/red]")
        for error in errors:
            console.print(f"  - {error}")
        raise typer.Exit(1)

    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]
    skip_list = [p.strip() for p in skip.split(",") if p.strip()]

    workflow = EventCreationWorkflow(client)

    try:
        result = workflow.run(
            event_data=event_data,
            platforms=platform_list,
            skip_platforms=skip_list,
            meetup_group_url=meetup_url,
        )

        if json_output:
            console.print(json.dumps(result.to_dict(), indent=2, default=str))
        else:
            print_result(result.to_dict(), "Event Creation Results")
            if result.primary_url:
                console.print(f"\n[green]Primary URL:[/green] {result.primary_url}")

    except CCPMarketingError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("promote")
def promote_event(
    title: str = typer.Option(..., "--title", "-t", help="Event title"),
    date: str = typer.Option(..., "--date", "-d", help="Event date"),
    time: str = typer.Option(..., "--time", help="Event time"),
    location: str = typer.Option(..., "--location", "-l", help="Event location"),
    description: str = typer.Option(..., "--description", help="Event description"),
    event_url: str = typer.Option(..., "--event-url", "-u", help="Primary event RSVP URL"),
    discord_channel: str = typer.Option("", "--discord-channel", help="Discord channel ID"),
    facebook_page: str = typer.Option("", "--facebook-page", help="Facebook page ID"),
    skip: str = typer.Option("", "--skip", "-s", help="Comma-separated platforms to skip"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Promote an event on social media platforms."""
    client = get_client()

    event_data = EventData(
        title=title,
        date=date,
        time=time,
        location=location,
        description=description,
        url=event_url,
    )

    skip_list = [p.strip() for p in skip.split(",") if p.strip()]

    workflow = SocialPromotionWorkflow(client)

    try:
        result = workflow.run(
            event_data=event_data,
            event_url=event_url,
            skip_platforms=skip_list,
            discord_channel_id=discord_channel,
            facebook_page_id=facebook_page,
        )

        if json_output:
            console.print(json.dumps(result.to_dict(), indent=2, default=str))
        else:
            print_result(result.to_dict(), "Social Promotion Results")

    except CCPMarketingError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("full-workflow")
def full_workflow(
    title: str = typer.Option(..., "--title", "-t", help="Event title"),
    date: str = typer.Option(..., "--date", "-d", help="Event date"),
    time: str = typer.Option(..., "--time", help="Event time"),
    location: str = typer.Option(..., "--location", "-l", help="Event location"),
    description: str = typer.Option(..., "--description", help="Event description"),
    meetup_url: str = typer.Option("", "--meetup-url", "-m", help="Meetup group URL"),
    discord_channel: str = typer.Option("", "--discord-channel", help="Discord channel ID"),
    facebook_page: str = typer.Option("", "--facebook-page", help="Facebook page ID"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Run the full workflow: create event + promote on social media."""
    client = get_client()

    event_data = EventData(
        title=title,
        date=date,
        time=time,
        location=location,
        description=description,
    )

    # Validate
    errors = event_data.validate()
    if errors:
        console.print("[red]Validation errors:[/red]")
        for error in errors:
            console.print(f"  - {error}")
        raise typer.Exit(1)

    workflow = FullWorkflow(client)

    try:
        result = workflow.run(
            event_data=event_data,
            meetup_group_url=meetup_url,
            discord_channel_id=discord_channel,
            facebook_page_id=facebook_page,
        )

        if json_output:
            console.print(json.dumps(result.to_dict(), indent=2, default=str))
        else:
            console.print("\n")
            print_result(result.to_dict(), "Full Workflow Results")

            if result.primary_url:
                console.print(f"\n[green]Primary URL:[/green] {result.primary_url}")
            console.print(f"[dim]Duration: {result.duration_seconds:.1f}s[/dim]")

    except CCPMarketingError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("info")
def show_info(
    recipe: str = typer.Option(
        "all",
        "--recipe",
        "-r",
        help="Recipe to show info for (create, promote, all)",
    ),
) -> None:
    """Show information about available workflows."""
    table = Table(title="CCP Marketing Workflows")
    table.add_column("Workflow", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Platforms", style="green")

    if recipe in ("create", "all"):
        table.add_row(
            "create-event",
            "Create events on event platforms",
            "Luma, Meetup, Partiful",
        )

    if recipe in ("promote", "all"):
        table.add_row(
            "promote",
            "Promote on social media",
            "Twitter, LinkedIn, Instagram, Facebook, Discord",
        )

    if recipe == "all":
        table.add_row(
            "full-workflow",
            "Create event + promote (combined)",
            "All platforms",
        )

    console.print(table)

    console.print("\n[yellow]Environment Variables:[/yellow]")
    console.print("  COMPOSIO_API_KEY    Your Composio API key (required)")
    console.print("  CCP_LOG_LEVEL       Log level (default: INFO)")
    console.print("  CCP_MAX_WORKERS     Parallel workers (default: 5)")


@app.command("version")
def show_version() -> None:
    """Show version information."""
    from ccp_marketing import __version__
    console.print(f"CCP Marketing v{__version__}")


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
