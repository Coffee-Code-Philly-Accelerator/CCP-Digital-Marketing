# CCP Marketing

Event creation and social media promotion using Composio SDK.

## Installation

```bash
pip install ccp-marketing
```

## Usage

### CLI

```bash
# Create an event
ccp-marketing create-event \
  --title "AI Workshop" \
  --date "January 25, 2025" \
  --time "6:00 PM EST" \
  --location "The Station, Philadelphia" \
  --description "Join us for a hands-on workshop"

# Promote an event
ccp-marketing promote \
  --title "AI Workshop" \
  --date "January 25, 2025" \
  --time "6:00 PM EST" \
  --location "The Station, Philadelphia" \
  --description "Join us for a hands-on workshop" \
  --event-url "https://lu.ma/ai-workshop"

# Full workflow (create + promote)
ccp-marketing full-workflow \
  --title "AI Workshop" \
  --date "January 25, 2025" \
  --time "6:00 PM EST" \
  --location "The Station, Philadelphia" \
  --description "Join us for a hands-on workshop"
```

### Library

```python
from ccp_marketing import CreateEventWorkflow, EventData, ComposioClient

client = ComposioClient()
event = EventData(
    title="AI Workshop",
    date="January 25, 2025",
    time="6:00 PM EST",
    location="Philadelphia",
    description="Learn AI basics..."
)

result = CreateEventWorkflow(client).run(event, platforms=["luma", "partiful"])
print(result.primary_url)
```

## Environment Variables

- `COMPOSIO_API_KEY` - Your Composio API key (required)
- `CCP_LOG_LEVEL` - Log level (default: INFO)
- `CCP_MAX_WORKERS` - Parallel workers (default: 5)
