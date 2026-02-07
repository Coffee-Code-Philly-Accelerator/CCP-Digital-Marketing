"""Tests for CCP Marketing platform adapters."""

import pytest

from ccp_marketing.adapters.base import BasePlatformAdapter
from ccp_marketing.adapters.luma import LumaAdapter
from ccp_marketing.adapters.meetup import MeetupAdapter
from ccp_marketing.adapters.partiful import PartifulAdapter
from ccp_marketing.state_machine.states import EventState


class TestBasePlatformAdapter:
    """Tests for BasePlatformAdapter base class."""

    def test_get_description_uses_platform_specific(self, sample_event):
        """Test get_description returns platform-specific description."""
        descriptions = {"luma": "Luma-specific description"}
        adapter = LumaAdapter(sample_event, descriptions)

        assert adapter.get_description() == "Luma-specific description"

    def test_get_description_falls_back(self, sample_event):
        """Test get_description falls back to event description."""
        adapter = LumaAdapter(sample_event, {})

        assert adapter.get_description() == sample_event.description

    def test_to_dict(self, sample_event):
        """Test to_dict returns adapter info."""
        adapter = LumaAdapter(sample_event)

        d = adapter.to_dict()
        assert d["name"] == "luma"
        assert d["create_url"] == "https://lu.ma/create"


class TestLumaAdapter:
    """Tests for LumaAdapter."""

    def test_class_attributes(self):
        """Test Luma class attributes."""
        assert LumaAdapter.name == "luma"
        assert LumaAdapter.create_url == "https://lu.ma/create"
        assert LumaAdapter.home_url == "https://lu.ma/home"
        assert LumaAdapter.inter_step_delay == 0.5

    def test_form_indicators(self):
        """Test form indicators."""
        indicators = LumaAdapter.form_indicators
        assert "event title" in indicators
        assert "create event" in indicators

    def test_success_url_check_valid(self, sample_event):
        """Test success_url_check for valid event URLs."""
        adapter = LumaAdapter(sample_event)

        assert adapter.success_url_check("https://lu.ma/ai-workshop-abc123")
        assert adapter.success_url_check("https://lu.ma/my-event")

    def test_success_url_check_invalid(self, sample_event):
        """Test success_url_check rejects invalid URLs."""
        adapter = LumaAdapter(sample_event)

        assert not adapter.success_url_check("https://lu.ma/create")
        assert not adapter.success_url_check("https://lu.ma/home")
        assert not adapter.success_url_check("https://other.com/event")

    def test_get_prompt_fill_title(self, sample_event):
        """Test prompt for filling title."""
        adapter = LumaAdapter(sample_event)

        prompt = adapter.get_prompt(EventState.FILL_TITLE)
        assert "AI Workshop" in prompt
        assert "title" in prompt.lower()

    def test_get_prompt_fill_date(self, sample_event):
        """Test prompt for filling date."""
        adapter = LumaAdapter(sample_event)

        prompt = adapter.get_prompt(EventState.FILL_DATE)
        assert "January 25, 2025" in prompt
        assert "date" in prompt.lower()

    def test_get_prompt_fill_time(self, sample_event):
        """Test prompt for filling time."""
        adapter = LumaAdapter(sample_event)

        prompt = adapter.get_prompt(EventState.FILL_TIME)
        assert "6:00 PM EST" in prompt

    def test_get_prompt_fill_location(self, sample_event):
        """Test prompt for filling location."""
        adapter = LumaAdapter(sample_event)

        prompt = adapter.get_prompt(EventState.FILL_LOCATION)
        assert "The Station, Philadelphia" in prompt

    def test_get_prompt_submit(self, sample_event):
        """Test prompt for submit."""
        adapter = LumaAdapter(sample_event)

        prompt = adapter.get_prompt(EventState.SUBMIT)
        assert "Publish" in prompt or "Create" in prompt

    def test_get_prompt_returns_empty_for_unknown(self, sample_event):
        """Test prompt returns empty for unhandled states."""
        adapter = LumaAdapter(sample_event)

        prompt = adapter.get_prompt(EventState.INIT)
        assert prompt == ""

    def test_post_step_wait_date(self, sample_event):
        """Test extra wait time for date field."""
        adapter = LumaAdapter(sample_event)

        wait = adapter.post_step_wait(EventState.FILL_DATE)
        assert wait == 1.5  # Extra time for React date picker

    def test_post_step_wait_default(self, sample_event):
        """Test default wait time for other fields."""
        adapter = LumaAdapter(sample_event)

        wait = adapter.post_step_wait(EventState.FILL_TITLE)
        assert wait == 0.5

    def test_is_form_page_positive(self, sample_event):
        """Test is_form_page detects form."""
        adapter = LumaAdapter(sample_event)

        assert adapter.is_form_page("Create Event - Enter your event title here")
        assert adapter.is_form_page("What's your event about?")

    def test_is_form_page_negative(self, sample_event):
        """Test is_form_page rejects non-form pages."""
        adapter = LumaAdapter(sample_event)

        assert not adapter.is_form_page("Your Events Dashboard")
        assert not adapter.is_form_page("Please sign in")

    def test_post_submit_action(self, sample_event):
        """Test post_submit_action returns None for Luma."""
        adapter = LumaAdapter(sample_event)
        assert adapter.post_submit_action() is None


class TestMeetupAdapter:
    """Tests for MeetupAdapter."""

    def test_class_attributes(self):
        """Test Meetup class attributes."""
        assert MeetupAdapter.name == "meetup"
        assert MeetupAdapter.home_url == "https://www.meetup.com/home"
        assert MeetupAdapter.inter_step_delay == 2.0  # Anti-bot delay

    def test_init_with_group_url(self, sample_event):
        """Test initialization with group URL."""
        adapter = MeetupAdapter(
            sample_event,
            group_url="https://meetup.com/coffee-code-philly",
        )
        assert adapter.group_url == "https://meetup.com/coffee-code-philly"

    def test_get_create_url_with_group(self, sample_event):
        """Test create URL is derived from group URL."""
        adapter = MeetupAdapter(
            sample_event,
            group_url="https://meetup.com/coffee-code-philly",
        )

        url = adapter.get_create_url()
        assert url == "https://meetup.com/coffee-code-philly/events/create/"

    def test_get_create_url_without_group(self, sample_event):
        """Test create URL is empty without group URL."""
        adapter = MeetupAdapter(sample_event)

        url = adapter.get_create_url()
        assert url == ""

    def test_get_create_url_strips_trailing_slash(self, sample_event):
        """Test create URL handles trailing slash."""
        adapter = MeetupAdapter(
            sample_event,
            group_url="https://meetup.com/coffee-code-philly/",
        )

        url = adapter.get_create_url()
        assert url == "https://meetup.com/coffee-code-philly/events/create/"

    def test_success_url_check_valid(self, sample_event):
        """Test success_url_check for valid event URLs."""
        adapter = MeetupAdapter(sample_event)

        assert adapter.success_url_check("https://meetup.com/group/events/12345/")
        assert adapter.success_url_check("https://www.meetup.com/group/events/67890/")

    def test_success_url_check_invalid(self, sample_event):
        """Test success_url_check rejects invalid URLs."""
        adapter = MeetupAdapter(sample_event)

        assert not adapter.success_url_check("https://meetup.com/group/events/create/")
        assert not adapter.success_url_check("https://meetup.com/home")

    def test_get_prompt_fill_title(self, sample_event):
        """Test prompt for filling title."""
        adapter = MeetupAdapter(sample_event)

        prompt = adapter.get_prompt(EventState.FILL_TITLE)
        assert "AI Workshop" in prompt

    def test_form_indicators(self):
        """Test form indicators."""
        indicators = MeetupAdapter.form_indicators
        assert "event details" in indicators
        assert "create event" in indicators


class TestPartifulAdapter:
    """Tests for PartifulAdapter."""

    def test_class_attributes(self):
        """Test Partiful class attributes."""
        assert PartifulAdapter.name == "partiful"
        assert PartifulAdapter.create_url == "https://partiful.com/create"
        assert PartifulAdapter.home_url == "https://partiful.com/home"
        assert PartifulAdapter.inter_step_delay == 0.6

    def test_success_url_check_valid(self, sample_event):
        """Test success_url_check for valid event URLs."""
        adapter = PartifulAdapter(sample_event)

        assert adapter.success_url_check("https://partiful.com/e/abc123")
        assert adapter.success_url_check("https://partiful.com/e/my-event-xyz")

    def test_success_url_check_invalid(self, sample_event):
        """Test success_url_check rejects invalid URLs."""
        adapter = PartifulAdapter(sample_event)

        assert not adapter.success_url_check("https://partiful.com/create")
        assert not adapter.success_url_check("https://partiful.com/home")
        assert not adapter.success_url_check("https://partiful.com/events/123")

    def test_get_prompt_fill_title(self, sample_event):
        """Test prompt for filling title."""
        adapter = PartifulAdapter(sample_event)

        prompt = adapter.get_prompt(EventState.FILL_TITLE)
        assert "AI Workshop" in prompt
        assert "Untitled Event" in prompt

    def test_post_submit_action(self, sample_event):
        """Test post_submit_action dismisses share modal."""
        adapter = PartifulAdapter(sample_event)

        action = adapter.post_submit_action()
        assert action is not None
        assert "share" in action.lower() or "modal" in action.lower()

    def test_form_indicators(self):
        """Test form indicators."""
        indicators = PartifulAdapter.form_indicators
        assert "untitled event" in indicators
        assert "create party" in indicators


class TestAdapterCommonBehavior:
    """Tests for behavior common to all adapters."""

    @pytest.fixture(params=[
        LumaAdapter,
        MeetupAdapter,
        PartifulAdapter,
    ])
    def adapter_class(self, request):
        """Parametrized fixture for all adapter classes."""
        return request.param

    def test_has_name(self, adapter_class, sample_event):
        """Test all adapters have a name."""
        if adapter_class == MeetupAdapter:
            adapter = adapter_class(sample_event, group_url="https://meetup.com/test")
        else:
            adapter = adapter_class(sample_event)

        assert adapter.name
        assert isinstance(adapter.name, str)

    def test_has_form_indicators(self, adapter_class):
        """Test all adapters have form indicators."""
        assert adapter_class.form_indicators
        assert len(adapter_class.form_indicators) > 0

    def test_get_prompt_for_all_fill_states(self, adapter_class, sample_event):
        """Test all adapters return prompts for fill states."""
        if adapter_class == MeetupAdapter:
            adapter = adapter_class(sample_event, group_url="https://meetup.com/test")
        else:
            adapter = adapter_class(sample_event)

        fill_states = [
            EventState.FILL_TITLE,
            EventState.FILL_DATE,
            EventState.FILL_TIME,
            EventState.FILL_LOCATION,
            EventState.FILL_DESCRIPTION,
        ]

        for state in fill_states:
            prompt = adapter.get_prompt(state)
            assert prompt, f"No prompt for {state} in {adapter_class.__name__}"

    def test_get_prompt_for_submit(self, adapter_class, sample_event):
        """Test all adapters return prompt for submit."""
        if adapter_class == MeetupAdapter:
            adapter = adapter_class(sample_event, group_url="https://meetup.com/test")
        else:
            adapter = adapter_class(sample_event)

        prompt = adapter.get_prompt(EventState.SUBMIT)
        assert prompt
        assert "click" in prompt.lower() or "button" in prompt.lower()

    def test_post_step_wait_returns_float(self, adapter_class, sample_event):
        """Test post_step_wait returns a float."""
        if adapter_class == MeetupAdapter:
            adapter = adapter_class(sample_event, group_url="https://meetup.com/test")
        else:
            adapter = adapter_class(sample_event)

        for state in [EventState.FILL_TITLE, EventState.FILL_DATE, EventState.SUBMIT]:
            wait = adapter.post_step_wait(state)
            assert isinstance(wait, (int, float))
            assert wait >= 0

    def test_success_url_check_returns_bool(self, adapter_class, sample_event):
        """Test success_url_check returns boolean."""
        if adapter_class == MeetupAdapter:
            adapter = adapter_class(sample_event, group_url="https://meetup.com/test")
        else:
            adapter = adapter_class(sample_event)

        result = adapter.success_url_check("https://example.com")
        assert isinstance(result, bool)
