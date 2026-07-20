/**
 * Intermediary Agent extension for hermes-webui.
 *
 * This extension adds a side panel (and a rail button) that connects to a
 * separate Intermediary Agent service (Pure-Python FastAPI). It communicates
 * with hermes-webui's existing /api/chat endpoints to proxy user messages to
 * the Intermediary service and stream the response back via Server-Sent Events.
 *
 * The extension can also talk to a local FastAPI intermediary backend that
 * lives in /Users/<you>/workspace/intermediary-agent. By default it expects the
 * intermediary server's base window to be available at the parent origin.
 */

(function () {
    'use strict';

    // ── DOM setup ──────────────────────────────────────────────────────────────

    const wrap = document.createElement('div');
    wrap.id = 'intermediary-panel';
    wrap.style.cssText = [
        'display: none',
        'position: fixed',
        'top: 0; right: 0',
        'width: 420px; height: 100vh',
        'z-index: 1000',
        'background: #0e0e0f',
        'border-left: 1px solid #333',
        'box-shadow: -4px 0 16px rgba(0,0,0,0.4)',
        'flex-direction: column',
        'font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        'font-size: 13px',
        'color: #d7d7d7',
    ].join(';');

    wrap.innerHTML = `
        <div style="display:flex;align-items:center;padding:8px 12px;border-bottom:1px solid #333;gap:8px;">
            <span style="color:#00b894;font-weight:600;font-size:14px;">Intermediary</span>
            <select id="i-session" style="flex:1;background:#18181a;color:#d7d7d7;border:1px solid #333;border-radius:4px;padding:4px 8px;font-size:12px;"></select>
            <button id="i-toggle" title="Close" style="background:none;border:none;color:#888;cursor:pointer;font-size:16px;padding:4px;">×</button>
        </div>
        <div id="i-transcript" style="flex:1;overflow-y:auto;padding:8px;display:flex;flex-direction:column;gap:6px;"></div>
        <div style="padding:8px;border-top:1px solid #333;display:flex;gap:6px;">
            <textarea id="i-input" placeholder="Send to intermediary..." rows="1" style="flex:1;background:#18181a;color:#d7d7d7;border:1px solid #333;border-radius:6px;padding:6px 10px;resize:none;outline:none;font-size:13px;"></textarea>
            <button id="i-send" style="background:#00b894;color:#0e0e0f;border:none;border-radius:6px;padding:6px 12px;font-weight:600;cursor:pointer;">Send</button>
        </div>
    `;

    document.body.appendChild(wrap);

    // ── State ──────────────────────────────────────────────────────────────────

    const iToggle = document.getElementById('i-toggle');
    const iSession = document.getElementById('i-session');
    const iTranscript = document.getElementById('i-transcript');
    const iInput = document.getElementById('i-input');
    const iSend = document.getElementById('i-send');

    let isOpen = false;
    let eventSource = null;
    let cookie = null;

    // ── Helpers ────────────────────────────────────────────────────────────────

    function setIOPen(open) {
        isOpen = open;
        wrap.style.display = open ? 'flex' : 'none';
        if (!open && eventSource) { eventSource.close(); eventSource = null; }
    }

    function appendMsg(speaker, text, klass) {
        const div = document.createElement('div');
        div.className = `i-msg ${klass || ''}`;
        div.style.cssText = [
            'padding:6px 10px',
            'border-radius:6px',
            'white-space:pre-wrap',
            'word-break:break-word',
            'font-size:12px',
            klass === 'user' ? 'background:#0a84ff;color:#fff;margin-left:auto;max-width:90%;' :
            klass === 'inter' ? 'background:#1a3a2a;border:1px solid #00b894;' :
            klass === 'err'  ? 'background:#3a1a1a;border:1px solid #ff4444;' :
            klass === 'sys'  ? 'background:transparent;color:#888;font-style:italic;' :
            'background:#1c1c1e;border:1px solid #333;'
        ].join(';');

        const label = document.createElement('div');
        label.textContent = speaker;
        label.style.cssText = 'font-weight:600;font-size:10px;text-transform:uppercase;letter-spacing:0.5px;color:#888;margin-bottom:2px;';
        div.textContent = text;
        div.prepend(label);
        iTranscript.appendChild(div);
        iTranscript.scrollTop = iTranscript.scrollHeight;
    }

    // I know this is in-session, so I can ask the server for an up-to-date cookie.
    async function ensureCookie() {
        if (cookie) return cookie;
        try {
            const r = await fetch('/api/hermes-cookie', { credentials: 'include' });
            const d = await r.json();
            cookie = d.cookie || d.value;
        } catch (e) {
            cookie = null;
        }
        return cookie;
    }

    async function loadSessions() {
        try {
            const r = await fetch('/api/sessions', { credentials: 'include' });
            const d = await r.json();
            const sessions = d.sessions || [];
            iSession.innerHTML = sessions.length
                ? sessions.map(s => `<option value="${s.session_id}">${s.title || s.session_id.slice(0, 8)} (${s.message_count})</option>`).join('')
                : '<option value="">No sessions</option>';
        } catch (e) {
            iSession.innerHTML = '<option value="">Error loading sessions</option>';
        }
    }

    async function sendMessage() {
        const msg = iInput.value.trim();
        if (!msg) return;
        appendMsg('You', msg, 'user');
        iInput.value = '';
        iInput.style.height = 'auto';

        const c = await ensureCookie();
        if (!c) {
            appendMsg('System', 'No Hermes auth — please login.', 'sys');
            return;
        }

        const body = { message: msg, cookie: c };
        const sid = iSession.value;
        if (sid) body.session_id = sid;

        try {
            const r = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const d = await r.json();
            appendMsg('System', 'Connected to stream', 'sys');

            // Don't use EventSource for streaming — use fetch + ReadableStream for custom headers
            const streamResp = await fetch(`/api/chat/stream?stream_id=${d.stream_id}`, { credentials: 'include' });
            const reader = streamResp.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const parts = buffer.split('\n\n');
                buffer = parts.pop();

                for (const part of parts) {
                    try {
                        const data = JSON.parse(part.replace(/^data: /, ''));
                        if (data.speaker === 'intermediary') appendMsg('Refined', data.text, 'inter');
                        else if (data.speaker === 'hermes_raw') appendMsg('Hermes', data.text, '');
                        else if (data.speaker === 'agent_speaking') appendMsg('Answer', data.text, 'inter');
                        else if (data.speaker === 'system' && data.text === 'done') appendMsg('Done', '', 'sys');
                    } catch (e) {}
                }
            }
        } catch (e) {
            appendMsg('Error', `${e.message}`, 'err');
        }
    }

    // ── Event listeners ────────────────────────────────────────────────────────

    iToggle.addEventListener('click', () => setIOPen(!isOpen));
    iSend.addEventListener('click', sendMessage);
    iInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    iInput.addEventListener('input', () => {
        iInput.style.height = 'auto';
        iInput.style.height = Math.min(iInput.scrollHeight, 100) + 'px';
    });

    // ── Rail button ────────────────────────────────────────────────────────────

    const railBtn = document.createElement('button');
    railBtn.className = 'nav-tab has-tooltip';
    railBtn.dataset.panel = 'intermediary';
    railBtn.title = 'Intermediary';
    railBtn.style.cssText = 'background:none;border:none;color:#888;cursor:pointer;padding:6px 12px;';
    railBtn.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/><path d="M8 12h8"/><path d="M12 8v8"/></svg>';

    railBtn.addEventListener('click', () => {
        setIOPen(!isOpen);
        loadSessions();
    });

    // Find the rail and add the button
    function addRailButton() {
        const rail = document.querySelector('.rail');
        if (rail && !rail.querySelector('[data-panel="intermediary"]')) {
            // Insert before settings button
            const settingsBtn = rail.querySelector('[data-panel="settings"]');
            if (settingsBtn) rail.insertBefore(railBtn, settingsBtn);
            else rail.appendChild(railBtn);
        }
    }

    // Wait for the rail to appear
    const observer = new MutationObserver(() => addRailButton());
    observer.observe(document.body, { childList: true, subtree: true });
    addRailButton(); // try immediately in case it already exists
})();
