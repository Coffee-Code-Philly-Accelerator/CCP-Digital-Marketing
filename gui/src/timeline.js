// timeline.js - Gantt-style timeline visualization (vanilla JS)
// Uses escapeHtml() and formatTimestampShared() from app.js

async function loadWorkflowTimeline(workflowId) {
    const { invoke } = window.__TAURI__.core;
    const container = document.getElementById('timeline-container');
    const title = document.getElementById('timeline-title');
    const content = document.getElementById('timeline-content');

    title.textContent = `Workflow #${workflowId} Timeline`;
    content.innerHTML = '<div class="loading">Loading timeline...</div>';
    container.style.display = 'block';

    try {
        const toolCalls = await invoke('get_workflow_tool_calls', { workflow_id: workflowId });

        if (toolCalls.length === 0) {
            content.innerHTML = '<p style="color: #858585;">No tool calls found for this workflow</p>';
            return;
        }

        // Render timeline
        renderTimeline(toolCalls);
    } catch (error) {
        content.innerHTML = `<p style="color: #f48771;">Error loading timeline: ${escapeHtml(String(error))}</p>`;
    }
}

function renderTimeline(toolCalls) {
    const content = document.getElementById('timeline-content');

    // Calculate time range
    const startTime = Math.min(...toolCalls.map(tc => tc.created_at));
    const endTime = Math.max(...toolCalls.map(tc => tc.created_at));
    const duration = endTime - startTime;

    // Calculate total latency
    const totalLatency = toolCalls.reduce((sum, tc) => sum + (tc.latency_ms || 0), 0);

    // Summary
    const summary = document.createElement('div');
    summary.style.marginBottom = '20px';
    summary.style.padding = '10px';
    summary.style.background = '#2d2d2d';
    summary.style.borderRadius = '4px';
    summary.innerHTML = `
        <strong>Summary:</strong>
        ${toolCalls.length} tool calls |
        Duration: ${formatDuration(duration)} |
        Total Latency: ${totalLatency}ms |
        Success: ${toolCalls.filter(tc => tc.status === 'success').length} |
        Errors: ${toolCalls.filter(tc => tc.status === 'error').length}
    `;
    content.innerHTML = '';
    content.appendChild(summary);

    // Render each tool call as a timeline item
    toolCalls.forEach((tc, index) => {
        const item = document.createElement('div');
        item.className = `tool-call ${tc.status}`;

        const relativeTime = tc.created_at - startTime;
        const timeLabel = formatDuration(relativeTime);

        item.innerHTML = `
            <div class="tool-call-header">
                <span>${index + 1}. ${escapeHtml(tc.tool_name)}</span>
                <span>${escapeHtml(tc.status.toUpperCase())} (${tc.latency_ms || '?'}ms)</span>
            </div>
            <div class="tool-call-details">
                Time: +${timeLabel} | ID: ${tc.id} | Created: ${formatTimestampShared(tc.created_at)}
            </div>
        `;

        content.appendChild(item);
    });
}

function formatDuration(seconds) {
    if (seconds < 60) {
        return `${seconds}s`;
    }
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}m ${secs}s`;
}
