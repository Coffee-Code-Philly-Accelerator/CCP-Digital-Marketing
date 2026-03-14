# email-reply

Three-pass review system for email replies (clarity, grammar, tone). Supports generating replies from Gmail/Outlook messages or reviewing user-drafted replies.

## Invocation

This skill is triggered when the user wants to:
- "Review my email reply"
- "Help me write an email response"
- "Check this email draft"
- "Generate a reply to this email"

## Required Inputs

| Parameter | Type | Description |
|-----------|------|-------------|
| `mode` | string | "generate" (create reply from email) or "review" (review existing draft) |

### Generate Mode

| Parameter | Type | Description |
|-----------|------|-------------|
| `provider` | string | Email provider: "gmail" or "outlook" |
| `message_id` | string | Email message ID to reply to |

### Review Mode

| Parameter | Type | Description |
|-----------|------|-------------|
| `draft_text` | string | The reply text to review |

## Optional Inputs

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `context` | string | "" | Additional context for generation (e.g., "Be friendly and offer to meet next week") |

## Execution

Use the Rube MCP tool to execute the email reply recipe:

```
RUBE_EXECUTE_RECIPE(
    recipe_id="rcp_NLnlCNmIcIuN",
    input_data={
        "mode": "<generate or review>",
        "provider": "<gmail or outlook>",
        "message_id": "<email message ID>",
        "draft_text": "<reply text to review>",
        "context": "<optional context>"
    }
)
```

Only include parameters relevant to the chosen mode.

## Output

```json
{
  "mode": "generate",
  "reply_text": "Thank you for your email...",
  "pass1_clarity": {
    "score": "PASS",
    "feedback": "Message is clear and direct",
    "suggestions": []
  },
  "pass2_grammar": {
    "score": "PASS",
    "feedback": "No grammar issues found",
    "corrections": []
  },
  "pass3_tone": {
    "score": "PASS",
    "feedback": "Professional and friendly tone maintained",
    "adjustments": []
  },
  "overall_status": "APPROVED",
  "final_recommendation": "Reply is ready to send"
}
```

## Three-Pass Review System

| Pass | Focus | Evaluates |
|------|-------|-----------|
| Pass 1: Clarity | Message comprehension | Is the response clear? Does it address all points? Is it concise? |
| Pass 2: Grammar | Language mechanics | Spelling, punctuation, sentence structure, word choice |
| Pass 3: Tone | Emotional impact | Professional yet friendly? Appropriate formality? Respectful? |

## Connection Setup

**Gmail:**
- Requires `GMAIL_GET_MESSAGE` permission (read-only access)
- Connect via Composio: https://app.composio.dev/connections

**Outlook:**
- Requires `OUTLOOK_GET_MESSAGE` permission (Mail.Read scope)
- Connect via Composio: https://app.composio.dev/connections

## Platform Notes

- **Generate mode** reads the original email, generates a reply, then runs all 3 review passes on the generated reply
- **Review mode** takes user-written text and runs the 3 review passes without generating new content
- **`reply_text`** is only present in generate mode output
- **Scores** are "PASS" or "NEEDS_REVISION" — if any pass returns NEEDS_REVISION, the `overall_status` is "NEEDS_REVISION"
