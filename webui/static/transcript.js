/**
 * Transcript UI — connects to WebSocket and displays intermediary events.
 * 
 * Events from server:
 *   { speaker: "user"|"hermes_raw"|"intermediary"|"agent_speaking"|"system", text: string, timestamp: string }
 */

const transcript = document.getElementById('transcript');
const statusEl = document.getElementById('status');

let ws = null;
let reconnectDelay = 1000;

function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/transcript`);

    ws.onopen = () => {
        console.log('WebSocket connected');
        statusEl.textContent = 'Connected';
        statusEl.className = 'status connected';
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleMessage(data);
        } catch (e) {
            console.error('Bad message:', event.data);
        }
    };

    ws.onclose = () => {
        console.log('WebSocket closed, reconnecting...');
        statusEl.textContent = 'Disconnected';
        statusEl.className = 'status disconnected';
        setTimeout(connect, reconnectDelay);
    };

    ws.onerror = (err) => {
        console.error('WebSocket error:', err);
    };
}

function handleMessage(data) {
    const { speaker, text, timestamp } = data;
    if (!text) return;

    const msg = document.createElement('div');
    msg.className = `message ${speaker}`;

    const label = document.createElement('div');
    label.className = 'speaker';
    label.textContent = speaker.replace('_', ' ').toUpperCase();
    msg.appendChild(label);

    const content = document.createElement('div');
    content.className = 'content';
    content.textContent = text;
    msg.appendChild(content);

    if (timestamp) {
        const time = document.createElement('div');
        time.className = 'timestamp';
        time.textContent = new Date(timestamp).toLocaleTimeString();
        msg.appendChild(time);
    }

    transcript.appendChild(msg);
    transcript.scrollTop = transcript.scrollHeight;
}

// Start connection on load
connect();
