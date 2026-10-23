// src/preload.js
// Jembatan aman antara Frontend (renderer) dan Backend (main process)
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('jarvis', {
    // ==================== AI AGENT ====================
    
    /** Kirim perintah dan dapatkan response (non-streaming) */
    sendCommand: (input) => ipcRenderer.invoke('process-command', input),
    
    /** Kirim perintah dengan streaming response real-time */
    sendCommandStream: (input) => ipcRenderer.invoke('process-command-stream', input),
    
    /** Listener untuk token streaming dari AI */
    onStreamToken: (callback) => {
        ipcRenderer.removeAllListeners('stream-token');
        ipcRenderer.on('stream-token', (event, token) => callback(token));
    },
    
    /** Listener untuk status update */
    onStatusUpdate: (callback) => {
        ipcRenderer.removeAllListeners('status-update');
        ipcRenderer.on('status-update', (event, data) => callback(data));
    },

    // ==================== THINKING PROCESS (BARU) ====================

    /**
     * Listener untuk event trace/thinking process.
     * Setiap event berbentuk: { type, timestamp, ...detail }
     * type bisa: 'routing', 'tool_call', 'tool_result', 'retry',
     * 'stale_knowledge_override', 'synthesis_start', 'chat_response',
     * 'done', 'error', 'final_fallback'
     */
    onTraceUpdate: (callback) => {
        ipcRenderer.removeAllListeners('trace-update');
        ipcRenderer.on('trace-update', (event, traceStep) => callback(traceStep));
    },
    
    // ==================== WEB TOOLS ====================
    
    /** Buka URL di browser default */
    openWeb: (url) => ipcRenderer.invoke('tool-open-web', url),
    
    /** Baca/scrape konten dari halaman web */
    scrapeWeb: (url) => ipcRenderer.invoke('tool-scrape-web', url),
    
    /** Cari informasi di web (Google Search) */
    searchWeb: (query) => ipcRenderer.invoke('tool-search-web', query),
    
    // ==================== YOUTUBE TOOLS ====================
    
    /** Cari konten di YouTube */
    searchYouTube: (query) => ipcRenderer.invoke('tool-search-yt', query),
    
    /** Putar lagu dari YouTube Music */
    playMusic: (query) => ipcRenderer.invoke('tool-play-music', query),
    
    /** Putar video dari YouTube */
    playVideo: (query) => ipcRenderer.invoke('tool-play-video', query),
    
    /** Dapatkan info video YouTube */
    getYouTubeInfo: (url) => ipcRenderer.invoke('tool-yt-info', url),
    
    // ==================== AGENT STATE ====================
    
    /** Dapatkan status agent saat ini */
    getAgentState: () => ipcRenderer.invoke('get-agent-state'),
    
    /** Update status agent */
    updateAgentState: (newState) => ipcRenderer.invoke('update-agent-state', newState),

    // ==================== CHAT HISTORY / CONVERSATIONS (BARU) ====================

    /** Ambil daftar semua percakapan (metadata ringan: id, title, timestamp) */
    listConversations: () => ipcRenderer.invoke('list-conversations'),

    /** Buat percakapan baru, return objek percakapan (kosong) */
    createConversation: () => ipcRenderer.invoke('create-conversation'),

    /** Load satu percakapan penuh (termasuk semua messages) berdasarkan id */
    loadConversation: (conversationId) => ipcRenderer.invoke('load-conversation', conversationId),

    /** Hapus percakapan berdasarkan id */
    deleteConversation: (conversationId) => ipcRenderer.invoke('delete-conversation', conversationId),

    /** Beralih ke percakapan tertentu sebagai percakapan aktif di agent */
    switchConversation: (conversationId) => ipcRenderer.invoke('switch-conversation', conversationId),

    // ==================== FILE PREVIEW / CONFIRM-SAVE (BARU) ====================

    /** Konfirmasi simpan draft file dari Code Preview pane ke Desktop */
    confirmSaveFile: (payload) => ipcRenderer.invoke('confirm-save-file', payload),
    
    // ==================== SETTINGS (BARU) ====================
    getSettings: () => ipcRenderer.invoke('get-settings'),
    saveSettings: (settings) => ipcRenderer.invoke('save-settings', settings),
    getOllamaModels: () => ipcRenderer.invoke('get-ollama-models'),
    
    // ==================== CLIPBOARD ====================
    copyToClipboard: (text) => ipcRenderer.invoke('copy-to-clipboard', text),

    // ==================== WINDOW CONTROLS ====================
    
    minimizeWindow: () => ipcRenderer.send('window-minimize'),
    maximizeWindow: () => ipcRenderer.send('window-maximize'),
    closeWindow: () => ipcRenderer.send('window-close'),
    
    /** Tandai bahwa window sudah siap */
    windowReady: () => ipcRenderer.send('window-ready'),
});