# Support

Need help with CCP Digital Marketing? Here's how to get support.

## Getting Help

### 1. Search Existing Resources

Before asking for help, check if your question is already answered:

- **README.md**: Quick start guide, setup instructions, basic usage
- **CLAUDE.md**: Architecture, design principles, recipe patterns
- **docs/troubleshooting.md**: Common issues and solutions (if available)
- **Existing GitHub Issues**: Search https://github.com/Coffee-Code-Philly-Accelerator/CCP-Digital-Marketing/issues

### 2. Ask the Community

#### GitHub Issues (Public Questions)

For bugs, feature requests, and usage questions:

1. Go to https://github.com/Coffee-Code-Philly-Accelerator/CCP-Digital-Marketing/issues
2. Search existing issues first (your question may already be answered)
3. If not found, click "New Issue"
4. Choose the appropriate template:
   - **Bug Report**: Something is broken
   - **Feature Request**: Suggest a new feature
   - **Blank Issue**: General questions or discussion

#### Discord (Real-Time Support)

For quick questions and community chat:

1. Join https://discord.gg/X2a8jr73N4
2. Introduce yourself in #introductions
3. Ask questions in #help or #general
4. Get real-time assistance from maintainers and community members

**Discord is best for:**
- Quick questions ("How do I...?")
- Troubleshooting with back-and-forth discussion
- Community chat and networking
- Getting unstuck during development

**GitHub Issues are best for:**
- Bug reports (need tracking and long-term visibility)
- Feature requests (need design discussion)
- Documentation improvements

## Common Issues

### NEEDS_AUTH Status

**Problem**: Recipe returns `{"status": "NEEDS_AUTH"}`

**Solution**:
1. Run the auth-setup skill for the affected platform
2. Complete the login flow in the browser window
3. Save the profile ID to your `.env` file
4. Re-run the recipe

```bash
# Re-authenticate for Luma
export CCP_LUMA_PROFILE_ID='profile_abc123'
```

### Form Filling Fails

**Problem**: Browser agent can't fill out the form correctly

**Possible causes**:
- Platform UI changed (forms are different than task instructions expect)
- Anti-bot detection triggered
- Timeout (operation took longer than 4 minutes)

**Solution**:
1. Check the `live_url` in the recipe output to watch the browser in real-time
2. If the form layout changed, update the recipe task description
3. If anti-bot detection triggered, try re-running (random timeouts help)
4. If timeout, report as a bug (recipe may need optimization)

### Social Post Fails

**Problem**: Social media posting fails with API error

**Solution**:
1. Go to https://app.composio.dev/connections
2. Find the failing integration (Twitter, LinkedIn, Facebook, etc.)
3. Click "Re-authorize" to refresh the connection
4. Test with the `social-post` skill:
   ```bash
   /social-post
   ```

### Recipe Execution Timeout

**Problem**: Recipe exceeds 4-minute Rube runtime limit

**Solution**:
- This should not happen with current recipes (all use single AI browser agent calls)
- If it does, report as a bug with the recipe ID and input parameters

### Python Dependencies

**Problem**: `ModuleNotFoundError` when running CLI

**Solution**:
```bash
pip install -r scripts/requirements.txt
```

### Environment Variables

**Problem**: Recipe fails with "Missing required input"

**Solution**:
Check that all required environment variables are set:

```bash
# Required
export COMPOSIO_API_KEY='comp_xxxxx'

# Optional (platform defaults)
export CCP_MEETUP_GROUP_URL='https://www.meetup.com/code-coffee-philly'
export CCP_DISCORD_CHANNEL_ID='1234567890'
export CCP_FACEBOOK_PAGE_ID='1234567890'

# Optional (browser profiles)
export CCP_LUMA_PROFILE_ID='profile_xxxxx'
export CCP_MEETUP_PROFILE_ID='profile_xxxxx'
export CCP_PARTIFUL_PROFILE_ID='profile_xxxxx'
```

## Feature Requests

Have an idea for a new feature? We'd love to hear it!

1. Check existing feature requests: https://github.com/Coffee-Code-Philly-Accelerator/CCP-Digital-Marketing/issues?q=is%3Aissue+label%3Aenhancement
2. If your idea isn't listed, open a new feature request
3. Provide details:
   - What problem does it solve?
   - How would it work?
   - Are you willing to contribute?

Popular feature request categories:
- New event platforms (Eventbrite, Universe, etc.)
- New social networks (Bluesky, Mastodon, Threads, etc.)
- CLI enhancements (better error messages, progress bars, etc.)
- Recipe improvements (better prompts, image generation, etc.)

## Contributing

Want to fix a bug or add a feature yourself? See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## What NOT to Post

Please avoid posting the following in public channels:

- **API keys or secrets** (use GitHub Security Advisories for security issues)
- **Personal information** (email addresses, phone numbers, etc.)
- **Off-topic discussions** (keep it relevant to CCP Digital Marketing)
- **Spam or promotional content**
- **Code of Conduct violations** (see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md))

## Response Times

- **Discord**: Usually within a few hours (community-driven)
- **GitHub Issues**: Within 1-3 business days (maintainer response)
- **Security Issues**: Within 48 hours (see [SECURITY.md](SECURITY.md))

## Contact Information

- **GitHub Issues**: https://github.com/Coffee-Code-Philly-Accelerator/CCP-Digital-Marketing/issues
- **Discord**: https://discord.gg/X2a8jr73N4
- **Organization**: Coffee Code Philly Accelerator
- **Meetup**: https://www.meetup.com/code-coffee-philly

---

**Still stuck?** Don't hesitate to ask! We're here to help. Join Discord or open a GitHub issue, and the community will jump in to assist.
