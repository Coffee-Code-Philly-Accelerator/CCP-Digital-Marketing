"""
RECIPE: Email Reply with Three-Pass Review
RECIPE ID: rcp_NLnlCNmIcIuN

FLOW: Read Email > Auto-detect Tone > Generate/Review Draft > Pass 1 (Clarity) > Pass 2 (Grammar) > Pass 3 (Tone) > Final Reply

VERSION HISTORY:
v1 (current): Initial version - three-pass review system with Gmail/Outlook integration

API LEARNINGS:
- GMAIL_GET_MESSAGE: Returns data.data with 'id', 'threadId', 'snippet', 'payload' (headers + body parts)
- OUTLOOK_GET_MESSAGE: Returns data.data with 'id', 'subject', 'body', 'from', 'toRecipients'
- Email body extraction requires parsing MIME parts for Gmail, direct 'body.content' for Outlook
- invoke_llm returns (response, error) tuple for LLM calls

KNOWN ISSUES:
- Gmail requires OAuth2 connection with gmail.readonly scope
- Outlook requires OAuth2 connection with Mail.Read scope
- Complex HTML emails may require additional parsing
- LLM JSON extraction can fail if response is not well-formed

THREE-PASS REVIEW METHODOLOGY:
Pass 1: Clarity & Coherence - Logical flow, completeness, ambiguities, structure
Pass 2: Spelling & Grammar - Typos, punctuation, grammar, sentence structure
Pass 3: Tone & Perception - Tone match, emotional impact, recipient perception
"""

import base64
import json
import os
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
        if "GET_MESSAGE" in tool_name:
            return {
                "data": {
                    "data": {
                        "id": "mock_msg_id",
                        "subject": "Re: Project Status Update",
                        "snippet": "Hi there, can you provide an update?",
                        "payload": {
                            "headers": [{"name": "Subject", "value": "Re: Project Status Update"}],
                            "body": {
                                "data": base64.b64encode(
                                    b"Hi there, can you provide an update on the project?"
                                ).decode()
                            },
                        },
                        "from": {"emailAddress": {"address": "sender@example.com"}},
                    }
                }
            }, None
        return {"data": {"mock": True}}, None


try:
    # Check if invoke_llm is available (injected by Composio runtime)
    invoke_llm
except NameError:

    def invoke_llm(prompt):
        """Mock implementation for local testing"""
        print(f"[MOCK] invoke_llm(prompt length={len(prompt)})")
        if "CLARITY" in prompt:
            return (
                '{"issues": ["No major issues"], "improved_text": "Mock improved text for clarity", "summary": "Improved clarity"}',
                None,
            )
        elif "SPELLING" in prompt:
            return '{"issues": [], "improved_text": "Mock improved text for grammar", "summary": "Fixed grammar"}', None
        elif "TONE" in prompt:
            return (
                '{"issues": [], "improved_text": "Mock final text", "summary": "Adjusted tone", "recipient_perception": "positive"}',
                None,
            )
        return '{"improved_text": "Mock reply text"}', None


print(f"[{datetime.utcnow().isoformat()}] Starting email reply workflow with three-pass review")


# ============================================================================
# Pure Helper Functions
# ============================================================================


def sanitize_input(text, max_len=5000):
    """Sanitize user input for safe inclusion in prompts."""
    if not text:
        return ""
    text = str(text)
    # Remove control characters except newline and tab
    text = "".join(char for char in text if char >= " " or char in "\n\t")
    # Escape problematic sequences
    text = text.replace("```", "'''")
    text = text.replace("---", "___")
    return text[:max_len]


def extract_json_from_text(text):
    """Extract JSON object from LLM response text."""
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
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:  # LET-IT-CRASH-EXCEPTION: json.loads has no error-return API
                    return {}
    return {}


def extract_data(result):
    """Unwrap Composio nested data responses."""
    if not result:
        return {}
    data = result.get("data", {})
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    return data if isinstance(data, dict) else {}


def detect_tone_from_email(subject, body, sender):
    """
    Auto-detect appropriate tone for reply based on email context.

    Pure function - deterministic tone detection based on content analysis.
    """
    content = f"{subject} {body}".lower()

    # Urgent indicators
    if any(word in content for word in ["urgent", "asap", "immediately", "critical", "emergency"]):
        return "urgent"

    # Apologetic indicators (complaint, issue, problem)
    if any(word in content for word in ["sorry", "apologize", "mistake", "error", "problem", "issue", "complaint"]):
        return "apologetic"

    # Formal indicators (titles, formal language)
    if any(word in content for word in ["dear", "sincerely", "regards", "dr.", "prof.", "director"]):
        return "formal"

    # Friendly indicators (casual language, exclamation marks)
    if any(word in content for word in ["hey", "thanks!", "awesome", "great!", "hi there"]) or "!" in content:
        return "friendly"

    # Default to professional for business contexts
    return "professional"


def extract_email_body_gmail(payload):
    """Extract plain text body from Gmail MIME payload."""
    if not payload:
        return ""

    # Check for direct body data
    body = payload.get("body", {})
    if body.get("data"):
        try:
            return base64.urlsafe_b64decode(body["data"]).decode("utf-8")
        except Exception:  # LET-IT-CRASH-EXCEPTION: base64 decode can fail with non-utf8
            return ""

    # Check for multipart (nested parts)
    parts = payload.get("parts", [])
    for part in parts:
        mime_type = part.get("mimeType", "")
        if mime_type == "text/plain":
            part_body = part.get("body", {})
            if part_body.get("data"):
                try:
                    return base64.urlsafe_b64decode(part_body["data"]).decode("utf-8")
                except Exception:  # LET-IT-CRASH-EXCEPTION: base64 decode can fail  # noqa: S112
                    continue
        # Recursively check nested multipart
        if mime_type.startswith("multipart/"):
            nested_body = extract_email_body_gmail(part)
            if nested_body:
                return nested_body

    return ""


def extract_email_subject_gmail(payload):
    """Extract subject from Gmail headers."""
    if not payload:
        return ""
    headers = payload.get("headers", [])
    for header in headers:
        if header.get("name", "").lower() == "subject":
            return header.get("value", "")
    return ""


def extract_email_sender_gmail(payload):
    """Extract sender email from Gmail headers."""
    if not payload:
        return ""
    headers = payload.get("headers", [])
    for header in headers:
        if header.get("name", "").lower() == "from":
            return header.get("value", "")
    return ""


# ============================================================================
# Inputs
# ============================================================================

mode = os.environ.get("mode", "").lower()  # "generate" or "review"
email_source = os.environ.get("email_source", "").lower()  # "gmail" or "outlook"
message_id = os.environ.get("message_id", "")
user_draft = sanitize_input(os.environ.get("user_draft"))
desired_tone = sanitize_input(os.environ.get("desired_tone"), max_len=50)

# Validate inputs
if mode not in ["generate", "review"]:
    raise ValueError("Invalid mode. Must be 'generate' or 'review'")

if mode == "generate":
    if not email_source or email_source not in ["gmail", "outlook"]:
        raise ValueError("email_source required for generate mode. Must be 'gmail' or 'outlook'")
    if not message_id:
        raise ValueError("message_id required for generate mode")
elif mode == "review":
    if not user_draft:
        raise ValueError("user_draft required for review mode")

print(f"[{datetime.utcnow().isoformat()}] Mode: {mode}, Email Source: {email_source or 'N/A'}")

# ============================================================================
# Phase 1: Read Incoming Email (Generate Mode Only)
# ============================================================================

incoming_subject = ""
incoming_body = ""
incoming_sender = ""
detected_tone = ""
draft_reply = ""

if mode == "generate":
    print(f"[{datetime.utcnow().isoformat()}] Reading email from {email_source}...")

    if email_source == "gmail":
        email_result, email_error = run_composio_tool("GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID", {"message_id": message_id})

        if email_error:
            output = {
                "status": "FAILED",
                "error": f"Failed to read Gmail message: {email_error}",
                "mode": mode,
            }
            print(f"[{datetime.utcnow().isoformat()}] Error: {email_error}")
            output

        email_data = extract_data(email_result)
        payload = email_data.get("payload", {})

        incoming_subject = extract_email_subject_gmail(payload)
        incoming_body = extract_email_body_gmail(payload)
        incoming_sender = extract_email_sender_gmail(payload)

    elif email_source == "outlook":
        email_result, email_error = run_composio_tool("OUTLOOK_GET_MESSAGE", {"message_id": message_id})

        if email_error:
            output = {
                "status": "FAILED",
                "error": f"Failed to read Outlook message: {email_error}",
                "mode": mode,
            }
            print(f"[{datetime.utcnow().isoformat()}] Error: {email_error}")
            output

        email_data = extract_data(email_result)
        incoming_subject = email_data.get("subject", "")
        body_obj = email_data.get("body", {})
        incoming_body = body_obj.get("content", "") if isinstance(body_obj, dict) else ""
        from_obj = email_data.get("from", {})
        if isinstance(from_obj, dict):
            email_addr = from_obj.get("emailAddress", {})
            incoming_sender = email_addr.get("address", "") if isinstance(email_addr, dict) else ""

    if not incoming_body:
        output = {
            "status": "FAILED",
            "error": "Could not extract email body from message",
            "mode": mode,
        }
        print(f"[{datetime.utcnow().isoformat()}] Error: Empty email body")
        output

    print(f"[{datetime.utcnow().isoformat()}] Email read successfully")
    print(f"Subject: {incoming_subject}")
    print(f"From: {incoming_sender}")
    print(f"Body length: {len(incoming_body)} chars")

    # Auto-detect tone
    detected_tone = detect_tone_from_email(incoming_subject, incoming_body, incoming_sender)
    print(f"[{datetime.utcnow().isoformat()}] Auto-detected tone: {detected_tone}")

# ============================================================================
# Phase 2: Generate Reply (Generate Mode Only)
# ============================================================================

if mode == "generate":
    print(f"[{datetime.utcnow().isoformat()}] Generating reply draft...")

    # Use desired_tone override if provided, otherwise use detected tone
    target_tone = desired_tone if desired_tone else detected_tone

    generate_prompt = f"""Generate a professional email reply to the following email:

Subject: {incoming_subject}
From: {incoming_sender}

Email content:
{incoming_body}

Target tone: {target_tone}

Generate a complete, well-structured reply that:
- Addresses all points raised in the original email
- Maintains appropriate {target_tone} tone
- Is clear and professional
- Includes proper greeting and closing

Return ONLY the reply text (no JSON, no additional commentary).
"""

    generate_response, generate_error = invoke_llm(generate_prompt)

    if generate_error:
        output = {
            "status": "FAILED",
            "error": f"Failed to generate reply: {generate_error}",
            "mode": mode,
        }
        print(f"[{datetime.utcnow().isoformat()}] Error: {generate_error}")
        output

    draft_reply = generate_response.strip()
    print(f"[{datetime.utcnow().isoformat()}] Reply generated: {len(draft_reply)} chars")

elif mode == "review":
    # In review mode, use the user-provided draft
    draft_reply = user_draft
    # Use desired_tone if provided, otherwise default to professional
    target_tone = desired_tone if desired_tone else "professional"
    detected_tone = "N/A (review mode)"
    print(f"[{datetime.utcnow().isoformat()}] Review mode: analyzing {len(draft_reply)} char draft")

# ============================================================================
# Phase 3: Three-Pass Sequential Review
# ============================================================================

print(f"[{datetime.utcnow().isoformat()}] Starting three-pass review...")

# Pass 1: Clarity & Coherence
print(f"[{datetime.utcnow().isoformat()}] Pass 1: Clarity & Coherence")

pass1_prompt = f"""Review this email draft for CLARITY and COHERENCE:

{draft_reply}

Check for:
- Logical flow and structure
- Completeness (all points addressed)
- Ambiguities or unclear statements
- Paragraph organization
- Transitions between ideas

Return JSON with this exact structure:
{{
  "issues": ["issue1", "issue2", ...],
  "improved_text": "the improved email text",
  "summary": "brief summary of changes made"
}}

If no issues found, return empty issues array but still return the text (even if unchanged).
"""

pass1_response, pass1_error = invoke_llm(pass1_prompt)

if pass1_error:
    output = {
        "status": "FAILED",
        "error": f"Pass 1 (Clarity) failed: {pass1_error}",
        "mode": mode,
        "original_draft": draft_reply,
    }
    print(f"[{datetime.utcnow().isoformat()}] Pass 1 error: {pass1_error}")
    output

pass1_result = extract_json_from_text(pass1_response)
pass1_issues = pass1_result.get("issues", [])
pass1_summary = pass1_result.get("summary", "No changes")
pass1_text = pass1_result.get("improved_text", draft_reply)

if not pass1_text:
    pass1_text = draft_reply

print(f"[{datetime.utcnow().isoformat()}] Pass 1 complete: {len(pass1_issues)} issues, {len(pass1_text)} chars")

# Pass 2: Spelling & Grammar
print(f"[{datetime.utcnow().isoformat()}] Pass 2: Spelling & Grammar")

pass2_prompt = f"""Review this email draft for SPELLING and GRAMMAR:

{pass1_text}

Check for:
- Typos and spelling errors
- Punctuation mistakes
- Grammar issues (subject-verb agreement, tense consistency, etc.)
- Sentence structure problems
- Capitalization errors

Return JSON with this exact structure:
{{
  "issues": ["issue1", "issue2", ...],
  "improved_text": "the corrected email text",
  "summary": "brief summary of corrections made"
}}

If no issues found, return empty issues array but still return the text (even if unchanged).
"""

pass2_response, pass2_error = invoke_llm(pass2_prompt)

if pass2_error:
    output = {
        "status": "FAILED",
        "error": f"Pass 2 (Grammar) failed: {pass2_error}",
        "mode": mode,
        "original_draft": draft_reply,
        "pass1_clarity": {
            "issues": pass1_issues,
            "summary": pass1_summary,
            "text": pass1_text,
        },
    }
    print(f"[{datetime.utcnow().isoformat()}] Pass 2 error: {pass2_error}")
    output

pass2_result = extract_json_from_text(pass2_response)
pass2_issues = pass2_result.get("issues", [])
pass2_summary = pass2_result.get("summary", "No changes")
pass2_text = pass2_result.get("improved_text", pass1_text)

if not pass2_text:
    pass2_text = pass1_text

print(f"[{datetime.utcnow().isoformat()}] Pass 2 complete: {len(pass2_issues)} issues, {len(pass2_text)} chars")

# Pass 3: Tone & Perception
print(f"[{datetime.utcnow().isoformat()}] Pass 3: Tone & Perception")

pass3_prompt = f"""Review this email draft for TONE and RECIPIENT PERCEPTION:

{pass2_text}

Target tone: {target_tone}

Check for:
- Tone consistency with target ({target_tone})
- Emotional impact on recipient
- Potential negative or unintended perceptions
- Formality level appropriateness
- Courtesy and professionalism

Return JSON with this exact structure:
{{
  "issues": ["issue1", "issue2", ...],
  "improved_text": "the tone-adjusted email text",
  "summary": "brief summary of tone adjustments made",
  "recipient_perception": "how the recipient will likely feel after reading this (1-2 sentences)"
}}

If no issues found, return empty issues array but still return the text (even if unchanged).
"""

pass3_response, pass3_error = invoke_llm(pass3_prompt)

if pass3_error:
    output = {
        "status": "FAILED",
        "error": f"Pass 3 (Tone) failed: {pass3_error}",
        "mode": mode,
        "original_draft": draft_reply,
        "pass1_clarity": {
            "issues": pass1_issues,
            "summary": pass1_summary,
            "text": pass1_text,
        },
        "pass2_grammar": {
            "issues": pass2_issues,
            "summary": pass2_summary,
            "text": pass2_text,
        },
    }
    print(f"[{datetime.utcnow().isoformat()}] Pass 3 error: {pass3_error}")
    output

pass3_result = extract_json_from_text(pass3_response)
pass3_issues = pass3_result.get("issues", [])
pass3_summary = pass3_result.get("summary", "No changes")
pass3_text = pass3_result.get("improved_text", pass2_text)
recipient_perception = pass3_result.get("recipient_perception", "Positive and professional")

if not pass3_text:
    pass3_text = pass2_text

print(f"[{datetime.utcnow().isoformat()}] Pass 3 complete: {len(pass3_issues)} issues, {len(pass3_text)} chars")

# ============================================================================
# Build Final Output
# ============================================================================

final_text = pass3_text

output = {
    "status": "DONE",
    "mode": mode,
    "original_draft": draft_reply,
    "final_reply": final_text,
    "detected_tone": detected_tone,
    "target_tone": target_tone,
    "pass1_clarity": {
        "issues": pass1_issues,
        "summary": pass1_summary,
        "text": pass1_text,
    },
    "pass2_grammar": {
        "issues": pass2_issues,
        "summary": pass2_summary,
        "text": pass2_text,
    },
    "pass3_tone": {
        "issues": pass3_issues,
        "summary": pass3_summary,
        "text": pass3_text,
        "recipient_perception": recipient_perception,
    },
}

if mode == "generate":
    output["incoming_email"] = {
        "subject": incoming_subject,
        "sender": incoming_sender,
        "body_preview": incoming_body[:200] + "..." if len(incoming_body) > 200 else incoming_body,
    }

print(f"[{datetime.utcnow().isoformat()}] Three-pass review complete!")
print(f"Original: {len(draft_reply)} chars")
print(f"Final: {len(final_text)} chars")
print(f"Pass 1 issues: {len(pass1_issues)}")
print(f"Pass 2 issues: {len(pass2_issues)}")
print(f"Pass 3 issues: {len(pass3_issues)}")

output
