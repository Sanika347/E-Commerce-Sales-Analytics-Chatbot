const chatHistory = document.getElementById('chat-history');
const queryInput = document.getElementById('query-input');
const sendBtn = document.getElementById('send-btn');
const dashboard = document.getElementById('dashboard');

let lastQueryResponse = null;

// Initialize dashboard on load
window.onload = loadDashboard;

sendBtn.addEventListener('click', askQuestion);
queryInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') askQuestion();
});

async function askQuestion() {
    const question = queryInput.value.trim();
    if (!question) return;

    appendMessage(question, 'user');
    queryInput.value = '';
    
    // Add loading
    const loadingId = appendMessage("Thinking...", 'bot');

    try {
        const response = await fetch('/api/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });
        
        const data = await response.json();
        removeMessage(loadingId);
        
        if (data.error) {
            appendMessage(`Error: ${data.error}`, 'bot error');
            return;
        }

        lastQueryResponse = { ...data, user_query: question };
        renderChartResponse(data, question);
    } catch (err) {
        removeMessage(loadingId);
        appendMessage(`System error: ${err.message}`, 'bot error');
    }
}

function appendMessage(text, type) {
    const id = `msg-${Date.now()}`;
    const div = document.createElement('div');
    div.className = `message ${type}`;
    div.id = id;
    div.textContent = text;
    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return id;
}

function removeMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function renderChartResponse(data, question) {
    const msgId = `msg-${Date.now()}`;
    const div = document.createElement('div');
    div.className = 'message bot';
    div.id = msgId;
    
    const insightP = document.createElement('p');
    insightP.innerHTML = `<strong>Insight:</strong> ${data.insight}`;
    div.appendChild(insightP);

    if (data.chart_type_justification) {
        const justP = document.createElement('p');
        justP.innerHTML = `<em><strong>Chart Justification:</strong> ${data.chart_type_justification}</em>`;
        div.appendChild(justP);
    }

    if (data.chart_config && Object.keys(data.chart_config).length > 0) {
        const canvasWrapper = document.createElement('div');
        canvasWrapper.className = 'chart-wrapper';
        const canvas = document.createElement('canvas');
        canvasWrapper.appendChild(canvas);
        div.appendChild(canvasWrapper);
        
        const pinBtn = document.createElement('button');
        pinBtn.textContent = 'Pin to Dashboard';
        pinBtn.onclick = () => pinChart(lastQueryResponse);
        div.appendChild(pinBtn);

        chatHistory.appendChild(div);
        new Chart(canvas, data.chart_config);
    } else {
        chatHistory.appendChild(div);
    }
    
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

async function pinChart(payload) {
    if (!payload) return;
    try {
        const res = await fetch('/api/dashboard/pin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            alert('Pinned to dashboard!');
            loadDashboard();
        }
    } catch (err) {
        alert('Failed to pin: ' + err.message);
    }
}

async function loadDashboard() {
    try {
        const res = await fetch('/api/dashboard');
        const items = await res.json();
        
        dashboard.innerHTML = '';
        items.forEach(item => {
            const card = document.createElement('div');
            card.className = 'dashboard-card';
            
            card.innerHTML = `
                <h3>Q: ${item.user_query}</h3>
                <p><em>${item.insight}</em></p>
                <div class="chart-wrapper"><canvas id="canvas-${item.id}"></canvas></div>
                <div class="card-actions">
                    <button onclick="refreshChart('${item.id}')">Refresh</button>
                    <button onclick="deletePin('${item.id}')">Unpin</button>
                </div>
            `;
            dashboard.appendChild(card);
            
            const canvas = document.getElementById(`canvas-${item.id}`);
            new Chart(canvas, item.chart_config);
        });
    } catch (err) {
        console.error("Failed to load dashboard", err);
    }
}

async function refreshChart(id) {
    try {
        const res = await fetch(`/api/dashboard/${id}/refresh`, { method: 'POST' });
        const data = await res.json();
        
        if (data.error) {
            alert('Refresh failed: ' + data.error);
            return;
        }
        
        alert(data.message);
        loadDashboard(); // Reload to show new chart if changed
    } catch (err) {
        alert('Refresh failed: ' + err.message);
    }
}

async function deletePin(id) {
    try {
        await fetch(`/api/dashboard/${id}`, { method: 'DELETE' });
        loadDashboard();
    } catch (err) {
        alert('Delete failed: ' + err.message);
    }
}
