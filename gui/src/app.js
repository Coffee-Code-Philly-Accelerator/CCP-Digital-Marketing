// app.js - Tab router and shared utilities

function switchTab(tabName) {
    // Hide all tab sections
    document.querySelectorAll('.tab-section').forEach(section => {
        section.style.display = 'none';
    });
    // Deactivate all nav buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    // Show selected section and activate button
    const section = document.getElementById('tab-' + tabName);
    if (section) section.style.display = 'block';
    const btn = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
    if (btn) btn.classList.add('active');
}

function formatTimestampShared(timestamp) {
    if (!timestamp) return '';
    if (typeof timestamp === 'number') {
        return new Date(timestamp * 1000).toLocaleString();
    }
    return new Date(timestamp).toLocaleString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showError(container, message) {
    container.innerHTML = `<p style="color: #f48771; padding: 10px;">${escapeHtml(message)}</p>`;
}

function showSuccess(container, message) {
    container.innerHTML = `<p style="color: #4ec9b0; padding: 10px;">${escapeHtml(message)}</p>`;
}

// Initialize tab navigation
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            switchTab(btn.dataset.tab);
        });
    });
    // Default to telemetry tab
    switchTab('telemetry');
});
