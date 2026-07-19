/**
 * MVP Text Chat — Intermediary Agent frontend
 * 
 * Flow:
 * 1. User types message → POST /api/chat → receive stream_id
 * 2. Connect to SSE: GET /api/chat/stream?stream_id=XXX
 * 3. Render events as they arrive (user → refined → hermes_raw → distilled)
 * 4. Handle reconnection and demo mode
 */

(function() {
    'use strict';

    // DOM elements
    const transcriptEl = document.getElementById('transcript');
    const inputEl = document.getElementById('composer-input');
    const sendBtn = document.getElementById('send-btn');
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const demoBtn = document.getElementById('demo-btn');

    // State
    let eventSource = null;
    let currentStreamId = null;
    let isProcessing = false;
    let reconnectAttempts = 0;
    const MAX_RECONNECT_ATTEMPTS = 5;

    // --- Status management ---

    function setStatus(connected, text) {
        if (connected) {
            statusDot.classList.add('connected');
            statusText.textContent = text || 'Connected';
        } else {
            statusDot.classList.remove('connected');
            statusText.textContent = text || 'Disconnected';
        }
    }

    // --- Message rendering ---

    function createMessageElement(speaker, text, timestamp) {
        const msg = document.createElement('div');
        msg.className = `message ${speaker}`;

        // Speaker label
        const label = document.createElement('div');
        label.className = 'speaker-label';
        label.textContent = getSpeakerLabel(speaker);
        msg.appendChild(label);

        // Content
        const content = document.createElement('div');
        content.className = 'content';
        content.textContent = text;
        msg.appendChild(content);

        // Timestamp
        const time = document.createElement('div');
        time.className = 'timestamp';
        time.textContent = formatTimestamp(timestamp);
        msg.appendChild(time);

        return msg;
    }

    function getSpeakerLabel(speaker) {
        const labels = {
            'user': 'You',
            'refined': 'Refined Prompt',
            'hermes_raw': 'Hermes Response',
            'distilled': 'Summary',
            'system': 'System',
            'error': 'Error'
        };
        return labels[speaker] || speaker;
    }

    function formatTimestamp(ts) {
        if (!ts) return '';
        try {
            const d = new Date(ts);
            return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        } catch {
            return '';
        }
    }

    function appendMessage(speaker, text, timestamp) {
        if (!text && text !== 0) return;
        const el = createMessageElement(speaker, String(text), timestamp);
        transcriptEl.appendChild(el);
        scrollToBottom();
    }

    function scrollToBottom() {
        const container = document.querySelector('.transcript-container');
        if (container) {
            container.scrollTop = container.scrollHeight;
        }
    }

    // --- Typing indicator ---

    function showTypingIndicator() {
        const existing = document.querySelector('.typing-indicator');
        if (existing) return;

        const indicator = document.createElement('div');
        indicator.className = 'typing-indicator';
        indicator.id = 'typing-indicator';
        indicator.innerHTML = '<span></span><span></span><span></span>';
        transcriptEl.appendChild(indicator);
        scrollToBottom();
    }

    function hideTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) indicator.remove();
    }

    // --- SSE Connection ---

    function connectSSE(streamId) {
        // Close existing connection
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }

        currentStreamId = streamId;
        const url = `/api/chat/stream?stream_id=${encodeURIComponent(streamId)}`;

        setStatus(true, 'Streaming...');

        eventSource = new EventSource(url);

        eventSource.onopen = () => {
            reconnectAttempts = 0;
        };

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleStreamEvent(data);
            } catch (e) {
                console.error('Failed to parse SSE message:', event.data, e);
            }
        };

        eventSource.onerror = (err) => {
            console.error('SSE error:', err);
            hideTypingIndicator();

            if (eventSource.readyState === EventSource.CLOSED) {
                setStatus(false, 'Stream ended');
            } else {
                setStatus(false, 'Connection error');
            }

            // Auto-reconnect logic
            eventSource.close();
            eventSource = null;

            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS && currentStreamId) {
                reconnectAttempts++;
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
                setStatus(false, `Reconnecting (${reconnectAttempts})...`);
                setTimeout(() => {
                    if (currentStreamId) connectSSE(currentStreamId);
                }, delay);
            } else {
                setStatus(false, 'Disconnected');
                isProcessing = false;
                updateUI();
            }
        };
    }

    function handleStreamEvent(data) {
        const { speaker, text, timestamp, emotion } = data;

        // Handle special events
        if (speaker === 'system') {
            if (text === 'stream_start') {
                showTypingIndicator();
                return;
            }
            if (text === 'stream_end' || text === 'done') {
                hideTypingIndicator();
                setStatus(true, 'Connected');
                isProcessing = false;
                updateUI();
                return;
            }
            if (text === 'error') {
                hideTypingIndicator();
                appendMessage('error', data.error || 'An error occurred', timestamp);
                isProcessing = false;
                updateUI();
                return;
            }
            appendMessage('system', text, timestamp);
            return;
        }

        // Hide typing indicator on first real content
        hideTypingIndicator();

        // Render the message
        appendMessage(speaker, text, timestamp);
    }

    // --- Send message ---

    async function sendMessage() {
        const text = inputEl.value.trim();
        if (!text || isProcessing) return;

        isProcessing = true;
        updateUI();

        // Show user message immediately
        appendMessage('user', text, new Date().toISOString());
        inputEl.value = '';
        autoResize();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            const streamId = data.stream_id;

            if (!streamId) {
                throw new Error('No stream_id received from server');
            }

            connectSSE(streamId);
        } catch (err) {
            console.error('Failed to send message:', err);
            hideTypingIndicator();
            appendMessage('error', `Failed to send: ${err.message}`, new Date().toISOString());
            isProcessing = false;
            updateUI();
            setStatus(false, 'Error');
        }
    }

    // --- UI state ---

    function updateUI() {
        sendBtn.disabled = isProcessing;
        inputEl.disabled = isProcessing;
        if (!isProcessing) {
            inputEl.focus();
        }
    }

    function autoResize() {
        inputEl.style.height = 'auto';
        inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + 'px';
    }

    // --- Demo mode ---

    function fillDemoText() {
        const samples = [
            "What's the weather like today?",
            "Tell me a joke about programming",
            "How do I make a perfect cup of coffee?",
            "Explain quantum computing in simple terms",
            "What are the best practices for writing clean code?"
        ];
        const sample = samples[Math.floor(Math.random() * samples.length)];
        inputEl.value = sample;
        autoResize();
        inputEl.focus();
    }

    // --- Event listeners ---

    sendBtn.addEventListener('click', sendMessage);

    inputEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    inputEl.addEventListener('input', autoResize);

    demoBtn.addEventListener('click', fillDemoText);

    // --- Initialize ---

    function init() {
        setStatus(false, 'Ready');
        updateUI();
        inputEl.focus();

        // Add welcome message
        appendMessage('system', 'Welcome! Type a message to chat with the Intermediary Agent.', new Date().toISOString());
    }

    init();
})();
