// drafts-view.js - Draft management UI

async function loadDraftsList() {
    const { invoke } = window.__TAURI__.core;
    const tbody = document.getElementById('drafts-body');
    tbody.innerHTML = '<tr><td colspan="5" class="loading">Loading...</td></tr>';

    try {
        const drafts = await invoke('list_drafts_cmd');
        if (!drafts || drafts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="loading">No drafts found</td></tr>';
            return;
        }
        tbody.innerHTML = drafts.map(d => `
            <tr data-filepath="${escapeHtml(d.filepath)}" style="cursor:pointer;">
                <td><span class="draft-status-badge status-${d.status}">${escapeHtml(d.status)}</span></td>
                <td>${escapeHtml(d.title)}</td>
                <td>${escapeHtml(d.date)}</td>
                <td>${escapeHtml(d.created_at)}</td>
                <td>${escapeHtml(d.filename)}</td>
            </tr>
        `).join('');
        tbody.querySelectorAll('tr[data-filepath]').forEach(row => {
            row.addEventListener('click', () => loadDraftDetail(row.dataset.filepath));
        });
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="5" style="color: #f48771;">Error: ${escapeHtml(String(error))}</td></tr>`;
    }
}

async function loadDraftDetail(filepath) {
    const { invoke } = window.__TAURI__.core;
    const detailDiv = document.getElementById('draft-detail');
    detailDiv.style.display = 'block';
    detailDiv.innerHTML = '<p class="loading">Loading draft...</p>';

    try {
        const draft = await invoke('load_draft_cmd', { filepath });
        renderDraftDetail(draft, filepath);
    } catch (error) {
        showError(detailDiv, String(error));
    }
}

function renderDraftDetail(draft, filepath) {
    const detailDiv = document.getElementById('draft-detail');
    const statusClass = `status-${draft.status}`;

    detailDiv.innerHTML = `
        <div class="draft-detail-header">
            <h3>${escapeHtml(draft.event.title)}</h3>
            <span class="draft-status-badge ${statusClass}">${escapeHtml(draft.status)}</span>
            <button onclick="closeDraftDetail()" class="btn-secondary">Close</button>
        </div>

        <div class="draft-meta">
            <p><strong>Date:</strong> ${escapeHtml(draft.event.date)} at ${escapeHtml(draft.event.time)}</p>
            <p><strong>Location:</strong> ${escapeHtml(draft.event.location)}</p>
            <p><strong>URL:</strong> ${escapeHtml(draft.event.url || 'N/A')}</p>
            ${draft.image_url ? `<p><strong>Image:</strong> <a href="${escapeHtml(draft.image_url)}" style="color:#4ec9b0;">${escapeHtml(draft.image_url)}</a></p>` : ''}
        </div>

        <div class="draft-copies">
            <h4>Platform Copies</h4>
            ${renderCopyField('Twitter', draft.copies.twitter)}
            ${renderCopyField('LinkedIn', draft.copies.linkedin)}
            ${renderCopyField('Instagram', draft.copies.instagram)}
            ${renderCopyField('Facebook', draft.copies.facebook)}
            ${renderCopyField('Discord', draft.copies.discord)}
        </div>

        <div class="draft-actions">
            ${draft.status === 'draft' ? `<button data-action="approve" class="btn-primary">Approve</button>` : ''}
            ${draft.status === 'approved' ? `<button data-action="publish" class="btn-primary">Publish</button>` : ''}
        </div>

        <div id="draft-action-progress" style="display:none;"></div>
        <div id="draft-action-result"></div>

        ${draft.publish_results ? `
            <div class="draft-publish-results">
                <h4>Publish Results</h4>
                <pre>${escapeHtml(JSON.stringify(draft.publish_results, null, 2))}</pre>
            </div>
        ` : ''}
    `;

    const approveBtn = detailDiv.querySelector('[data-action="approve"]');
    if (approveBtn) approveBtn.addEventListener('click', () => approveDraft(filepath));
    const publishBtn = detailDiv.querySelector('[data-action="publish"]');
    if (publishBtn) publishBtn.addEventListener('click', () => publishDraft(filepath));
}

function renderCopyField(label, text) {
    return `<div class="copy-field">
        <label>${escapeHtml(label)}</label>
        <div class="copy-text">${escapeHtml(text || '(empty)')}</div>
    </div>`;
}

function closeDraftDetail() {
    document.getElementById('draft-detail').style.display = 'none';
}

async function approveDraft(filepath) {
    const { invoke } = window.__TAURI__.core;
    const resultDiv = document.getElementById('draft-action-result');

    try {
        await invoke('approve_draft', { filepath });
        showSuccess(resultDiv, 'Draft approved successfully.');
        loadDraftDetail(filepath);
        loadDraftsList();
    } catch (error) {
        showError(resultDiv, String(error));
    }
}

async function publishDraft(filepath) {
    const { invoke } = window.__TAURI__.core;
    const resultDiv = document.getElementById('draft-action-result');

    createProgressPanel('draft-action-progress');
    startListening('draft-action-progress', 'publish_draft');
    resultDiv.innerHTML = '<p class="loading">Publishing...</p>';

    try {
        const result = await invoke('publish_draft', { filepath });
        resultDiv.innerHTML = `<pre class="result-json">${escapeHtml(JSON.stringify(result, null, 2))}</pre>`;
        loadDraftDetail(filepath);
        loadDraftsList();
    } catch (error) {
        showError(resultDiv, String(error));
    } finally {
        stopListening('draft-action-progress');
    }
}

// Generate drafts form handler
async function submitGenerateDrafts() {
    const { invoke } = window.__TAURI__.core;
    const resultDiv = document.getElementById('gen-draft-result');

    const title = document.getElementById('gd-title').value.trim();
    const date = document.getElementById('gd-date').value.trim();
    const time = document.getElementById('gd-time').value.trim();
    const location = document.getElementById('gd-location').value.trim();
    const description = document.getElementById('gd-description').value.trim();
    const eventUrl = document.getElementById('gd-event-url').value.trim();

    if (!title || !date || !time || !location || !description || !eventUrl) {
        showError(resultDiv, 'Please fill in all required fields.');
        return;
    }

    const discordChannel = document.getElementById('gd-discord-channel').value.trim();
    const facebookPage = document.getElementById('gd-facebook-page').value.trim();

    createProgressPanel('gen-draft-progress');
    startListening('gen-draft-progress', 'generate_drafts');
    resultDiv.innerHTML = '<p class="loading">Generating drafts...</p>';
    document.getElementById('gen-draft-btn').disabled = true;

    try {
        const result = await invoke('generate_drafts', {
            title, date, time, location, description,
            event_url: eventUrl,
            discord_channel_id: discordChannel || null,
            facebook_page_id: facebookPage || null,
            skip_platforms: null,
        });
        resultDiv.innerHTML = `<pre class="result-json">${escapeHtml(JSON.stringify(result, null, 2))}</pre>`;
        loadDraftsList();
    } catch (error) {
        showError(resultDiv, String(error));
    } finally {
        stopListening('gen-draft-progress');
        document.getElementById('gen-draft-btn').disabled = false;
    }
}

// Load drafts when tab is shown
document.addEventListener('DOMContentLoaded', () => {
    const draftsBtn = document.querySelector('.tab-btn[data-tab="drafts"]');
    if (draftsBtn) {
        draftsBtn.addEventListener('click', loadDraftsList);
    }
});
