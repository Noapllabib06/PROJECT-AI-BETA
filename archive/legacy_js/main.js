// src/main.js
// Electron Main Process - Window Management, IPC, Tool Orchestrator
require('dotenv').config();
const { app, BrowserWindow, ipcMain, session, shell, Menu, MenuItem, clipboard } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
//const { spawn } = require('child_process');
const agent = require('./engine/agent');
const conversationManager = require('./engine/conversation_manager');
const configManager = require('./engine/config_manager');
const axios = require('axios');
const { open_web_tool, scrape_web_tool, search_web_tool } = require('./tools/web_tools');
const { yt_search_tool, play_youtube_music, play_youtube_video, getVideoInfo } = require('./tools/yt_tools');

// Suppress Chromium audio stream errors
process.env.ELECTRON_NO_ATTACHED_CONSOLE = '1';

// Add Electron command line switches to suppress audio stream errors
if (process.defaultApp || /[\\/]electron/.test(process.execPath)) {
    app.commandLine.appendSwitch('disable-features', 'AudioServiceOutOfProcess');
}

let mainWindow;
let pythonServerProcess = null;

function startPythonServer() {

}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        minWidth: 900,
        minHeight: 600,
        frame: false,
        transparent: true,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
            webviewTag: true,
            permissions: ['microphone', 'audio-capture', 'media'],
            audioCapture: true,
        },
    });

    mainWindow.loadFile(path.join(__dirname, 'gui', 'index.html'));

    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        shell.openExternal(url);
        return { action: 'deny' };
    });

    // Native context menu (Right-click: Salin, Tempel, Pilih Semua)
    mainWindow.webContents.on('context-menu', (event, params) => {
        const menu = new Menu();
        if (params.selectionText && params.selectionText.trim().length > 0) {
            menu.append(new MenuItem({ label: 'Salin (Copy)', role: 'copy' }));
            menu.append(new MenuItem({ type: 'separator' }));
        }
        if (params.isEditable) {
            menu.append(new MenuItem({ label: 'Tempel (Paste)', role: 'paste' }));
            menu.append(new MenuItem({ label: 'Potong (Cut)', role: 'cut' }));
            menu.append(new MenuItem({ type: 'separator' }));
        }
        menu.append(new MenuItem({ label: 'Pilih Semua (Select All)', role: 'selectAll' }));
        menu.popup({ window: mainWindow });
    });
}

// ============ AI AGENT ORCHESTRATOR ============

async function processUserCommand(userInput) {
    console.log(`\n[USER]: ${userInput}`);

    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('status-update', { text: 'Memproses...', state: 'thinking' });
    }

    const response = await agent.processInput(userInput);

    console.log(`[JARVIS]: ${response}`);

    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('status-update', { text: 'Menunggu perintah...', state: 'idle' });
    }

    return response;
}

// ============ IPC HANDLERS ============

ipcMain.handle('process-command', async (event, userInput) => {
    try {
        const response = await processUserCommand(userInput);
        return { success: true, response };
    } catch (error) {
        console.error("IPC Error:", error);
        return { success: false, response: "❌ Maaf, terjadi kesalahan internal." };
    }
});

// Handler streaming: untuk chat AI real-time
// UPDATE: sekarang juga forward event trace ('trace-update') ke renderer,
// dipakai untuk panel Thinking Process. conversationId TIDAK dikirim di sini
// secara eksplisit — renderer sudah memanggil IPC 'switch-conversation'
// terpisah sebelum mengirim pesan, jadi agent.activeConversationId sudah
// ter-set duluan (lihat agent.js -> processInputStream).
ipcMain.handle('process-command-stream', async (event, userInput) => {
    try {
        const onToken = (token) => {
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('stream-token', token);
            }
        };
        const onTrace = (traceStep) => {
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('trace-update', traceStep);
            }
        };

        const stream = await agent.processInputStream(userInput, onToken, null, onTrace);
        return { success: true, response: stream };
    } catch (error) {
        console.error("Stream Error:", error);
        return { success: false, response: "❌ Maaf, terjadi kesalahan saat streaming." };
    }
});

// ============ CONVERSATION / CHAT HISTORY IPC HANDLERS (BARU) ============

ipcMain.handle('list-conversations', async () => {
    try {
        return conversationManager.listConversations();
    } catch (error) {
        console.error("List Conversations Error:", error);
        return [];
    }
});

ipcMain.handle('create-conversation', async () => {
    try {
        const conv = conversationManager.createConversation();
        agent.switchConversation(conv.id);
        return conv;
    } catch (error) {
        console.error("Create Conversation Error:", error);
        return null;
    }
});

ipcMain.handle('load-conversation', async (event, conversationId) => {
    try {
        return conversationManager.loadConversation(conversationId);
    } catch (error) {
        console.error("Load Conversation Error:", error);
        return null;
    }
});

ipcMain.handle('delete-conversation', async (event, conversationId) => {
    try {
        return conversationManager.deleteConversation(conversationId);
    } catch (error) {
        console.error("Delete Conversation Error:", error);
        return false;
    }
});

ipcMain.handle('switch-conversation', async (event, conversationId) => {
    try {
        agent.switchConversation(conversationId);
        return { success: true };
    } catch (error) {
        console.error("Switch Conversation Error:", error);
        return { success: false };
    }
});

// ============ SETTINGS IPC HANDLERS ============

ipcMain.handle('get-settings', async () => {
    return configManager.getAll();
});

ipcMain.handle('save-settings', async (event, settings) => {
    try {
        if (settings.activeModel) {
            configManager.set('activeModel', settings.activeModel);
            await agent.reloadModel(settings.activeModel);
        }
        return { success: true };
    } catch (error) {
        console.error("Save Settings Error:", error);
        return { success: false, error: error.message };
    }
});

ipcMain.handle('get-ollama-models', async () => {
    try {
        const response = await axios.get('http://127.0.0.1:11434/api/tags');
        return response.data.models || [];
    } catch (error) {
        console.error("Failed to fetch Ollama models:", error.message);
        return [];
    }
});

// ============ FILE PREVIEW / CONFIRM-SAVE (BARU) ============
// Dipanggil dari Code Preview pane setelah user klik "Simpan" pada draft
// file yang dibuat lewat create_file. Ini SATU-SATUNYA titik yang benar-benar
// menulis file ke disk untuk alur create_file — tool create_file sendiri
// (lihat agent.js) sekarang cuma menghasilkan draft, tidak menulis apa pun.
ipcMain.handle('confirm-save-file', async (event, { filename, content }) => {
    try {
        if (!filename || typeof filename !== 'string') {
            return { success: false, error: 'Nama file tidak valid.' };
        }
        // Sanitasi dasar nama file (samakan prinsipnya dengan create_file asli)
        const safeName = filename.replace(/[<>:"/\\|?*\x00-\x1F]/g, '_').trim();
        if (!safeName) {
            return { success: false, error: 'Nama file kosong setelah sanitasi.' };
        }

        const desktopPath = path.join(os.homedir(), 'Desktop');
        if (!fs.existsSync(desktopPath)) {
            fs.mkdirSync(desktopPath, { recursive: true });
        }
        const filePath = path.join(desktopPath, safeName);

        fs.writeFileSync(filePath, content ?? '', 'utf8');
        const stats = fs.statSync(filePath);
        const sizeKB = (stats.size / 1024).toFixed(2);

        console.log(`[Main] File dikonfirmasi & disimpan: ${filePath} (${sizeKB} KB)`);
        return { success: true, filePath, sizeKB };
    } catch (error) {
        console.error("Confirm Save File Error:", error);
        return { success: false, error: error.message };
    }
});

ipcMain.handle('copy-to-clipboard', async (event, text) => {
    try {
        clipboard.writeText(text || '');
        return { success: true };
    } catch (err) {
        return { success: false, error: err.message };
    }
});

// ============ TOOL IPC HANDLERS ============

ipcMain.handle('tool-open-web', async (event, url) => {
    return await open_web_tool(url);
});

ipcMain.handle('tool-scrape-web', async (event, url) => {
    return await scrape_web_tool(url);
});

ipcMain.handle('tool-search-web', async (event, query) => {
    return await search_web_tool(query);
});

ipcMain.handle('tool-search-yt', async (event, query) => {
    return await yt_search_tool(query);
});

ipcMain.handle('tool-play-music', async (event, query) => {
    agent.updateState(`Memutar musik: "${query}"`);
    return await play_youtube_music(query);
});

ipcMain.handle('tool-play-video', async (event, query) => {
    agent.updateState(`Memutar video: "${query}"`);
    return await play_youtube_video(query);
});

ipcMain.handle('tool-yt-info', async (event, url) => {
    return await getVideoInfo(url);
});

ipcMain.handle('get-agent-state', async () => {
    return agent.currentState;
});

ipcMain.handle('update-agent-state', async (event, newState) => {
    agent.updateState(newState);
    return { success: true };
});

// ============ WINDOW CONTROLS ============

ipcMain.on('window-minimize', () => {
    if (mainWindow) mainWindow.minimize();
});

ipcMain.on('window-maximize', () => {
    if (mainWindow) {
        mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize();
    }
});

ipcMain.on('window-close', () => {
    if (mainWindow) mainWindow.close();
});

ipcMain.on('window-ready', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('status-update', {
            text: agent.currentState,
            state: 'idle'
        });
    }
});

// ============ APP LIFECYCLE ============

app.whenReady().then(() => {
    session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
        if (permission === 'media' || permission === 'microphone' || permission === 'audio-capture') {
            console.log('[Main] Microphone permission granted');
            callback(true);
            return;
        }
        callback(false);
    });

    session.defaultSession.setDevicePermissionHandler((details, callback) => {
        if (details.deviceType === 'audioinput') {
            console.log('[Main] Audio input device permission granted');
            callback(true);
            return;
        }
        callback(false);
    });

    startPythonServer();
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
    if (pythonServerProcess) {
        console.log('[Main] Mematikan Python Server...');
        pythonServerProcess.kill();
    }
});

module.exports = { processUserCommand };