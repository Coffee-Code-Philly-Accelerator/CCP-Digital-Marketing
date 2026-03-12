// progress.js - Real-time recipe progress rendering via Tauri events

const progressListeners = new Map();

function createProgressPanel(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = `
        <div class="progress-header">
            <span class="progress-title">Progress</span>
            <span class="progress-elapsed" id="${containerId}-elapsed"></span>
        </div>
        <div class="progress-phases" id="${containerId}-phases"></div>
        <div class="progress-result" id="${containerId}-result" style="display:none;"></div>
    `;
    container.style.display = 'block';
}

function resetProgressPanel(containerId) {
    const container = document.getElementById(containerId);
    if (container) {
        container.style.display = 'none';
        container.innerHTML = '';
    }
}

function startListening(containerId, commandFilter) {
    // Stop any existing listener
    stopListening(containerId);

    const phaseStatuses = {};
    let startTime = Date.now();

    const { listen } = window.__TAURI__.event;
    const unlistenPromise = listen('recipe-progress', (event) => {
        const data = event.payload;
        if (commandFilter && data.command !== commandFilter) return;

        const phasesDiv = document.getElementById(containerId + '-phases');
        const elapsedSpan = document.getElementById(containerId + '-elapsed');
        const resultDiv = document.getElementById(containerId + '-result');
        if (!phasesDiv) return;

        // Update elapsed
        if (elapsedSpan) {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            elapsedSpan.textContent = elapsed + 's';
        }

        // Update phase status
        phaseStatuses[data.phase] = {
            status: data.status,
            message: data.message,
        };

        // Render phase pills
        phasesDiv.innerHTML = Object.entries(phaseStatuses).map(([phase, info]) => {
            const statusClass = getStatusClass(info.status);
            return `<div class="progress-phase ${statusClass}">
                <span class="phase-name">${escapeHtml(phase)}</span>
                <span class="phase-status">${escapeHtml(info.status)}</span>
            </div>`;
        }).join('');

        // Show result on completion
        if (data.status === 'completed' || data.status === 'failed') {
            if (resultDiv && data.result) {
                resultDiv.style.display = 'block';
                resultDiv.innerHTML = `<pre>${escapeHtml(JSON.stringify(data.result, null, 2))}</pre>`;
            }
        }
    });

    progressListeners.set(containerId, unlistenPromise);
}

function stopListening(containerId) {
    const unlistenPromise = progressListeners.get(containerId);
    if (unlistenPromise) {
        unlistenPromise.then(unlisten => unlisten());
        progressListeners.delete(containerId);
    }
}

function getStatusClass(status) {
    if (status === 'completed') return 'phase-completed';
    if (status === 'failed') return 'phase-failed';
    if (status === 'skipped') return 'phase-skipped';
    if (status === 'started' || status.startsWith('polling')) return 'phase-running';
    return 'phase-pending';
}
