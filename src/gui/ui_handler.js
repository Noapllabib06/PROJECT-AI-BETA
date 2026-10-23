/**
 * src/gui/ui_handler.js
 * Menghubungkan semua interaksi UI ke API window.jarvis (lewat preload.js).
 *
 * Mendukung fitur:
 * - Chat History: sidebar percakapan (list/buat/pindah/hapus) — sementara disabled
 * - Thinking Process: panel collapsible (<details>) berisi trace tiap balasan AI
 * - Code Preview: pane kanan untuk file draft & view
 * - Code Cards: blok kode di chat jadi clickable card
 * - Response Tags: badge tool yang digunakan di bawah pesan AI
 */

// ===================== ELEMENT REFERENCES =====================
const chatMessages = document.getElementById('chatMessages');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const voiceBtn = document.getElementById('voiceBtn');
const attachBtn = document.getElementById('attachBtn');
const imageInput = document.getElementById('imageInput');
const imagePreviewContainer = document.getElementById('imagePreviewContainer');
const imagePreview = document.getElementById('imagePreview');
const removeImageBtn = document.getElementById('removeImageBtn');
const statusText = document.getElementById('statusText');

const newChatBtn = document.getElementById('newChatBtn');
const conversationList = document.getElementById('conversationList');
const conversationEmptyState = document.getElementById('conversationEmptyState');

const minimizeBtn = document.getElementById('minimizeBtn');
const maximizeBtn = document.getElementById('maximizeBtn');
const closeBtn = document.getElementById('closeBtn');

const codePreview = document.getElementById('codePreview');
const codeContentInner = document.getElementById('codeContentInner');
const codeFileName = document.getElementById('codeFileName');
const toggleCodeBtn = document.getElementById('toggleCodeBtn');
const closeCodeBtn = document.getElementById('closeCodeBtn');

const aiMessageTemplate = document.getElementById('aiMessageTemplate');
const userMessageTemplate = document.getElementById('userMessageTemplate');
const conversationItemTemplate = document.getElementById('conversationItemTemplate');

const activeModelLabel = document.getElementById('activeModelLabel');
const settingsBtn = document.getElementById('settingsBtn');
const settingsModal = document.getElementById('settingsModal');
const closeSettingsBtn = document.getElementById('closeSettingsBtn');
const cancelSettingsBtn = document.getElementById('cancelSettingsBtn');
const saveSettingsBtn = document.getElementById('saveSettingsBtn');
const modelSelect = document.getElementById('modelSelect');
const refreshModelsBtn = document.getElementById('refreshModelsBtn');
const tempSlider = document.getElementById('tempSlider');
const tempValueLabel = document.getElementById('tempValueLabel');

// ===================== STATE =====================
const TOOL_LABELS = {
    search_web: 'Web', read_webpage: 'Web', open_website: 'Web',
    research_and_summarize: 'Riset',
    check_email: 'Email',
    play_music: 'Musik', play_video: 'Video',
    search_youtube: 'YouTube', open_youtube_channel: 'YouTube',
    create_file: 'File', read_file: 'File', ingest_codebase: 'Kode',
    open_app: 'Aplikasi', control_volume: 'Sistem',
    take_screenshot: 'Screenshot', analyze_screen: 'Vision',
    save_memory: 'Memori', search_memory: 'Memori',
    save_credential: 'Kredensial', list_credentials: 'Kredensial', delete_credential: 'Kredensial',
    get_jarvis_capabilities: 'Info Sistem',
    process_second_brain_pipeline: 'Second Brain',
    ingest_with_markitdown: 'MarkItDown',
    search_second_brain: 'Second Brain',
    read_github_repo: 'GitHub',
    read_github_file: 'GitHub',
    clone_and_ingest_github: 'GitHub'
};

const TOOL_ICONS = {
    'Web': 'language', 'Riset': 'science', 'Email': 'email',
    'Musik': 'music_note', 'Video': 'videocam', 'YouTube': 'smart_display',
    'File': 'description', 'Kode': 'code', 'Aplikasi': 'apps',
    'Sistem': 'settings', 'Screenshot': 'screenshot_monitor',
    'Vision': 'visibility', 'Memori': 'psychology',
    'Kredensial': 'key', 'Info Sistem': 'info',
    'Second Brain': 'neurology', 'MarkItDown': 'edit_note', 'GitHub': 'code_blocks'
};

let activeConversationId = null;
let pendingImageBase64 = null;
let isProcessing = false;

// ===================== WINDOW CONTROLS (Electron frameless) =====================
minimizeBtn?.addEventListener('click', () => window.jarvis.minimizeWindow());
maximizeBtn?.addEventListener('click', () => window.jarvis.maximizeWindow());
closeBtn?.addEventListener('click', () => window.jarvis.closeWindow());

// ===================== CODE PREVIEW PANE TOGGLE =====================
toggleCodeBtn?.addEventListener('click', () => {
    codePreview.classList.toggle('hidden');
    codePreview.classList.toggle('flex');
});

closeCodeBtn?.addEventListener('click', () => {
    codePreview.classList.add('hidden');
    codePreview.classList.remove('flex');
});

// ===================== SETTINGS MODAL =====================
async function loadSettings() {
    const settings = await window.jarvis.getSettings();
    if (settings) {
        if (settings.activeModel) {
            activeModelLabel.textContent = `${settings.activeModel} · Local`;
            modelSelect.value = settings.activeModel;
        }
        if (settings.temperature !== undefined && tempSlider) {
            tempSlider.value = settings.temperature;
            if (tempValueLabel) {
                tempValueLabel.textContent = Number(settings.temperature).toFixed(2);
            }
        }
    }
}

async function fetchOllamaModels() {
    modelSelect.innerHTML = '<option value="">Loading models...</option>';
    modelSelect.disabled = true;
    try {
        const models = await window.jarvis.getOllamaModels();
        modelSelect.innerHTML = '';
        if (models.length === 0) {
            modelSelect.innerHTML = '<option value="">No models found in Ollama</option>';
        } else {
            models.forEach(model => {
                const opt = document.createElement('option');
                opt.value = model.name;
                opt.textContent = model.name;
                modelSelect.appendChild(opt);
            });
        }
        await loadSettings(); // Re-select active model and temperature after populating
    } catch (e) {
        modelSelect.innerHTML = '<option value="">Error fetching models</option>';
    } finally {
        modelSelect.disabled = false;
    }
}

tempSlider?.addEventListener('input', () => {
    if (tempValueLabel) {
        tempValueLabel.textContent = Number(tempSlider.value).toFixed(2);
    }
});

settingsBtn?.addEventListener('click', () => {
    settingsModal.classList.remove('hidden');
    fetchOllamaModels();
});

const closeSettings = () => settingsModal.classList.add('hidden');
closeSettingsBtn?.addEventListener('click', closeSettings);
cancelSettingsBtn?.addEventListener('click', closeSettings);

refreshModelsBtn?.addEventListener('click', fetchOllamaModels);

saveSettingsBtn?.addEventListener('click', async () => {
    const selectedModel = modelSelect.value;
    const tempVal = tempSlider ? parseFloat(tempSlider.value) : undefined;
    const payload = {};
    if (selectedModel) {
        payload.activeModel = selectedModel;
        activeModelLabel.textContent = `${selectedModel} · Local`;
    }
    if (tempVal !== undefined && !isNaN(tempVal)) {
        payload.temperature = tempVal;
    }
    await window.jarvis.saveSettings(payload);
    closeSettings();
});

// Initial Load
document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
});

// ===================== TEXTAREA AUTO-RESIZE =====================
userInput?.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = this.scrollHeight + 'px';
    if (this.value === '') this.style.height = 'auto';
});

// ===================== THINKING PROCESS: LABEL MAPPING =====================
/**
 * Ubah 1 trace step dari agent.js (emitTrace) jadi baris teks yang
 * enak dibaca manusia di panel Thinking Process.
 */
function formatTraceStep(step) {
    if (!step) return 'Memproses langkah...';
    if (typeof step === 'string') return step;
    const type = step.type || step.step || 'info';
    switch (type) {
        case 'routing': {
            const tools = (step.toolsConsidered || (step.details && step.details.tools) || []).join(', ') || '(tidak ada, mode chat biasa)';
            const cats = step.categoryScores ? Object.keys(step.categoryScores).join(', ') : (step.message || '-');
            return `🧭 Analisis Rute: ${cats} → Tool dipertimbangkan: ${tools}`;
        }
        case 'routing_completed': {
            const tools = (step.tools || (step.details && step.details.tools) || []).join(', ') || '(chat biasa)';
            return `🧭 Kandidat tool terpilih: ${tools}`;
        }
        case 'memory_retrieval':
            return `🧠 Mengakses memori dan basis pengetahuan RAG...`;
        case 'planning':
            return `📋 Perencanaan tugas: ${step.message || step.content || 'Dekomposisi langkah'}`;
        case 'tool_call': {
            const list = (step.tools || []).map(t => `${t.tool}("${t.query || ''}")`).join(', ');
            return `⚙️ Menjalankan: ${list}`;
        }
        case 'tool_execution':
            return `⚙️ ${step.message || 'Mengeksekusi tool...'}`;
        case 'tool_decision':
            return `🎯 Keputusan tool: ${step.message || step.content}`;
        case 'reasoning':
        case 'llm_reasoning': {
            const txt = step.content || step.message || '';
            return `🧠 Memikirkan aksi:\n<div class="mt-1 p-2 bg-black/5 rounded text-xs font-code-snippet">${escapeHtml(txt).replace(/\n/g, '<br>')}</div>`;
        }
        case 'tool_result': {
            return (step.results || []).map(r =>
                r.success ? `✅ ${r.tool} berhasil` : `❌ ${r.tool} gagal: ${r.error || 'unknown error'}`
            ).join('\n');
        }
        case 'tool_warning':
            return `⚠️ ${step.message || 'Peringatan eksekusi tool'}`;
        case 'retry':
            return `🔁 Percobaan ulang #${step.attempt || 1} — alasan: ${step.reason || step.message || 'koreksi otomatis'}`;
        case 'self_correction':
            return `🔁 Koreksi mandiri: ${step.message || 'Memperbaiki format respons...'}`;
        case 'supervision':
            return `🛡️ Supervisi: Memvalidasi kualitas jawaban...`;
        case 'completed':
            return `✔️ Proses selesai dan respons tervalidasi.`;
        case 'stale_knowledge_override':
            return `⏱️ Info berpotensi usang, dialihkan ke pencarian web`;
        case 'synthesis_start':
        case 'synthesis':
            return `📝 Merangkum hasil jadi jawaban akhir...`;
        case 'done':
            return `✔️ Selesai.`;
        case 'chat_response':
            return `💬 Merespons langsung tanpa tool.`;
        case 'final_fallback':
            return `⚠️ Gagal semua percobaan — kirim fallback.`;
        case 'error':
            return `❌ Error: ${step.message || step.content || 'Tidak diketahui'}`;
        default:
            return step.message || step.content || (type && type !== 'undefined' ? `• ${type}` : 'Memproses langkah...');
    }
}

function traceStepLabel(step) {
    if (!step) return 'Memproses...';
    if (typeof step === 'string') return step;
    const type = step.type || step.step || 'info';
    switch (type) {
        case 'routing':
        case 'routing_completed': return 'Menganalisis permintaan...';
        case 'memory_retrieval': return 'Mencari memori...';
        case 'planning': return 'Menyusun rencana...';
        case 'reasoning':
        case 'llm_reasoning': return 'Memutuskan langkah...';
        case 'tool_call':
        case 'tool_execution': return 'Menjalankan tool...';
        case 'tool_decision': return 'Memilih tindakan...';
        case 'tool_result': return 'Memproses hasil tool...';
        case 'retry':
        case 'self_correction': return `Mencoba ulang (percobaan ${step.attempt || 1})...`;
        case 'supervision': return 'Memvalidasi output...';
        case 'completed':
        case 'done': return 'Proses berpikir selesai';
        case 'synthesis_start':
        case 'synthesis': return 'Merangkum hasil...';
        case 'chat_response': return 'Menjawab langsung';
        case 'final_fallback': return 'Gagal setelah beberapa percobaan';
        case 'error': return 'Terjadi kesalahan';
        default: return step.message || 'Memproses...';
    }
}

// ===================== CODE PREVIEW PANE (File Draft / View) =====================

const codeTabBar = document.getElementById('codeTabBar');
const codePlaceholder = document.getElementById('codePlaceholder');

const openTabs = new Map();
let activeTabId = null;

function switchTab(id) {
    if (!openTabs.has(id)) return;
    
    activeTabId = id;
    const tabData = openTabs.get(id);
    
    // Update UI for all tabs
    for (const [tabId, data] of openTabs.entries()) {
        if (tabId === id) {
            data.contentEl.classList.remove('hidden');
            data.tabBtnEl.classList.add('bg-surface', 'border-t-2', 'border-t-primary', 'text-primary');
            data.tabBtnEl.classList.remove('bg-surface-container', 'text-secondary', 'hover:bg-surface-container-high');
        } else {
            data.contentEl.classList.add('hidden');
            data.tabBtnEl.classList.remove('bg-surface', 'border-t-2', 'border-t-primary', 'text-primary');
            data.tabBtnEl.classList.add('bg-surface-container', 'text-secondary', 'hover:bg-surface-container-high');
        }
    }
    
    codeFileName.textContent = tabData.title;
    if (codePlaceholder) codePlaceholder.classList.add('hidden');
}

function closeTab(id, event) {
    if (event) {
        event.stopPropagation(); // prevent switching to this tab
    }
    
    const tabData = openTabs.get(id);
    if (!tabData) return;
    
    // Remove from DOM
    tabData.contentEl.remove();
    tabData.tabBtnEl.remove();
    
    openTabs.delete(id);
    
    if (openTabs.size === 0) {
        clearCodePreview();
    } else if (activeTabId === id) {
        // Switch to the last opened tab
        const lastTabId = Array.from(openTabs.keys()).pop();
        switchTab(lastTabId);
    }
}

function createOrUpdateTab(id, title, contentEl, type) {
    expandCodeSidebar();
    codeTabBar.classList.remove('hidden');
    
    if (openTabs.has(id)) {
        // Tab exists, just replace content and switch to it
        const tabData = openTabs.get(id);
        tabData.contentEl.replaceWith(contentEl);
        tabData.contentEl = contentEl;
        tabData.title = title;
        tabData.tabBtnEl.querySelector('.tab-title').textContent = title;
        switchTab(id);
        return;
    }
    
    // Create new tab button
    const tabBtn = document.createElement('button');
    tabBtn.className = 'flex items-center gap-2 px-3 py-1.5 min-w-[120px] max-w-[200px] rounded-t-lg border border-b-0 border-border-subtle text-sm font-medium transition-colors shrink-0 outline-none';
    
    let iconName = 'description';
    if (type === 'youtube-music') iconName = 'music_note';
    else if (type === 'youtube-video') iconName = 'smart_display';
    else if (type === 'image') iconName = 'image';
    else if (type === 'web') iconName = 'public';
    
    tabBtn.innerHTML = `
        <span class="material-symbols-outlined text-[16px] shrink-0">${iconName}</span>
        <span class="tab-title truncate flex-1 text-left">${escapeHtml(title)}</span>
        <span class="close-tab-btn material-symbols-outlined text-[14px] shrink-0 hover:text-error rounded hover:bg-black/10 p-0.5">close</span>
    `;
    
    tabBtn.addEventListener('click', () => switchTab(id));
    tabBtn.querySelector('.close-tab-btn').addEventListener('click', (e) => closeTab(id, e));
    
    codeTabBar.appendChild(tabBtn);
    codeContentInner.appendChild(contentEl);
    
    openTabs.set(id, { id, title, type, contentEl, tabBtnEl: tabBtn });
    switchTab(id);
}

function expandCodeSidebar() {
    codePreview.classList.remove('hidden');
    codePreview.classList.add('flex');
}

/**
 * Render draft file (dari create_file yang di-intercept) — bisa diedit,
 * ada tombol Konfirmasi (tulis ke disk via confirmSaveFile) dan Batalkan.
 */
function renderFileDraft(filename, content) {
    if (filename.includes('snippet.image') || filename.endsWith('.png') || filename.endsWith('.jpg')) {
        try {
            const data = JSON.parse(content);
            const container = document.createElement('div');
            container.className = 'absolute inset-4 flex flex-col gap-4 overflow-y-auto hidden';
            
            if (data.path || data.image) {
                const img = document.createElement('img');
                img.src = data.path ? `file:///${data.path.replace(/\\/g, '/')}` : data.image;
                img.className = 'max-w-full rounded-lg border border-border-subtle shadow-sm object-contain';
                container.appendChild(img);
            }
            
            if (data.explanation) {
                const text = document.createElement('div');
                text.className = 'text-on-surface font-body-md whitespace-pre-wrap';
                text.textContent = data.explanation;
                container.appendChild(text);
            }
            
            const tabId = `image-${Date.now()}`;
            createOrUpdateTab(tabId, filename, container, 'image');
            return;
        } catch (e) {
            console.error("Gagal parse image snippet JSON", e);
        }
    }

    if (filename.includes('snippet.youtube')) {
        try {
            const data = JSON.parse(content);
            const container = document.createElement('div');
            container.className = 'absolute inset-0 flex flex-col hidden bg-[#0f0f0f]';
            
            const isMusic = data.type === 'music';
            const tabTitle = isMusic 
                ? (data.title ? `🎵 ${data.title}` : 'YouTube Music') 
                : (data.title ? `▶️ ${data.title}` : 'YouTube Video');
            const tabType = isMusic ? 'youtube-music' : 'youtube-video';
            const tabId = `youtube-${data.videoId || Date.now()}`;
            
            const directUrl = data.url || (isMusic 
                ? (data.videoId && data.videoId !== 'search' 
                    ? `https://music.youtube.com/watch?v=${data.videoId}` 
                    : `https://music.youtube.com/search?q=${encodeURIComponent(data.title || '')}`)
                : (data.videoId && data.videoId !== 'search' 
                    ? `https://www.youtube.com/watch?v=${data.videoId}` 
                    : `https://www.youtube.com/results?search_query=${encodeURIComponent(data.title || '')}`));
            
            // Header bar with external app link
            const header = document.createElement('div');
            header.className = 'flex items-center justify-between px-4 py-2.5 bg-[#181818] border-b border-[#2e2e2e] text-xs text-[#f1f1f1] select-none';
            header.innerHTML = `
                <div class="flex items-center gap-2 truncate pr-2">
                    <span class="material-symbols-outlined text-red-500 text-[18px] shrink-0">${isMusic ? 'music_note' : 'smart_display'}</span>
                    <span class="font-medium truncate">${escapeHtml(data.title || (isMusic ? 'YouTube Music Player' : 'YouTube Video Player'))}</span>
                </div>
                <a href="${directUrl}" target="_blank" rel="noopener noreferrer" class="px-2.5 py-1 bg-[#cc0000] hover:bg-red-700 text-white rounded font-medium flex items-center gap-1.5 transition-colors shrink-0 shadow-sm">
                    <span>${isMusic ? 'Buka YT Music' : 'Buka YouTube'}</span>
                    <span class="material-symbols-outlined text-[13px]">open_in_new</span>
                </a>
            `;
            container.appendChild(header);

            if (data.videoId && data.videoId !== 'search') {
                const iframe = document.createElement('iframe');
                // Standard responsive YouTube embed with autoplay and API support
                iframe.src = `https://www.youtube-nocookie.com/embed/${data.videoId}?autoplay=1&enablejsapi=1`;
                iframe.className = 'flex-1 w-full border-0 bg-black';
                iframe.setAttribute('allow', 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share');
                iframe.setAttribute('allowfullscreen', 'true');
                container.appendChild(iframe);
            } else {
                const emptyState = document.createElement('div');
                emptyState.className = 'flex-1 flex flex-col items-center justify-center p-6 text-center text-gray-400 gap-3';
                emptyState.innerHTML = `
                    <span class="material-symbols-outlined text-[48px] text-red-500">music_note</span>
                    <p class="text-sm font-medium text-white">${escapeHtml(data.title || 'Pencarian Musik')}</p>
                    <p class="text-xs text-gray-400">Membuka YouTube Music di browser...</p>
                    <a href="${directUrl}" target="_blank" rel="noopener noreferrer" class="mt-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors">
                        <span class="material-symbols-outlined text-[16px]">open_in_new</span>
                        <span>Buka di YouTube Music</span>
                    </a>
                `;
                container.appendChild(emptyState);
            }
            
            createOrUpdateTab(tabId, tabTitle, container, tabType);
            return;
        } catch (e) {
            console.error("Gagal parse youtube snippet JSON", e);
        }
    }

    if (filename.includes('snippet.web')) {
        try {
            const data = JSON.parse(content);
            const container = document.createElement('div');
            container.className = 'absolute inset-0 flex flex-col hidden bg-white';
            
            let tabTitle = data.title || 'Web Page';
            tabTitle = tabTitle.charAt(0).toUpperCase() + tabTitle.slice(1);
            const tabId = `web-${Date.now()}`;
            
            const header = document.createElement('div');
            header.className = 'flex items-center justify-between px-4 py-2 bg-surface-container border-b border-border-subtle text-xs text-on-surface';
            header.innerHTML = `
                <span class="font-medium truncate flex-1">${escapeHtml(data.url || '')}</span>
                <a href="${data.url}" target="_blank" rel="noopener noreferrer" class="ml-2 text-primary hover:underline flex items-center gap-1 font-semibold">
                    <span>Buka Tab Baru</span>
                    <span class="material-symbols-outlined text-[14px]">open_in_new</span>
                </a>
            `;
            container.appendChild(header);

            const iframe = document.createElement('iframe');
            iframe.src = data.url;
            iframe.className = 'flex-1 w-full border-0 bg-white';
            iframe.setAttribute('allow', 'fullscreen; clipboard-read; clipboard-write');
            container.appendChild(iframe);

            createOrUpdateTab(tabId, tabTitle, container, 'web');
            return;
        } catch (e) {
            console.error("Gagal parse web snippet JSON", e);
        }
    }
    
    const container = document.createElement('div');
    container.className = 'absolute inset-4 flex flex-col gap-3 hidden';

    const textarea = document.createElement('textarea');
    textarea.className = 'code-editor flex-1 w-full p-3 font-code-snippet text-sm bg-surface-gray border border-border-subtle rounded-lg focus:outline-none focus:ring-1 focus:ring-primary/50 text-on-surface resize-none';
    textarea.value = content;
    container.appendChild(textarea);

    const actionsRow = document.createElement('div');
    actionsRow.className = 'flex items-center justify-between w-full pb-2';

    const statusMsg = document.createElement('div');
    statusMsg.className = 'text-sm font-medium';

    const actions = document.createElement('div');
    actions.className = 'flex gap-2 justify-end';

    const saveBtn = document.createElement('button');
    saveBtn.className = 'px-4 py-2 bg-primary text-white rounded-lg text-sm font-semibold hover:bg-primary-hover transition-colors';
    saveBtn.textContent = 'Konfirmasi';

    const discardBtn = document.createElement('button');
    discardBtn.className = 'px-4 py-2 bg-surface-container-high text-on-surface rounded-lg text-sm font-medium hover:bg-surface-dim transition-colors';
    discardBtn.textContent = 'Batalkan';

    actions.appendChild(discardBtn);
    actions.appendChild(saveBtn);
    
    actionsRow.appendChild(statusMsg);
    actionsRow.appendChild(actions);

    container.appendChild(actionsRow);

    const tabId = `file-${filename}`;

    saveBtn.addEventListener('click', async () => {
        saveBtn.disabled = true;
        saveBtn.textContent = 'Menyimpan...';
        const result = await window.jarvis.confirmSaveFile({
            filename,
            content: textarea.value
        });

        if (result?.success) {
            statusMsg.textContent = `✅ Tersimpan di ${result.filePath}`;
            statusMsg.className = 'text-sm text-green-600 font-medium';
            saveBtn.textContent = 'Tersimpan';
            setTimeout(() => {
                saveBtn.disabled = false;
                saveBtn.textContent = 'Konfirmasi';
            }, 2000);
        } else {
            statusMsg.textContent = `❌ Gagal menyimpan: ${result?.error || 'unknown error'}`;
            statusMsg.className = 'text-sm text-error font-medium';
            saveBtn.disabled = false;
            saveBtn.textContent = 'Konfirmasi';
        }
    });

    discardBtn.addEventListener('click', () => {
        closeTab(tabId);
    });
    
    createOrUpdateTab(tabId, filename, container, 'code');
}

/**
 * Render isi file hasil read_file — sekarang juga editable
 * dan memiliki opsi untuk Konfirmasi (simpan) atau Batalkan.
 */
function renderFileView(filename, content) {
    renderFileDraft(filename, content);
}

function clearCodePreview() {
    codeFileName.textContent = 'Preview';
    if (codePlaceholder) codePlaceholder.classList.remove('hidden');
    codeTabBar.classList.add('hidden');
    codePreview.classList.add('hidden');
    codePreview.classList.remove('flex');
    activeTabId = null;
}

// ===================== MARKDOWN RENDERING (RINGAN) =====================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

let codeSnippetCounter = 0;

function highlightCode(code, lang) {
    const cleanLang = (lang || '').toLowerCase().trim();
    if (window.Prism && Prism.languages) {
        const grammar = Prism.languages[cleanLang] || Prism.languages.javascript || Prism.languages.python;
        if (grammar) {
            try {
                return Prism.highlight(code, grammar, cleanLang);
            } catch (e) {
                // fallback to escape
            }
        }
    }
    return escapeHtml(code);
}

function buildCodeSnippetHtml(id, language, code) {
    const cleanLang = (language || 'text').trim();
    const highlighted = highlightCode(code, cleanLang);

    return `
    <div class="code-snippet-box rounded-xl border border-[#333333] bg-[#1e1e1e] text-[#d4d4d4] my-3 overflow-hidden shadow-md text-left" data-id="${id}" data-lang="${escapeHtml(cleanLang)}">
        <div class="code-header flex items-center justify-between px-3 py-1.5 bg-[#252526] border-b border-[#333333] text-xs font-mono select-none">
            <span class="text-[#9cdcfe] font-semibold flex items-center gap-1.5">
                <span class="material-symbols-outlined text-[15px]">code</span>
                ${escapeHtml(cleanLang)}
            </span>
            <div class="flex items-center gap-1.5">
                <button class="copy-code-btn flex items-center gap-1 text-[#cccccc] hover:text-white px-2 py-0.5 rounded hover:bg-[#333333] transition-colors" data-id="${id}" title="Salin Kode">
                    <span class="material-symbols-outlined text-[14px]">content_copy</span>
                    <span class="copy-code-label text-[11px]">Salin</span>
                </button>
                <button class="open-tab-btn flex items-center gap-1 text-[#cccccc] hover:text-white px-2 py-0.5 rounded hover:bg-[#333333] transition-colors" data-id="${id}" data-lang="${escapeHtml(cleanLang)}" title="Buka di Editor / Preview Tab">
                    <span class="material-symbols-outlined text-[14px]">open_in_new</span>
                    <span class="text-[11px]">Buka Tab</span>
                </button>
            </div>
        </div>
        <pre class="p-3.5 overflow-x-auto text-xs font-mono leading-relaxed m-0 text-[#d4d4d4] select-text bg-[#1e1e1e]"><code class="language-${escapeHtml(cleanLang)}">${highlighted}</code></pre>
    </div>`.trim();
}

function extractCodeBlocksAsCards(text) {
    // Match closed ```lang\ncode``` or unclosed code block during streaming
    const codeBlockRegex = /```([^\r\n]*?)\r?\n([\s\S]*?)(?:```|$)/g;
    let cardsHtml = [];
    const cleanedText = text.replace(codeBlockRegex, (match, lang, code) => {
        codeSnippetCounter++;
        const id = `snippet-${codeSnippetCounter}`;
        const language = lang ? lang.trim() : 'text';
        const cleanCode = code.replace(/```$/, '').trim();
        cardsHtml.push({ id, language, code: cleanCode });
        return `__CODE_BLOCK_${id}__`;
    });
    return { cleanedText, cardsHtml };
}

function renderMarkdownLite(text) {
    if (!text) return '';

    const { cleanedText, cardsHtml } = extractCodeBlocksAsCards(text);
    let html = escapeHtml(cleanedText);

    // Headings
    html = html.replace(/^### (.*$)/gim, '<h3 class="text-base font-bold text-on-surface mt-3 mb-1">$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 class="text-lg font-bold text-on-surface mt-4 mb-2">$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1 class="text-xl font-bold text-on-surface mt-4 mb-2">$1</h1>');
    html = html.replace(/^---$/gm, '<hr class="my-3 border-border-subtle">');

    // Inline formatting
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/`([^`\n]+)`/g, '<code class="px-1.5 py-0.5 rounded bg-black/10 dark:bg-white/10 font-mono text-xs text-action-orange-vibrant font-medium">$1</code>');
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    html = html.replace(/(?<!href="|>)(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');

    // Lists
    html = html.replace(/^(\d+)\.\s+(.+)$/gm, '<li class="ol-line">$2</li>');
    html = html.replace(/^[ \t]*[•\-]\s+(.+)$/gm, '<li class="bullet-line">$1</li>');

    html = html.replace(/(<li class="ol-line">.*?<\/li>\n?)+/gs, (match) => `<ol>${match.replace(/\n/g, '')}</ol>`);
    html = html.replace(/(<li class="bullet-line">.*?<\/li>\n?)+/gs, (match) => `<ul>${match.replace(/\n/g, '')}</ul>`);

    html = html.replace(/\n{2,}/g, '<br>');
    html = html.replace(/\n/g, '<br>');

    // Store code snippets globally
    window._codeSnippets = window._codeSnippets || {};
    cardsHtml.forEach(card => {
        window._codeSnippets[card.id] = card.code;

        if (card.language === 'snippet.youtube') {
            try {
                // Auto open snippet player tab in sidebar
                renderFileDraft('snippet.youtube', card.code);
            } catch (err) {
                console.error("Error auto-rendering youtube draft:", err);
            }

            try {
                const data = JSON.parse(card.code);
                const isMusic = data.type === 'music';
                const directUrl = data.url || (isMusic 
                    ? (data.videoId && data.videoId !== 'search' ? `https://music.youtube.com/watch?v=${data.videoId}` : `https://music.youtube.com/search?q=${encodeURIComponent(data.title || '')}`)
                    : (data.videoId && data.videoId !== 'search' ? `https://www.youtube.com/watch?v=${data.videoId}` : `https://www.youtube.com/results?search_query=${encodeURIComponent(data.title || '')}`));
                const title = data.title || (isMusic ? 'YouTube Music' : 'YouTube Video');
                
                const widgetHtml = `
                <div class="my-3 p-3.5 rounded-xl border border-red-500/30 bg-red-950/20 text-on-surface shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-full bg-red-600/20 text-red-500 flex items-center justify-center shrink-0">
                            <span class="material-symbols-outlined text-[24px]">${isMusic ? 'music_note' : 'smart_display'}</span>
                        </div>
                        <div>
                            <div class="font-semibold text-sm text-on-surface line-clamp-1">${escapeHtml(title)}</div>
                            <div class="text-xs text-on-surface-variant flex items-center gap-1.5 mt-0.5">
                                <span class="font-medium text-red-400">${isMusic ? 'YouTube Music' : 'YouTube Video'}</span>
                                • <span class="text-emerald-500 font-medium">Sedang diputar</span>
                            </div>
                        </div>
                    </div>
                    <div class="flex items-center gap-2 self-end sm:self-auto shrink-0">
                        <button class="open-tab-btn px-3 py-1.5 bg-surface-container-high hover:bg-surface-dim text-on-surface rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors shadow-xs" data-id="${card.id}" data-lang="snippet.youtube">
                            <span class="material-symbols-outlined text-[15px]">side_navigation</span>
                            <span>Buka di Panel Snippet</span>
                        </button>
                        <a href="${directUrl}" target="_blank" rel="noopener noreferrer" class="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-xs">
                            <span class="material-symbols-outlined text-[15px]">open_in_new</span>
                            <span>Buka di Browser</span>
                        </a>
                    </div>
                </div>`.trim();
                html = html.replace(`__CODE_BLOCK_${card.id}__`, widgetHtml);
                return;
            } catch (e) {
                // fallback to default code snippet box
            }
        }

        if (card.language === 'snippet.image') {
            try {
                renderFileDraft('snippet.image', card.code);
            } catch (err) {
                console.error("Error auto-rendering image draft:", err);
            }
        }

        html = html.replace(`__CODE_BLOCK_${card.id}__`, buildCodeSnippetHtml(card.id, card.language, card.code));
    });

    return html;
}

// ===================== MESSAGE RENDERING =====================

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function renderUserMessage(text) {
    const node = userMessageTemplate.content.cloneNode(true);
    node.querySelector('.message-text').innerHTML = renderMarkdownLite(text);
    chatMessages.appendChild(node);
    scrollToBottom();
}

/**
 * Render placeholder pesan AI (dengan panel thinking kosong + loading dots),
 * return referensi elemen-elemen pentingnya supaya bisa diupdate live
 * seiring trace/token masuk.
 */
function renderAiMessagePlaceholder() {
    const node = aiMessageTemplate.content.cloneNode(true);
    const wrapper = node.querySelector('.ai-message-wrapper');
    chatMessages.appendChild(node);
    scrollToBottom();

    const thinkingPanel = wrapper.querySelector('.thinking-panel');
    const thinkingLabel = wrapper.querySelector('.thinking-label');
    const thinkingBody = wrapper.querySelector('.thinking-body');
    const thinkingHeader = wrapper.querySelector('.thinking-header');
    const messageText = wrapper.querySelector('.message-text');
    // <details> handles expand/collapse natively — no click handler needed

    return { wrapper, thinkingPanel, thinkingLabel, thinkingBody, thinkingHeader, messageText };
}

function appendTraceStepToPanel(refs, step) {
    if (!step) return;
    const formatted = formatTraceStep(step);
    if (!formatted || formatted === 'undefined') return;

    const row = document.createElement('div');
    row.className = 'flex gap-2 py-0.5 text-xs';
    row.innerHTML = `<span class="text-secondary/50 flex-shrink-0 mt-0.5">›</span><span>${formatted.replace(/\\n/g, '<br>')}</span>`;

    const stepType = step.type || step.step;
    if (stepType === 'reasoning') {
        const lastRow = refs.thinkingBody.lastElementChild;
        if (lastRow && lastRow.dataset.type === 'reasoning') {
            lastRow.innerHTML = row.innerHTML;
            return;
        }
        row.dataset.type = 'reasoning';
    }

    refs.thinkingBody.appendChild(row);
    refs.thinkingLabel.textContent = traceStepLabel(step);
}

// Render ulang 1 pesan dari data tersimpan (dipakai saat load percakapan lama)
function renderStoredMessage(msg) {
    if (msg.role === 'user') {
        renderUserMessage(msg.content);
    } else if (msg.role === 'assistant') {
        const node = aiMessageTemplate.content.cloneNode(true);
        const wrapper = node.querySelector('.ai-message-wrapper');
        // Percakapan lama tidak punya trace — hapus thinking panel
        wrapper.querySelector('.thinking-panel').remove();
        wrapper.querySelector('.message-text').innerHTML = renderMarkdownLite(msg.content);
        chatMessages.appendChild(node);
    }
    // role 'system' (ringkasan auto-compaction) sengaja tidak ditampilkan ke user
}

function clearChatMessages() {
    chatMessages.innerHTML = '';
}

function renderWelcomeMessage() {
    const node = aiMessageTemplate.content.cloneNode(true);
    const wrapper = node.querySelector('.ai-message-wrapper');
    wrapper.querySelector('.thinking-panel').remove();
    wrapper.querySelector('.message-text').textContent = 'Hello. I am Jarvis. How can I assist you with your project today?';
    chatMessages.appendChild(node);
}

// ===================== SENDING MESSAGES =====================

async function sendMessage() {
    const text = userInput.value.trim();
    if (!text && !pendingImageBase64) return;
    if (isProcessing) return;

    isProcessing = true;
    sendBtn.disabled = true;
    userInput.value = '';
    userInput.style.height = 'auto'; // reset textarea height

    renderUserMessage(text || '[Gambar terlampir]');
    const refs = renderAiMessagePlaceholder();

    const payload = pendingImageBase64
        ? { text, image: pendingImageBase64 }
        : text;

    clearPendingImage();
    statusText.textContent = 'Memproses...';

    let firstTokenReceived = false;
    let rawBuffer = '';
    let usedTools = new Set();

    const STATUS_TOKEN_PATTERNS = [
        /^Memproses\.\.\.\s*$/,
        /^Menjalankan:.+\.\.\.\s*$/,
        /^\s*Merangkum hasil\.\.\.\s*$/
    ];

    function isStatusToken(token) {
        return STATUS_TOKEN_PATTERNS.some(pattern => pattern.test(token.trim()));
    }

    const onToken = (token) => {
        if (isStatusToken(token)) {
            refs.thinkingLabel.textContent = token.trim();
            return;
        }
        if (!firstTokenReceived) {
            refs.messageText.textContent = '';
            firstTokenReceived = true;
        }
        rawBuffer += token;
        refs.messageText.innerHTML = renderMarkdownLite(rawBuffer);
        scrollToBottom();
    };

    const onTrace = (step) => {
        if (step.type === 'tool_call') {
            step.tools.forEach(t => usedTools.add(t.tool));
        }
        appendTraceStepToPanel(refs, step);
        // Dua tipe trace khusus ini ditangani terpisah untuk mengisi Code Preview pane
        if (step.type === 'file_draft') {
            renderFileDraft(step.filename, step.content);
        } else if (step.type === 'file_view') {
            renderFileView(step.filename, step.content);
        }
        scrollToBottom();
    };

    window.jarvis.onStreamToken(onToken);
    window.jarvis.onTraceUpdate(onTrace);

    try {
        const result = await window.jarvis.sendCommandStream(payload);
        const finalText = result?.response;

        if (!result?.success) {
            refs.messageText.innerHTML = renderMarkdownLite(finalText || 'Terjadi kesalahan tidak diketahui.');
        } else if (!firstTokenReceived && finalText) {
            refs.messageText.innerHTML = renderMarkdownLite(finalText);
        }
        refs.thinkingLabel.textContent = 'Proses berpikir selesai';
    } catch (err) {
        refs.messageText.textContent = `❌ Terjadi kesalahan: ${err.message || err}`;
    } finally {
        statusText.textContent = 'Ready';
        isProcessing = false;
        sendBtn.disabled = false;

        // Render response tags (tool badges)
        if (usedTools.size > 0) {
            const tagsContainer = document.createElement('div');
            tagsContainer.className = 'flex gap-2 flex-wrap';
            usedTools.forEach(toolName => {
                const label = TOOL_LABELS[toolName] || toolName;
                const icon = TOOL_ICONS[label] || 'smart_toy';
                const tag = document.createElement('span');
                tag.className = 'font-label-sm text-label-sm bg-surface-container-high px-2 py-1 rounded-full text-secondary flex items-center gap-1';
                tag.innerHTML = `<span class="material-symbols-outlined" style="font-size:14px">${icon}</span> ${escapeHtml(label)}`;
                tagsContainer.appendChild(tag);
            });
            refs.wrapper.appendChild(tagsContainer);
        }

        // loadConversationList(); // disabled for now
    }
}

sendBtn?.addEventListener('click', sendMessage);
userInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Code snippet action buttons (Copy code & Open in Tab)
chatMessages.addEventListener('click', async (e) => {
    // 1. Copy snippet button
    const copyCodeBtn = e.target.closest('.copy-code-btn');
    if (copyCodeBtn) {
        const id = copyCodeBtn.dataset.id;
        const code = window._codeSnippets?.[id] || '';
        if (code) {
            try {
                if (window.jarvis && window.jarvis.copyToClipboard) {
                    await window.jarvis.copyToClipboard(code);
                } else if (navigator.clipboard) {
                    await navigator.clipboard.writeText(code);
                }
                const icon = copyCodeBtn.querySelector('.material-symbols-outlined');
                const label = copyCodeBtn.querySelector('.copy-code-label');
                if (icon) icon.textContent = 'check';
                if (label) label.textContent = 'Tersalin!';
                copyCodeBtn.classList.add('text-green-400');
                setTimeout(() => {
                    if (icon) icon.textContent = 'content_copy';
                    if (label) label.textContent = 'Salin';
                    copyCodeBtn.classList.remove('text-green-400');
                }, 2000);
            } catch (err) {
                console.error('Gagal menyalin snippet kode:', err);
            }
        }
        return;
    }

    // 2. Open in Tab button
    const openTabBtn = e.target.closest('.open-tab-btn');
    if (openTabBtn) {
        const id = openTabBtn.dataset.id;
        const lang = openTabBtn.dataset.lang || 'code';
        const code = window._codeSnippets?.[id] || '';
        if (code) {
            renderFileView(`snippet.${lang}`, code);
        }
        return;
    }

    // 3. Fallback code-card click
    const card = e.target.closest('.code-card');
    if (card) {
        const id = card.dataset.id;
        const lang = card.dataset.lang || 'code';
        const code = window._codeSnippets?.[id];
        if (code) renderFileView(`snippet.${lang}`, code);
    }
});

// Copy message button handler (event delegation)
chatMessages.addEventListener('click', async (e) => {
    const copyBtn = e.target.closest('.copy-message-btn');
    if (!copyBtn) return;

    const wrapper = copyBtn.closest('.ai-message-wrapper') || copyBtn.closest('.flex-1');
    const msgTextEl = wrapper ? wrapper.querySelector('.message-text') : null;
    if (!msgTextEl) return;

    // Bersihkan teks dari spasi berlebih
    const textToCopy = (msgTextEl.innerText || msgTextEl.textContent || '').trim();
    if (!textToCopy) return;

    try {
        if (window.jarvis && window.jarvis.copyToClipboard) {
            await window.jarvis.copyToClipboard(textToCopy);
        } else if (navigator.clipboard) {
            await navigator.clipboard.writeText(textToCopy);
        }

        const iconSpan = copyBtn.querySelector('.material-symbols-outlined');
        const labelSpan = copyBtn.querySelector('.copy-label');
        
        if (iconSpan) iconSpan.textContent = 'check';
        if (labelSpan) labelSpan.textContent = 'Tersalin!';
        copyBtn.classList.add('text-green-600');

        setTimeout(() => {
            if (iconSpan) iconSpan.textContent = 'content_copy';
            if (labelSpan) labelSpan.textContent = 'Salin';
            copyBtn.classList.remove('text-green-600');
        }, 2000);
    } catch (err) {
        console.error('Gagal menyalin pesan:', err);
    }
});

// ===================== IMAGE ATTACHMENT =====================
attachBtn?.addEventListener('click', () => imageInput.click());

imageInput?.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
        pendingImageBase64 = reader.result.split(',')[1];
        imagePreview.src = reader.result;
        imagePreviewContainer.classList.remove('hidden');
    };
    reader.readAsDataURL(file);
});

function clearPendingImage() {
    pendingImageBase64 = null;
    imageInput.value = '';
    imagePreviewContainer.classList.add('hidden');
    imagePreview.src = '';
}

removeImageBtn?.addEventListener('click', clearPendingImage);

// ===================== VOICE INPUT =====================
let recognition = null;
let isListening = false;

function initVoiceRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.warn('[Jarvis] Web Speech API tidak tersedia di environment ini.');
        return null;
    }
    const rec = new SpeechRecognition();
    rec.lang = 'id-ID';
    rec.continuous = false;
    rec.interimResults = false;

    rec.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        userInput.value = transcript;
    };
    rec.onend = () => {
        isListening = false;
        voiceBtn.classList.remove('listening');
    };
    rec.onerror = (e) => {
        console.error('[Jarvis] Voice recognition error:', e.error);
        isListening = false;
        voiceBtn.classList.remove('listening');
    };
    return rec;
}

voiceBtn?.addEventListener('click', () => {
    if (!recognition) recognition = initVoiceRecognition();
    if (!recognition) {
        statusText.textContent = 'Voice input tidak didukung';
        return;
    }
    if (isListening) {
        recognition.stop();
        isListening = false;
        voiceBtn.classList.remove('listening');
    } else {
        recognition.start();
        isListening = true;
        voiceBtn.classList.add('listening');
    }
});

// ===================== CHAT HISTORY / CONVERSATIONS =====================
// Fungsi-fungsi ini dipertahankan tapi belum dipanggil di init() —
// siap diaktifkan kembali nanti.

async function loadConversationList() {
    const conversations = await window.jarvis.listConversations();
    conversationList.innerHTML = '';

    if (!conversations || conversations.length === 0) {
        conversationList.appendChild(conversationEmptyState);
        return;
    }

    conversations.forEach(conv => {
        const node = conversationItemTemplate.content.cloneNode(true);
        const item = node.querySelector('.conv-item');
        item.dataset.id = conv.id;
        item.querySelector('.conv-title').textContent = conv.title;
        if (conv.id === activeConversationId) item.classList.add('bg-primary-container/10', 'text-primary');

        item.addEventListener('click', (e) => {
            if (e.target.closest('.conv-delete-btn')) return;
            switchToConversation(conv.id);
        });

        item.querySelector('.conv-delete-btn').addEventListener('click', async (e) => {
            e.stopPropagation();
            await window.jarvis.deleteConversation(conv.id);
            if (conv.id === activeConversationId) {
                await startNewConversation();
            } else {
                loadConversationList();
            }
        });

        conversationList.appendChild(node);
    });
}

async function switchToConversation(conversationId) {
    if (conversationId === activeConversationId) return;
    const conv = await window.jarvis.loadConversation(conversationId);
    if (!conv) return;

    activeConversationId = conversationId;
    await window.jarvis.switchConversation(conversationId);

    clearChatMessages();
    if (conv.messages && conv.messages.length > 0) {
        conv.messages.forEach(renderStoredMessage);
    } else {
        renderWelcomeMessage();
    }
    loadConversationList();
}

async function startNewConversation() {
    const conv = await window.jarvis.createConversation();
    activeConversationId = conv.id;
    await window.jarvis.switchConversation(conv.id);
    clearChatMessages();
    renderWelcomeMessage();
    loadConversationList();
}

newChatBtn?.addEventListener('click', startNewConversation);

// ===================== INIT =====================
async function init() {
    window.jarvis.windowReady();
    renderWelcomeMessage();
}

init();