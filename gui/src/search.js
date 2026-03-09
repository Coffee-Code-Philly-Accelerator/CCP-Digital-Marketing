// search.js - Correlation search functionality (vanilla JS)

async function searchCorrelation() {
    const { invoke } = window.__TAURI__.core;
    const artifact = document.getElementById('search-artifact').value.trim();
    const resultsDiv = document.getElementById('search-results');

    if (!artifact) {
        alert('Please enter an artifact to search for');
        return;
    }

    resultsDiv.innerHTML = '<div class="loading">Searching...</div>';

    try {
        const workflows = await invoke('search_correlation', { artifact });

        if (workflows.length === 0) {
            resultsDiv.innerHTML = '<p style="color: #858585; margin-top: 10px;">No workflows found containing this artifact</p>';
            return;
        }

        // Render results
        const table = document.createElement('table');
        table.style.width = '100%';
        table.style.borderCollapse = 'collapse';
        table.style.marginTop = '15px';

        table.innerHTML = `
            <thead>
                <tr style="background: #2d2d2d;">
                    <th style="padding: 8px; text-align: left; border-bottom: 1px solid #3e3e3e;">ID</th>
                    <th style="padding: 8px; text-align: left; border-bottom: 1px solid #3e3e3e;">Type</th>
                    <th style="padding: 8px; text-align: left; border-bottom: 1px solid #3e3e3e;">Status</th>
                    <th style="padding: 8px; text-align: left; border-bottom: 1px solid #3e3e3e;">Created</th>
                    <th style="padding: 8px; text-align: left; border-bottom: 1px solid #3e3e3e;">Action</th>
                </tr>
            </thead>
            <tbody>
                ${workflows.map(wf => `
                    <tr style="border-bottom: 1px solid #3e3e3e;">
                        <td style="padding: 8px;">${wf.id}</td>
                        <td style="padding: 8px;">${wf.workflow_type}</td>
                        <td style="padding: 8px;" class="status-${wf.status}">${wf.status}</td>
                        <td style="padding: 8px;">${formatTimestamp(wf.created_at)}</td>
                        <td style="padding: 8px;">
                            <button onclick="loadWorkflowTimeline(${wf.id})" style="padding: 4px 8px; background: #0e639c; border: none; color: white; border-radius: 2px; cursor: pointer;">
                                View Timeline
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        `;

        resultsDiv.innerHTML = `
            <p style="margin-top: 10px; color: #4ec9b0;">
                Found ${workflows.length} workflow${workflows.length === 1 ? '' : 's'} containing "<strong>${escapeHtml(artifact)}</strong>"
            </p>
        `;
        resultsDiv.appendChild(table);
    } catch (error) {
        resultsDiv.innerHTML = `<p style="color: #f48771; margin-top: 10px;">Error: ${error}</p>`;
    }
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Allow search on Enter key
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-artifact');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                searchCorrelation();
            }
        });
    }
});
