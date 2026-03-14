// chat-view.js - Chat-style social post draft generation

function toggleChatSettings() {
    document.getElementById('chat-settings').classList.toggle('open');
}

function appendChatMessage(container, role, text) {
    const div = document.createElement('div');
    div.className = 'chat-msg chat-msg-' + role;
    div.textContent = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
}

function appendThinking(container) {
    const id = 'thinking-' + Date.now();
    const div = document.createElement('div');
    div.className = 'chat-msg chat-msg-thinking';
    div.id = id;
    div.textContent = 'Generating platform copies...';
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return id;
}

function removeThinking(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function appendDraftResult(container, result) {
    const div = document.createElement('div');
    div.className = 'chat-msg chat-msg-system';

    const copies = result.copies || {};
    const imageUrl = result.image_url || '';

    let html = '<strong>Draft generated and saved!</strong>';
    if (imageUrl) {
        html += '<p style="margin-top:6px;font-size:12px;color:#858585;">Image: ' + escapeHtml(imageUrl) + '</p>';
    }

    html += '<div class="chat-copies-grid">';
    const platforms = ['twitter', 'linkedin', 'instagram', 'facebook', 'discord'];
    for (const p of platforms) {
        const text = copies[p] || '(empty)';
        html += '<div class="chat-copy-item"><label>' + escapeHtml(p) + '</label><p>' + escapeHtml(text) + '</p></div>';
    }
    html += '</div>';

    html += '<div style="margin-top:10px;">';
    html += '<button class="btn-secondary" style="font-size:12px;" data-action="view-drafts">View in Drafts</button>';
    html += '</div>';

    div.innerHTML = html;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;

    div.querySelector('[data-action="view-drafts"]').addEventListener('click', () => {
        switchTab('drafts');
        loadDraftsList();
    });
}

async function submitChatMessage() {
    const { invoke } = window.__TAURI__.core;
    const input = document.getElementById('chat-input');
    const container = document.getElementById('chat-messages');
    const btn = document.getElementById('chat-send-btn');
    const message = input.value.trim();

    if (!message) return;

    // Show user message
    appendChatMessage(container, 'user', message);
    input.value = '';
    btn.disabled = true;

    // Read optional settings
    const url = document.getElementById('chat-url').value.trim() || null;
    const tone = document.getElementById('chat-tone').value || null;
    const imageUrl = document.getElementById('chat-image-url').value.trim() || null;
    const imagePrompt = document.getElementById('chat-image-prompt').value.trim() || null;
    const cta = document.getElementById('chat-cta').value.trim() || null;
    const hashtags = document.getElementById('chat-hashtags').value.trim() || null;
    const discordChannel = document.getElementById('chat-discord-channel').value.trim() || null;
    const facebookPage = document.getElementById('chat-facebook-page').value.trim() || null;

    // Show thinking indicator
    const thinkingId = appendThinking(container);

    // Start progress listener
    createProgressPanel('chat-progress');
    startListening('chat-progress', 'chat_generate_draft');

    try {
        const result = await invoke('chat_generate_draft', {
            message,
            url,
            tone,
            image_url: imageUrl,
            image_prompt: imagePrompt,
            cta,
            hashtags,
            discord_channel_id: discordChannel,
            facebook_page_id: facebookPage,
            skip_platforms: null,
        });

        removeThinking(thinkingId);

        if (result.warning) {
            appendChatMessage(container, 'system', 'Warning: ' + result.warning);
        } else {
            appendDraftResult(container, result);
        }
    } catch (error) {
        removeThinking(thinkingId);
        appendChatMessage(container, 'system', 'Error: ' + String(error));
    } finally {
        stopListening('chat-progress');
        btn.disabled = false;
    }
}

// Enter key sends, Shift+Enter for newline
document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('chat-input');
    if (input) {
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submitChatMessage();
            }
        });
    }
});
