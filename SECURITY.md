# Security Policy

## Supported Versions

This project is currently in pre-1.0 development. Security updates are applied to the latest commit on the `main` branch.

| Version | Supported          |
| ------- | ------------------ |
| main (latest) | :white_check_mark: |
| Older commits | :x: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please report it responsibly.

### Preferred: GitHub Security Advisories (Private Disclosure)

1. Navigate to https://github.com/Coffee-Code-Philly-Accelerator/CCP-Digital-Marketing/security/advisories/new
2. Click "Report a vulnerability"
3. Fill out the form with:
   - **Title**: Brief description of the vulnerability
   - **Description**: Detailed explanation of the issue
   - **Severity**: Your assessment (Low/Moderate/High/Critical)
   - **Affected versions**: Usually "main branch"
   - **Steps to reproduce**: How to trigger the vulnerability
   - **Proof of concept**: Code snippets, screenshots, or sample exploits (if applicable)

This method keeps the vulnerability private until a fix is available.

### Alternative: Discord (For Sensitive Issues)

If you prefer not to use GitHub Security Advisories, you can contact maintainers directly via Discord:

1. Join https://discord.gg/X2a8jr73N4
2. Send a direct message to @CCP-Admin or moderators
3. Include "SECURITY" in the subject line

**Do NOT report security vulnerabilities in public GitHub Issues.**

## Response Timeline

- **Acknowledgment**: Within 48 hours of report
- **Initial assessment**: Within 5 business days
- **Fix timeline**:
  - **Critical**: Within 7 days
  - **High**: Within 14 days
  - **Moderate**: Within 30 days
  - **Low**: Next release cycle

We will keep you informed of progress throughout the process.

## Security Scope

### In Scope

We consider the following issues as security vulnerabilities:

- **Hardcoded secrets**: API keys, tokens, passwords in source code
- **Command injection**: Unsafe execution of user-provided input
- **XSS vulnerabilities**: Unsafe rendering of user-provided content in web contexts
- **Unsafe deserialization**: Pickle, eval() on untrusted input
- **Path traversal**: Unauthorized file access via crafted paths
- **Dependency vulnerabilities**: Known CVEs in requirements.txt
- **Authentication bypass**: Circumventing Composio API auth
- **Data leakage**: Exposing sensitive user data or credentials

### Out of Scope

The following are NOT considered security vulnerabilities in this project:

- **Composio API security**: Vulnerabilities in Composio's platform (report to Composio directly)
- **Third-party platform vulnerabilities**: Issues with Luma, Meetup, Partiful, social media APIs
- **Browser automation detection**: Anti-bot measures on target platforms (expected behavior)
- **Rate limiting bypass**: Circumventing API rate limits on third-party platforms
- **Social engineering**: Phishing attacks targeting users
- **Physical security**: Access to the server/machine running the code
- **Denial of service**: Resource exhaustion attacks (this is a CLI tool, not a web service)

## Security Best Practices for Contributors

When contributing code, please follow these security guidelines:

### 1. Never Commit Secrets

```bash
# BAD - Do NOT do this
COMPOSIO_API_KEY = "comp_abc123xyz"

# GOOD - Use environment variables
import os
COMPOSIO_API_KEY = os.environ.get("COMPOSIO_API_KEY")
```

### 2. Validate User Input

```python
# Sanitize inputs before passing to browser tasks
def sanitize_input(text: str, max_len: int = 2000) -> str:
    if not text:
        return ""
    text = str(text)
    text = ''.join(char for char in text if char >= ' ' or char in '\n\t')
    return text[:max_len]
```

### 3. Avoid Command Injection

```python
# BAD - Shell injection risk
os.system(f"curl {user_provided_url}")

# GOOD - Use safe APIs
import requests
requests.get(user_provided_url)
```

### 4. Use Secure Dependencies

- Keep `requirements.txt` up to date
- Run `pip-audit` to check for known vulnerabilities
- Enable Dependabot (already configured in `.github/dependabot.yml`)

### 5. Follow "Let It Crash" Principle

- **Don't hide errors** with broad `try/except` blocks
- Let stack traces surface (easier to debug and detect attacks)
- Use explicit error handling: `result, error = run_composio_tool(...)`

## Security Contacts

- **Primary**: GitHub Security Advisories (private reporting)
- **Discord**: https://discord.gg/X2a8jr73N4 (DM moderators)
- **GitHub Issues**: For non-sensitive security discussions ONLY

## Disclosure Policy

- **Private disclosure**: 90 days before public disclosure (standard responsible disclosure)
- **Coordinated release**: Security fixes released with minimal details until patch is widely adopted
- **Public CVE**: For critical vulnerabilities, we will request a CVE ID
- **Credit**: Security researchers will be credited (unless they prefer anonymity)

## Security Updates

Security fixes are released as soon as possible after verification. Users should:

1. Watch this repository for security advisories
2. Subscribe to GitHub Security Advisories: Settings → Notifications → Security alerts
3. Update to the latest commit on `main` regularly
4. Run `pip install --upgrade -r scripts/requirements.txt` to get dependency updates

## Past Security Issues

No security vulnerabilities have been reported or fixed yet (as of March 2026).

When issues are resolved, they will be listed here with:
- CVE ID (if applicable)
- Severity level
- Fixed version/commit
- Credit to reporter

---

Thank you for helping keep CCP Digital Marketing secure!
