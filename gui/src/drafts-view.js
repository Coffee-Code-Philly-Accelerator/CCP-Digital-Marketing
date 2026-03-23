// drafts-view.js - Draft management UI

async function loadDraftsList() {
    const { invoke } = window.__TAURI__.core;
    const tbody = document.getElementById('drafts-body');
    tbody.innerHTML = '<tr><td colspan="6" class="loading">Loading...</td></tr>';

    try {
        const drafts = await invoke('list_drafts_cmd');
        if (!drafts || drafts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="loading">No drafts found</td></tr>';
            return;
        }
        tbody.innerHTML = drafts.map(d => {
            const typeLabel = d.draft_type === 'social_post' ? 'Social Post' : 'Event';
            return `
            <tr data-filepath="${escapeHtml(d.filepath)}" style="cursor:pointer;">
                <td><span class="draft-status-badge status-${d.status}">${escapeHtml(d.status)}</span></td>
                <td>${escapeHtml(typeLabel)}</td>
                <td>${escapeHtml(d.title)}</td>
                <td>${escapeHtml(d.date)}</td>
                <td>${escapeHtml(d.created_at)}</td>
                <td>${escapeHtml(d.filename)}</td>
            </tr>`;
        }).join('');
        tbody.querySelectorAll('tr[data-filepath]').forEach(row => {
            row.addEventListener('click', () => loadDraftDetail(row.dataset.filepath));
        });
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="6" style="color: #f48771;">Error: ${escapeHtml(String(error))}</td></tr>`;
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
    const isSocialPost = draft.draft_type === 'social_post';

    const metaHtml = isSocialPost ? `
        <div class="draft-meta">
            <p><strong>Message:</strong> ${escapeHtml(draft.event.description || draft.event.title)}</p>
            ${draft.event.url ? `<p><strong>URL:</strong> ${escapeHtml(draft.event.url)}</p>` : ''}
            ${draft.image_url ? `<p><strong>Image:</strong> <a href="${escapeHtml(draft.image_url)}" style="color:#4ec9b0;">${escapeHtml(draft.image_url)}</a></p>` : ''}
        </div>
    ` : `
        <div class="draft-meta">
            <p><strong>Date:</strong> ${escapeHtml(draft.event.date)} at ${escapeHtml(draft.event.time)}</p>
            <p><strong>Location:</strong> ${escapeHtml(draft.event.location)}</p>
            <p><strong>URL:</strong> ${escapeHtml(draft.event.url || 'N/A')}</p>
            ${draft.image_url ? `<p><strong>Image:</strong> <a href="${escapeHtml(draft.image_url)}" style="color:#4ec9b0;">${escapeHtml(draft.image_url)}</a></p>` : ''}
        </div>
    `;

    detailDiv.innerHTML = `
        <div class="draft-detail-header">
            <h3>${escapeHtml(draft.event.title)}</h3>
            <span class="draft-status-badge ${statusClass}">${escapeHtml(draft.status)}</span>
            <button onclick="closeDraftDetail()" class="btn-secondary">Close</button>
        </div>

        ${metaHtml}

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
            ${draft.status === 'approved' ? `
                <button data-action="check-connections" class="btn-secondary">Check Connections</button>
                <button data-action="publish" class="btn-primary">Publish</button>
            ` : ''}
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
    const checkBtn = detailDiv.querySelector('[data-action="check-connections"]');
    if (checkBtn) checkBtn.addEventListener('click', () => checkConnectionsInDetail());
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

// ============================================================================
// Connection management
// ============================================================================

async function checkConnections() {
    const { invoke } = window.__TAURI__.core;
    const statusDiv = document.getElementById('connection-status');
    statusDiv.style.display = 'block';
    statusDiv.innerHTML = '<p class="loading">Checking connections...</p>';

    try {
        const result = await invoke('manage_connections', { toolkits: null });
        renderConnectionStatus(statusDiv, result);
    } catch (error) {
        showError(statusDiv, 'Connection check failed: ' + String(error));
    }
}

async function checkConnectionsInDetail() {
    const { invoke } = window.__TAURI__.core;
    const resultDiv = document.getElementById('draft-action-result');
    resultDiv.innerHTML = '<p class="loading">Checking connections...</p>';

    try {
        const result = await invoke('manage_connections', { toolkits: null });
        renderConnectionStatus(resultDiv, result);
    } catch (error) {
        showError(resultDiv, 'Connection check failed: ' + String(error));
    }
}

function renderConnectionStatus(container, result) {
    const allActive = result.all_active;
    const results = result.results || {};

    let html = '<div class="form-section" style="padding: 12px;">';
    html += '<h4 style="margin-bottom: 8px;">' +
        (allActive ? '<span style="color:#4ec9b0;">All connections active</span>'
                   : '<span style="color:#f48771;">Some connections need attention</span>') +
        '</h4>';

    html += '<div style="display: flex; gap: 12px; flex-wrap: wrap;">';
    for (const [toolkit, info] of Object.entries(results)) {
        const status = info.status || 'unknown';
        let color, label, hint;
        switch (status) {
            case 'active':
                color = '#4ec9b0'; label = 'connected'; hint = '';
                break;
            case 'needs_auth':
                color = '#f48771'; label = 'needs auth';
                if (info.redirect_url) {
                    hint = '<br><a href="' + escapeHtml(info.redirect_url) + '" target="_blank" ' +
                        'style="color:#569cd6;font-size:12px;">Connect ' + escapeHtml(name) + ' &rarr;</a>';
                } else {
                    hint = '<br><span style="font-size:11px;color:#858585;">Click Check Connections to get auth link</span>';
                }
                break;
            case 'needs_config':
                color = '#cca700'; label = 'needs config';
                hint = info.note ? '<br><span style="font-size:11px;color:#858585;">' +
                    escapeHtml(info.note) + '</span>' : '';
                break;
            case 'config_required':
                color = '#cca700'; label = 'needs config'; hint = '';
                break;
            case 'not_available':
                color = '#858585'; label = info.note || 'unavailable'; hint = '';
                break;
            default:
                color = '#f48771'; label = status;
                hint = info.error ? '<br><span style="font-size:11px;color:#858585;">' +
                    escapeHtml(info.error).substring(0, 100) + '</span>' : '';
                break;
        }

        html += '<div style="padding: 6px 12px; background: #2d2d2d; border-radius: 4px; border-left: 3px solid ' + color + ';">';
        html += '<strong style="color:' + color + ';">' + escapeHtml(toolkit) + '</strong>';
        html += '<span style="margin-left: 8px; font-size: 12px; color: #858585;">' + escapeHtml(label) + '</span>';
        html += hint;
        html += '</div>';
    }
    html += '</div></div>';

    container.innerHTML = html;
}

// Load drafts when tab is shown
document.addEventListener('DOMContentLoaded', () => {
    const draftsBtn = document.querySelector('.tab-btn[data-tab="drafts"]');
    if (draftsBtn) {
        draftsBtn.addEventListener('click', loadDraftsList);
    }
});
