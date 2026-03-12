// event-form.js - Create Event + Full Workflow forms

async function submitEventForm(mode) {
    const { invoke } = window.__TAURI__.core;
    const resultDiv = document.getElementById('event-result');

    const title = document.getElementById('ev-title').value.trim();
    const date = document.getElementById('ev-date').value.trim();
    const time = document.getElementById('ev-time').value.trim();
    const location = document.getElementById('ev-location').value.trim();
    const description = document.getElementById('ev-description').value.trim();

    if (!title || !date || !time || !location || !description) {
        showError(resultDiv, 'Please fill in all required fields.');
        return;
    }

    const meetupUrl = document.getElementById('ev-meetup-url').value.trim();
    const discordChannel = document.getElementById('ev-discord-channel').value.trim();
    const facebookPage = document.getElementById('ev-facebook-page').value.trim();
    const provider = document.getElementById('ev-provider').value;

    // Build skip list from unchecked checkboxes
    const skipParts = [];
    if (!document.getElementById('ev-plat-luma').checked) skipParts.push('luma');
    if (!document.getElementById('ev-plat-meetup').checked) skipParts.push('meetup');
    if (!document.getElementById('ev-plat-partiful').checked) skipParts.push('partiful');
    const skipPlatforms = skipParts.join(',');

    // Setup progress
    createProgressPanel('event-progress');
    const commandName = mode === 'full' ? 'full_workflow' : 'create_event';
    startListening('event-progress', commandName);
    resultDiv.innerHTML = '<p class="loading">Executing...</p>';

    // Disable submit buttons
    setEventButtonsDisabled(true);

    const args = {
        title, date, time, location, description,
        meetupUrl: meetupUrl || null,
        skipPlatforms: skipPlatforms || null,
        provider: provider || null,
    };

    if (mode === 'full') {
        args.discordChannelId = discordChannel || null;
        args.facebookPageId = facebookPage || null;
    }

    const command = mode === 'full' ? 'full_workflow' : 'create_event';

    try {
        const result = await invoke(command, args);
        resultDiv.innerHTML = `<pre class="result-json">${escapeHtml(JSON.stringify(result, null, 2))}</pre>`;
    } catch (error) {
        showError(resultDiv, String(error));
    } finally {
        stopListening('event-progress');
        setEventButtonsDisabled(false);
    }
}

async function submitPromoteForm() {
    const { invoke } = window.__TAURI__.core;
    const resultDiv = document.getElementById('promote-result');

    const title = document.getElementById('ev-title').value.trim();
    const date = document.getElementById('ev-date').value.trim();
    const time = document.getElementById('ev-time').value.trim();
    const location = document.getElementById('ev-location').value.trim();
    const description = document.getElementById('ev-description').value.trim();
    const eventUrl = document.getElementById('promote-event-url').value.trim();

    if (!title || !date || !time || !location || !description || !eventUrl) {
        showError(resultDiv, 'Please fill in all required fields including Event URL.');
        return;
    }

    const discordChannel = document.getElementById('ev-discord-channel').value.trim();
    const facebookPage = document.getElementById('ev-facebook-page').value.trim();

    createProgressPanel('event-progress');
    startListening('event-progress', 'promote_event');
    resultDiv.innerHTML = '<p class="loading">Promoting...</p>';
    setEventButtonsDisabled(true);

    try {
        const result = await invoke('promote_event', {
            title, date, time, location, description,
            eventUrl,
            discordChannelId: discordChannel || null,
            facebookPageId: facebookPage || null,
            skipPlatforms: null,
            imageUrl: null,
        });
        resultDiv.innerHTML = `<pre class="result-json">${escapeHtml(JSON.stringify(result, null, 2))}</pre>`;
    } catch (error) {
        showError(resultDiv, String(error));
    } finally {
        stopListening('event-progress');
        setEventButtonsDisabled(false);
    }
}

function setEventButtonsDisabled(disabled) {
    document.querySelectorAll('#tab-create-event button[type="button"]').forEach(btn => {
        btn.disabled = disabled;
    });
}
