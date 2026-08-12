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
    save_credential: 'Kredensial', list_credentials: 'Kredensial', delete_credential: 'Kredensial'
};

const TOOL_ICONS = {
    'Web': 'language', 'Riset': 'science', 'Email': 'email',
    'Musik': 'music_note', 'Video': 'videocam', 'YouTube': 'smart_display',
    'File': 'description', 'Kode': 'code', 'Aplikasi': 'apps',
    'Sistem': 'settings', 'Screenshot': 'screenshot_monitor',
    'Vision': 'visibility', 'Memori': 'psychology',
    'Kredensial': 'key'
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
    switch (step.type) {
        case 'routing': {
            const tools = (step.toolsConsidered || []).join(', ') || '(tidak ada, mode chat biasa)';
            const cats = Object.keys(step.categoryScores || {}).join(', ') || '-';
            return `🧭 Kategori terpilih: ${cats} → Tool dipertimbangkan: ${tools}`;
        }
        case 'tool_call': {
            const list = (step.tools || []).map(t => `${t.tool}("${t.query}")`).join(', ');
            return `⚙️ Menjalankan: ${list}`;
        }
        case 'reasoning': {
            return `🧠 Memikirkan aksi:\n<div class="mt-1 p-2 bg-black/5 rounded text-xs font-code-snippet">${escapeHtml(step.content).replace(/\n/g, '<br>')}</div>`;
        }
        case 'tool_result': {
            return (step.results || []).map(r =>
                r.success ? `✅ ${r.tool} berhasil` : `❌ ${r.tool} gagal: ${r.error || 'unknown error'}`
            ).join('\n');
        }
        case 'retry':
            return `🔁 Percobaan ulang #${step.attempt} — alasan: ${step.reason}`;
        case 'stale_knowledge_override':
            return `⏱️ Info berpotensi usang, dialihkan ke pencarian web`;
        case 'synthesis_start':
            return `📝 Merangkum hasil tool jadi jawaban akhir...`;
        case 'done':
            return `✔️ Selesai.`;
        case 'chat_response':
            return `💬 Merespons langsung tanpa tool.`;
        case 'final_fallback':
            return `⚠️ Gagal semua percobaan — kirim fallback.`;
        case 'error':
            return `❌ Error: ${step.message || 'Tidak diketahui'}`;
        default:
            return `• ${step.type}`;
    }
}

function traceStepLabel(step) {
    switch (step.type) {
        case 'routing': return 'Menganalisis permintaan...';
        case 'reasoning': return 'Memutuskan langkah...';
        case 'tool_call': return 'Menjalankan tool...';
        case 'tool_result': return 'Memproses hasil tool...';
        case 'retry': return `Mencoba ulang (percobaan ${step.attempt})...`;
        case 'synthesis_start': return 'Merangkum hasil...';
        case 'done': return 'Proses berpikir selesai';
        case 'chat_response': return 'Menjawab langsung';
        case 'final_fallback': return 'Gagal setelah beberapa percobaan';
        case 'error': return 'Terjadi kesalahan';
        default: return 'Memproses...';
    }
}

// ===================== CODE PREVIEW PANE (File Draft / View) =====================

function expandCodeSidebar() {
    codePreview.classList.remove('hidden');
    codePreview.classList.add('flex');
}

/**
 * Render draft file (dari create_file yang di-intercept) — bisa diedit,
 * ada tombol Simpan (tulis ke disk via confirmSaveFile) dan Batalkan.
 */
function renderFileDraft(filename, content) {
    expandCodeSidebar();
    codeFileName.textContent = filename;
    codeContentInner.innerHTML = '';

    const textarea = document.createElement('textarea');
    textarea.className = 'code-editor';
    textarea.value = content;
    codeContentInner.appendChild(textarea);

    const actions = document.createElement('div');
    actions.className = 'flex gap-2 mt-3';

    const saveBtn = document.createElement('button');
    saveBtn.className = 'px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-semibold hover:bg-green-700 transition-colors';
    saveBtn.textContent = 'Simpan';

    const discardBtn = document.createElement('button');
    discardBtn.className = 'px-4 py-2 bg-surface-container-high text-on-surface rounded-lg text-sm font-medium hover:bg-surface-dim transition-colors';
    discardBtn.textContent = 'Batalkan';

    const statusMsg = document.createElement('div');
    statusMsg.className = 'text-sm mt-2';

    saveBtn.addEventListener('click', async () => {
        saveBtn.disabled = true;
        saveBtn.textContent = 'Menyimpan...';
        const result = await window.jarvis.confirmSaveFile({
            filename,
            content: textarea.value
        });

        if (result?.success) {
            statusMsg.textContent = `✅ Tersimpan di ${result.filePath} (${result.sizeKB} KB)`;
            statusMsg.className = 'text-sm mt-2 text-green-600';
            textarea.disabled = true;
            saveBtn.remove();
            discardBtn.textContent = 'Tutup';
        } else {
            statusMsg.textContent = `❌ Gagal menyimpan: ${result?.error || 'unknown error'}`;
            statusMsg.className = 'text-sm mt-2 text-error';
            saveBtn.disabled = false;
            saveBtn.textContent = 'Simpan';
        }
    });

    discardBtn.addEventListener('click', () => {
        clearCodePreview();
    });

    actions.appendChild(saveBtn);
    actions.appendChild(discardBtn);
    codeContentInner.appendChild(actions);
    codeContentInner.appendChild(statusMsg);
}

/**
 * Render isi file hasil read_file — read-only, tanpa tombol simpan.
 */
function renderFileView(filename, content) {
    expandCodeSidebar();
    codeFileName.textContent = filename;
    codeContentInner.innerHTML = '';

    // Determine language from filename extension
    let lang = 'javascript';
    const extMatch = filename.match(/\.([a-z0-9]+)$/i);
    if (extMatch) {
        const ext = extMatch[1].toLowerCase();
        const map = {
            'js': 'javascript', 'html': 'html', 'css': 'css',
            'py': 'python', 'json': 'json', 'md': 'markdown'
        };
        lang = map[ext] || ext;
    }

    const pre = document.createElement('pre');
    pre.className = 'code-view';

    const codeEl = document.createElement('code');
    codeEl.className = `language-${lang}`;
    codeEl.textContent = content;

    pre.appendChild(codeEl);
    codeContentInner.appendChild(pre);

    // Apply Prism highlighting
    if (window.Prism) {
        Prism.highlightElement(codeEl);
    }
}

function clearCodePreview() {
    codeFileName.textContent = 'Preview';
    codeContentInner.innerHTML = '<div class="bg-surface-gray rounded-lg border border-border-subtle h-full p-4 flex items-center justify-center text-secondary font-body-md">No active preview available.</div>';
    codePreview.classList.add('hidden');
    codePreview.classList.remove('flex');
}

// ===================== MARKDOWN RENDERING (RINGAN) =====================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

let codeSnippetCounter = 0;

function extractCodeBlocksAsCards(text) {
    const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g;
    let cardsHtml = [];
    const cleanedText = text.replace(codeBlockRegex, (match, lang, code) => {
        codeSnippetCounter++;
        const id = `snippet-${codeSnippetCounter}-${Date.now()}`;
        const language = lang || 'text';
        cardsHtml.push({ id, language, code: code.trim() });
        return `__CODE_CARD_${id}__`;
    });
    return { cleanedText, cardsHtml };
}

function buildCodeCardHtml(id, language) {
    return `<div class="code-card flex items-center gap-3 p-3 bg-surface-gray rounded-lg border border-border-subtle my-2 cursor-pointer hover:bg-surface-container-high transition-colors" data-id="${id}" data-lang="${language}">
        <span class="material-symbols-outlined text-secondary" style="font-size:18px">description</span>
        <span class="flex-1 text-sm font-medium text-on-surface font-code-snippet">Kode ${escapeHtml(language)}</span>
        <span class="text-xs text-primary font-semibold">Lihat →</span>
    </div>`;
}

function renderMarkdownLite(text) {
    if (!text) return '';

    const { cleanedText, cardsHtml } = extractCodeBlocksAsCards(text);
    let html = escapeHtml(cleanedText);

    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
    html = html.replace(/(?<!href="|>)(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank">$1</a>');

    html = html.replace(/^(\d+)\.\s+(.+)$/gm, '<li class="ol-line">$2</li>');
    html = html.replace(/^[ \t]*[•\-]\s+(.+)$/gm, '<li class="bullet-line">$1</li>');

    html = html.replace(/(<li class="ol-line">.*?<\/li>\n?)+/gs, (match) => `<ol>${match.replace(/\n/g, '')}</ol>`);
    html = html.replace(/(<li class="bullet-line">.*?<\/li>\n?)+/gs, (match) => `<ul>${match.replace(/\n/g, '')}</ul>`);

    html = html.replace(/\n{2,}/g, '<br>');
    html = html.replace(/\n/g, '<br>');

    // Inject code cards (after escape, so HTML is safe)
    cardsHtml.forEach(card => {
        html = html.replace(`__CODE_CARD_${card.id}__`, buildCodeCardHtml(card.id, card.language));
    });

    // Store code snippets for retrieval on card click
    window._codeSnippets = window._codeSnippets || {};
    cardsHtml.forEach(card => { window._codeSnippets[card.id] = card.code; });

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
    const row = document.createElement('div');
    row.className = 'flex gap-2 py-0.5 text-xs';
    row.innerHTML = `<span class="text-secondary/50 flex-shrink-0 mt-0.5">›</span><span>${formatTraceStep(step).replace(/\\n/g, '<br>')}</span>`;

    if (step.type === 'reasoning') {
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

// Code card click handler (event delegation)
chatMessages.addEventListener('click', (e) => {
    const card = e.target.closest('.code-card');
    if (!card) return;
    const id = card.dataset.id;
    const lang = card.dataset.lang;
    const code = window._codeSnippets?.[id];
    if (code) renderFileView(`snippet.${lang}`, code);
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