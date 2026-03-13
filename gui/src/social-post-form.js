// social-post-form.js - Generic social post form

async function submitSocialPost() {
    const { invoke } = window.__TAURI__.core;
    const resultDiv = document.getElementById('social-result');

    const topic = document.getElementById('sp-topic').value.trim();
    const content = document.getElementById('sp-content').value.trim();

    if (!topic || !content) {
        showError(resultDiv, 'Topic and Content are required.');
        return;
    }

    const url = document.getElementById('sp-url').value.trim();
    const imageUrl = document.getElementById('sp-image-url').value.trim();
    const imagePrompt = document.getElementById('sp-image-prompt').value.trim();
    const tone = document.getElementById('sp-tone').value;
    const cta = document.getElementById('sp-cta').value.trim();
    const hashtags = document.getElementById('sp-hashtags').value.trim();
    const discordChannel = document.getElementById('sp-discord-channel').value.trim();
    const facebookPage = document.getElementById('sp-facebook-page').value.trim();

    const skipParts = [];
    if (!document.getElementById('sp-plat-twitter').checked) skipParts.push('twitter');
    if (!document.getElementById('sp-plat-linkedin').checked) skipParts.push('linkedin');
    if (!document.getElementById('sp-plat-instagram').checked) skipParts.push('instagram');
    if (!document.getElementById('sp-plat-facebook').checked) skipParts.push('facebook');
    if (!document.getElementById('sp-plat-discord').checked) skipParts.push('discord');
    const skipPlatforms = skipParts.join(',');

    createProgressPanel('social-progress');
    startListening('social-progress', 'social_post');
    resultDiv.innerHTML = '<p class="loading">Posting...</p>';

    document.getElementById('social-submit-btn').disabled = true;

    try {
        const result = await invoke('social_post', {
            topic, content,
            url: url || null,
            image_url: imageUrl || null,
            image_prompt: imagePrompt || null,
            tone: tone || null,
            cta: cta || null,
            hashtags: hashtags || null,
            discord_channel_id: discordChannel || null,
            facebook_page_id: facebookPage || null,
            skip_platforms: skipPlatforms || null,
        });
        resultDiv.innerHTML = `<pre class="result-json">${escapeHtml(JSON.stringify(result, null, 2))}</pre>`;
    } catch (error) {
        showError(resultDiv, String(error));
    } finally {
        stopListening('social-progress');
        document.getElementById('social-submit-btn').disabled = false;
    }
}
