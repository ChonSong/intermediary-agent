/**
 * MVP Text Chat — Intermediary Agent frontend
 */

(function() {
    'use strict';

    const transcriptEl = document.getElementById('transcript');
    const inputEl = document.getElementById('composer-input');
    const sendBtn = document.getElementById('send-btn');
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const demoBtn = document.getElementById('demo-btn');

    let eventSource = null;
    let currentStreamId = null;
    let isProcessing = false;
    let reconnectAttempts = 0;
    const MAX_RECONNECT_ATTEMPTS = 5;
    
    let sessionId = null;
    let authCookie = null;
    let useRealHermes = false;

    function setStatus(connected, text) {
        if (connected) {
            statusDot.classList.add('connected');
            statusText.textContent = text || 'Connected';
        } else {
            statusDot.classList.remove('connected');
            statusText.textContent = text || 'Connected';
        }
    }

    function createMessageElement(data) {
        const speaker = data.speaker;
        const text = data.text;
        const timestamp = data.timestamp;
        const isReasoning = data.is_reasoning;
        const isAnswer = data.is_answer;

        const msg = document.createElement('div');
        msg.className = `message ${speaker}`;
        
        if (isReasoning) msg.classList.add('reasoning');
        if (isAnswer) msg.classList.add('answer');

        // Speaker label
        const label = document.createElement('div');
        label.className = 'speaker-label';
        let labelText = getSpeakerLabel(speaker);
        // Don't append type to label — the pill shows that
        label.textContent = labelText;
        msg.appendChild(label);

        // Content
        const content = document.createElement('div');
        content.className = 'content';
        content.textContent = text;
        msg.appendChild(content);

        // Timestamp
        const timeEl = document.createElement('div');
        timeEl.className = 'timestamp';
        timeEl.textContent = formatTimestamp(timestamp);
        msg.appendChild(timeEl);

        // Type indicator pill
        if (isReasoning || isAnswer) {
            const pill = document.createElement('div');
            pill.className = 'pill';
            pill.textContent = isReasoning ? 'reasoning' : 'answer';
            msg.appendChild(pill);
        }

        return msg;
    }

    function getSpeakerLabel(speaker) {
        const labels = {
            'user': 'You',
            'intermediary': 'Refined',
            'hermes_raw': 'Hermes',
            'agent_speaking': 'Answer',
            'system': 'System'
        };
        return labels[speaker] || speaker;
    }

    function formatTimestamp(ts) {
        if (!ts) return '';
        try {
            const d = new Date(ts * 1000);
            return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        } catch {
            return '';
        }
    }

    function appendMessage(data) {
        const el = createMessageElement(data);
        transcriptEl.appendChild(el);
        scrollToBottom();
    }

    function scrollToBottom() {
        const container = document.querySelector('.transcript-container');
        if (container) container.scrollTop = container.scrollHeight;
    }

    function showTypingIndicator(text) {
        hideTypingIndicator();
        const indicator = document.createElement('div');
        indicator.className = 'typing-indicator';
        indicator.id = 'typing-indicator';
        indicator.innerHTML = `<span></span><span></span><span></span><em>${text || 'Hermes is thinking...'}</em>`;
        transcriptEl.appendChild(indicator);
        scrollToBottom();
    }

    function hideTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) indicator.remove();
    }

    function connectSSE(streamId) {
        if (eventSource) eventSource.close();

        currentStreamId = streamId;
        const url = `/api/chat/stream?stream_id=${encodeURIComponent(streamId)}`;

        showTypingIndicator();

        eventSource = new EventSource(url);

        eventSource.onopen = () => reconnectAttempts = 0;

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                hideTypingIndicator();
                handleStreamEvent(data);
            } catch (e) {
                console.error('Failed to parse SSE message:', event.data, e);
            }
        };

        eventSource.onerror = (err) => {
            hideTypingIndicator();
            if (eventSource) eventSource.close();
            eventSource = null;
            
            if (isProcessing && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts++;
                setTimeout(() => {
                    if (currentStreamId && isProcessing) connectSSE(currentStreamId);
                }, 1000);
            }
        };
    }

    function handleStreamEvent(data) {
        const { speaker, text, is_reasoning, is_answer } = data;

        if (speaker === 'system' && text === 'done') {
            hideTypingIndicator();
            setStatus(false, 'Connected');
            isProcessing = false;
            updateUI();
            return;
        }

        hideTypingIndicator();
        
        // Show "Hermes is thinking..." next time around
        if (is_reasoning) {
            appendMessage(data);
            showTypingIndicator();
            return;
        }

        if (is_answer) {
            appendMessage(data);
            return;
        }

        appendMessage(data);
    }

    async function initSession() {
        try {
            const resp = await fetch('/api/session', { method: 'POST' });
            if (resp.ok) {
                const data = await resp.json();
                sessionId = data.session_id;
                authCookie = data.cookie;
                useRealHermes = true;
                setStatus(false, 'Ready (Real Hermes)');
                return;
            }
        } catch (e) {}
        useRealHermes = false;
        setStatus(false, 'Ready (Demo)');
    }

    async function sendMessage() {
        const text = inputEl.value.trim();
        if (!text || isProcessing) return;

        isProcessing = true;
        updateUI();

        appendMessage({ speaker: 'user', text: text, timestamp: Date.now() / 1000 });
        inputEl.value = '';
        inputEl.style.height = 'auto';

        try {
            const body = { message: text };
            if (useRealHermes && sessionId && authCookie) {
                body.session_id = sessionId;
                body.cookie = authCookie;
            }
            
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const data = await response.json();
            if (data.error) throw new Error(data.error);

            connectSSE(data.stream_id);
        } catch (err) {
            hideTypingIndicator();
            appendMessage({ speaker: 'error', text: `Failed: ${err.message}`, timestamp: Date.now() / 1000 });
            isProcessing = false;
            updateUI();
        }
    }

    function updateUI() {
        sendBtn.disabled = isProcessing;
        inputEl.disabled = isProcessing;
        if (!isProcessing) inputEl.focus();
    }

    function fillDemoText() {
        const samples = ["What's the weather like?", "Tell me a joke about programming"];
        inputEl.value = samples[Math.floor(Math.random() * samples.length)];
        inputEl.focus();
    }

    sendBtn.addEventListener('click', sendMessage);
    inputEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    demoBtn.addEventListener('click', fillDemoText);

    setStatus(false, 'Connecting...');
    appendMessage({ speaker: 'system', text: 'Initializing...', timestamp: Date.now() / 1000 });
    
    initSession().then(() => {
        const firstMsg = transcriptEl.querySelector('.message.system');
        if (firstMsg) firstMsg.remove();
        appendMessage({ 
            speaker: 'system', 
            text: useRealHermes ? 'Connected to Real Hermes.' : 'Running in demo mode.', 
            timestamp: Date.now() / 1000 
        });
    });
})();
