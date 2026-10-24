/**
 * src/gui/api_adapter.js
 * Browser-compatible polyfill for window.jarvis.
 * 
 * Replaces Electron IPC with standard HTTP REST fetch and WebSocket streaming,
 * allowing the modern JARVIS GUI to run identically inside any standard Web Browser
 * or PyWebView Desktop application without requiring Electron.
 */

(function () {
    if (window.jarvis && !window.jarvis._isWebAdapter) {
        console.log('[API Adapter] Native Electron window.jarvis detected, keeping native bridge.');
        return;
    }

    const API_BASE = window.location.origin.startsWith('http')
        ? window.location.origin
        : 'http://localhost:8000';

    const WS_URL = API_BASE.replace(/^http/, 'ws') + '/ws/chat';

    // Callbacks
    let streamTokenCallback = null;
    let statusUpdateCallback = null;
    let traceUpdateCallback = null;

    let socket = null;
    let wsReadyPromise = null;
    let activeStreamResolver = null;
    let activeStreamRejecter = null;

    function initWebSocket() {
        if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
            return;
        }

        wsReadyPromise = new Promise((resolve) => {
            try {
                socket = new WebSocket(WS_URL);

                socket.onopen = () => {
                    console.log('[API Adapter] WebSocket connected to', WS_URL);
                    resolve(true);
                };

                socket.onmessage = (event) => {
                    try {
                        const msg = JSON.parse(event.data);
                        handleWebSocketMessage(msg);
                    } catch (e) {
                        console.error('[API Adapter] Failed to parse WS message:', e);
                    }
                };

                socket.onerror = (err) => {
                    console.warn('[API Adapter] WebSocket connection warning:', err);
                    resolve(false);
                };

                socket.onclose = () => {
                    console.log('[API Adapter] WebSocket closed, retrying in 3s...');
                    setTimeout(initWebSocket, 3000);
                };
            } catch (err) {
                console.error('[API Adapter] WebSocket creation failed:', err);
                resolve(false);
            }
        });
    }

    function handleWebSocketMessage(msg) {
        switch (msg.type) {
            case 'token':
                if (streamTokenCallback) streamTokenCallback(msg.data);
                break;
            case 'trace':
                if (traceUpdateCallback) traceUpdateCallback(msg.data);
                break;
            case 'status':
                if (statusUpdateCallback) statusUpdateCallback(msg.data);
                break;
            case 'done':
                if (activeStreamResolver) {
                    activeStreamResolver({
                        success: msg.success !== false,
                        response: msg.response,
                        conversation_id: msg.conversation_id,
                        tools_used: msg.tools_used || [],
                        traces: msg.traces || []
                    });
                    activeStreamResolver = null;
                    activeStreamRejecter = null;
                }
                break;
            case 'cancelled':
                if (activeStreamResolver) {
                    activeStreamResolver({
                        success: false,
                        response: msg.message || 'Proses berhasil dibatalkan oleh pengguna.',
                        is_cancelled: true
                    });
                    activeStreamResolver = null;
                    activeStreamRejecter = null;
                }
                break;
            case 'error':
                if (activeStreamRejecter) {
                    activeStreamRejecter(new Error(msg.message || 'Stream error'));
                    activeStreamResolver = null;
                    activeStreamRejecter = null;
                }
                break;
            default:
                console.debug('[API Adapter] Unknown WS message:', msg);
        }
    }

    // Initialize WS connection immediately
    initWebSocket();

    // ==================== WINDOW.JARVIS IMPLEMENTATION ====================

    window.jarvis = {
        _isWebAdapter: true,

        // ==================== STREAMING & COMMANDS ====================
        sendCommand: async (input) => {
            const query = typeof input === 'string' ? input : (input.text || '');
            const image_base64 = typeof input === 'object' ? input.image : null;

            try {
                const res = await fetch(`${API_BASE}/api/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query, image_base64 })
                });
                return await res.json();
            } catch (err) {
                return { success: false, response: `Network Error: ${err.message}` };
            }
        },

        sendCommandStream: async (input) => {
            const query = typeof input === 'string' ? input : (input.text || '');
            const image_base64 = typeof input === 'object' ? input.image : null;

            await wsReadyPromise;

            if (socket && socket.readyState === WebSocket.OPEN) {
                return new Promise((resolve, reject) => {
                    activeStreamResolver = resolve;
                    activeStreamRejecter = reject;

                    socket.send(JSON.stringify({
                        type: 'chat',
                        query,
                        image_base64
                    }));
                });
            } else {
                // Fallback to REST POST if WebSocket is unavailable
                console.warn('[API Adapter] WebSocket not open, falling back to HTTP REST /api/chat');
                return await window.jarvis.sendCommand(input);
            }
        },

        cancelCommand: async () => {
            console.log('[API Adapter] Sending cancel command...');
            if (socket && socket.readyState === WebSocket.OPEN) {
                try {
                    socket.send(JSON.stringify({ type: 'cancel' }));
                } catch (e) {
                    console.warn('[API Adapter] Error sending cancel over WS:', e);
                }
            }
            try {
                await fetch(`${API_BASE}/api/chat/cancel`, { method: 'POST' });
            } catch (e) {
                // Ignore fallback error
            }
            if (activeStreamResolver) {
                activeStreamResolver({
                    success: false,
                    response: 'Proses berhasil dibatalkan oleh pengguna.',
                    is_cancelled: true
                });
                activeStreamResolver = null;
                activeStreamRejecter = null;
            }
        },

        onStreamToken: (callback) => {
            streamTokenCallback = callback;
        },

        onStatusUpdate: (callback) => {
            statusUpdateCallback = callback;
        },

        onTraceUpdate: (callback) => {
            traceUpdateCallback = callback;
        },

        // ==================== WEB & MEDIA TOOLS ====================
        openWeb: async (url) => {
            window.open(url, '_blank');
            return { success: true, opened: url };
        },

        scrapeWeb: async (url) => {
            const res = await fetch(`${API_BASE}/api/tools/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tool_name: 'read_webpage', args: { url } })
            });
            return await res.json();
        },

        searchWeb: async (query) => {
            const res = await fetch(`${API_BASE}/api/tools/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tool_name: 'search_web', args: { query } })
            });
            return await res.json();
        },

        searchYouTube: async (query) => {
            const res = await fetch(`${API_BASE}/api/tools/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tool_name: 'search_youtube', args: { query } })
            });
            return await res.json();
        },

        playMusic: async (query) => {
            const res = await fetch(`${API_BASE}/api/tools/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tool_name: 'play_music', args: { query } })
            });
            return await res.json();
        },

        playVideo: async (query) => {
            const res = await fetch(`${API_BASE}/api/tools/execute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tool_name: 'play_video', args: { query } })
            });
            return await res.json();
        },

        getYouTubeInfo: async (url) => {
            return { success: true, url };
        },

        // ==================== AGENT STATE ====================
        getAgentState: async () => {
            return "Ready";
        },

        updateAgentState: async (newState) => {
            if (statusUpdateCallback) statusUpdateCallback({ text: newState, state: 'idle' });
            return { success: true };
        },

        // ==================== CONVERSATIONS ====================
        listConversations: async () => {
            try {
                const res = await fetch(`${API_BASE}/api/conversations`);
                return await res.json();
            } catch (e) {
                return [];
            }
        },

        createConversation: async () => {
            try {
                const res = await fetch(`${API_BASE}/api/conversations/new`, { method: 'POST' });
                return await res.json();
            } catch (e) {
                return null;
            }
        },

        loadConversation: async (conversationId) => {
            try {
                const res = await fetch(`${API_BASE}/api/conversations/${conversationId}`);
                return await res.json();
            } catch (e) {
                return null;
            }
        },

        deleteConversation: async (conversationId) => {
            try {
                const res = await fetch(`${API_BASE}/api/conversations/${conversationId}`, { method: 'DELETE' });
                return await res.json();
            } catch (e) {
                return { success: false, error: e.message };
            }
        },

        switchConversation: async (conversationId) => {
            try {
                const res = await fetch(`${API_BASE}/api/conversations/${conversationId}/switch`, { method: 'POST' });
                return await res.json();
            } catch (e) {
                return { success: false, error: e.message };
            }
        },

        // ==================== FILE PREVIEW / CONFIRM-SAVE ====================
        confirmSaveFile: async (payload) => {
            try {
                const res = await fetch(`${API_BASE}/api/tools/confirm_save_file`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                return await res.json();
            } catch (e) {
                return { success: false, error: e.message };
            }
        },

        // ==================== SETTINGS & MODELS ====================
        getSettings: async () => {
            try {
                const res = await fetch(`${API_BASE}/api/settings`);
                return await res.json();
            } catch (e) {
                return { activeModel: "llama3.2:latest" };
            }
        },

        saveSettings: async (settings) => {
            try {
                const res = await fetch(`${API_BASE}/api/settings`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });
                return await res.json();
            } catch (e) {
                return { success: false, error: e.message };
            }
        },

        getOllamaModels: async () => {
            try {
                const res = await fetch(`${API_BASE}/api/models`);
                const models = await res.json();
                // Map array of strings or objects to { name: string } format expected by UI
                return Array.isArray(models)
                    ? models.map(m => typeof m === 'string' ? { name: m } : m)
                    : [];
            } catch (e) {
                return [{ name: "llama3.2:latest" }];
            }
        },

        // ==================== CLIPBOARD ====================
        copyToClipboard: async (text) => {
            try {
                if (navigator.clipboard) {
                    await navigator.clipboard.writeText(text);
                    return { success: true };
                }
                return { success: false, error: "Clipboard API not accessible" };
            } catch (e) {
                return { success: false, error: e.message };
            }
        },

        // ==================== WINDOW CONTROLS ====================
        minimizeWindow: () => {
            if (window.pywebview && window.pywebview.api && window.pywebview.api.minimize) {
                window.pywebview.api.minimize();
            } else {
                console.log('[API Adapter] Window minimize invoked.');
            }
        },

        maximizeWindow: () => {
            if (window.pywebview && window.pywebview.api && window.pywebview.api.maximize) {
                window.pywebview.api.maximize();
            } else {
                console.log('[API Adapter] Window maximize invoked.');
            }
        },

        closeWindow: () => {
            if (window.pywebview && window.pywebview.api && window.pywebview.api.close) {
                window.pywebview.api.close();
            } else {
                window.close();
            }
        },

        windowReady: () => {
            console.log('[API Adapter] Window ready signal dispatched.');
        }
    };

    console.log('[API Adapter] window.jarvis successfully initialized for Web / PyWebView environment.');
})();
