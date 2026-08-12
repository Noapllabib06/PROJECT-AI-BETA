/**
 * src/gui/ui_handler.js
 * Menghubungkan semua interaksi UI ke API window.jarvis (lewat preload.js).
 *
 * Ditulis ulang untuk mendukung 2 fitur baru:
 * - Chat History: sidebar percakapan (list/buat/pindah/hapus)
 * - Thinking Process: panel collapsible berisi trace tiap balasan AI
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

const sidebar = document.getElementById('sidebar');
const toggleSidebarBtn = document.getElementById('toggle-sidebar-btn');
const newChatBtn = document.getElementById('newChatBtn');
const conversationList = document.getElementById('conversationList');
const conversationEmptyState = document.getElementById('conversationEmptyState');

const minimizeBtn = document.getElementById('minimizeBtn');
const maximizeBtn = document.getElementById('maximizeBtn');
const closeBtn = document.getElementById('closeBtn');

const aiMessageTemplate = document.getElementById('aiMessageTemplate');
const userMessageTemplate = document.getElementById('userMessageTemplate');
const conversationItemTemplate = document.getElementById('conversationItemTemplate');

// ===================== STATE =====================
let activeConversationId = null;
let pendingImageBase64 = null;
let isProcessing = false; // cegah kirim pesan bersamaan (satu request pada satu waktu)

// ===================== WINDOW CONTROLS =====================
minimizeBtn?.addEventListener('click', () => window.jarvis.minimizeWindow());
maximizeBtn?.addEventListener('click', () => window.jarvis.maximizeWindow());
closeBtn?.addEventListener('click', () => window.jarvis.closeWindow());

// ===================== SIDEBAR TOGGLE =====================
toggleSidebarBtn?.addEventListener('click', () => {
    sidebar.classList.toggle('collapsed');
});

// ===================== CODE PREVIEW PANE TOGGLE (placeholder) =====================
const codeSidebar = document.getElementById('code-sidebar');
const toggleCodeBtn = document.getElementById('toggle-code-btn');
toggleCodeBtn?.addEventListener('click', () => {
    codeSidebar.classList.toggle('collapsed');
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
        case 'chat_response':
            return `💬 Menjawab langsung tanpa tool`;
        case 'final_fallback':
            return `⚠️ Semua percobaan gagal — memberi jawaban permintaan maaf`;
        case 'error':
            return `🚨 Error: ${step.message}`;
        case 'done':
            return `✔️ Selesai`;
        case 'file_draft':
            return `📄 Draft file "${step.filename}" dikirim ke Code Preview, menunggu konfirmasi`;
        case 'file_view':
            return `📄 Menampilkan isi "${step.filename}" di Code Preview`;
        default:
            return `• ${step.type}`;
    }
}

function traceStepLabel(step) {
    // Label singkat yang tampil di header panel (sebelum diklik buka)
    switch (step.type) {
        case 'routing': return 'Menganalisis permintaan...';
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
const codeContentInner = document.getElementById('codeContentInner');
const codeFileName = document.getElementById('codeFileName');

function expandCodeSidebar() {
    codeSidebar.classList.remove('collapsed');
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
    actions.className = 'code-actions';

    const saveBtn = document.createElement('button');
    saveBtn.className = 'code-btn code-btn-save';
    saveBtn.textContent = 'Simpan';

    const discardBtn = document.createElement('button');
    discardBtn.className = 'code-btn code-btn-discard';
    discardBtn.textContent = 'Batalkan';

    const statusMsg = document.createElement('div');
    statusMsg.className = 'code-status-msg';

    saveBtn.addEventListener('click', async () => {
        saveBtn.disabled = true;
        saveBtn.textContent = 'Menyimpan...';
        const result = await window.jarvis.confirmSaveFile({
            filename,
            content: textarea.value // pakai versi yang sudah diedit user jika ada
        });

        if (result?.success) {
            statusMsg.textContent = `✅ Tersimpan di ${result.filePath} (${result.sizeKB} KB)`;
            statusMsg.classList.add('success');
            textarea.disabled = true;
            saveBtn.remove();
            discardBtn.textContent = 'Tutup';
        } else {
            statusMsg.textContent = `❌ Gagal menyimpan: ${result?.error || 'unknown error'}`;
            statusMsg.classList.add('error');
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
 * Render isi file hasil read_file — read-only, tanpa tombol simpan
 * (karena file ini sudah ada di disk, bukan draft baru).
 */
function renderFileView(filename, content) {
    expandCodeSidebar();
    codeFileName.textContent = filename;

    codeContentInner.innerHTML = '';
    const pre = document.createElement('pre');
    pre.className = 'code-view';
    pre.textContent = content;
    codeContentInner.appendChild(pre);
}

function clearCodePreview() {
    codeFileName.textContent = 'Code Preview';
    codeContentInner.innerHTML = '<div class="code-placeholder">Belum ada konten untuk ditampilkan di sini.</div>';
}

// ===================== MARKDOWN RENDERING (RINGAN) =====================
/**
 * Konversi markdown dasar ke HTML, dengan escape HTML dulu (anti-XSS)
 * sebelum menerapkan rule markdown. Cukup untuk kebutuhan Jarvis:
 * bold, newline, bullet list, dan link — bukan parser markdown lengkap.
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function renderMarkdownLite(text) {
    let html = escapeHtml(text);
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
    html = html.replace(/(?<!href="|>)(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank">$1</a>');
    html = html.replace(/^[•\-]\s+(.+)$/gm, '<span class="bullet-line">• $1</span>');
    html = html.replace(/\n/g, '<br>');
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

    // Klik header untuk buka/tutup panel
    thinkingHeader.addEventListener('click', () => {
        thinkingPanel.classList.toggle('expanded');
    });

    return { wrapper, thinkingPanel, thinkingLabel, thinkingBody, thinkingHeader, messageText };
}

function appendTraceStepToPanel(refs, step) {
    const row = document.createElement('div');
    row.className = 'thinking-step';
    row.innerHTML = `<span class="step-icon">›</span><span>${formatTraceStep(step).replace(/\n/g, '<br>')}</span>`;
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
        // Percakapan lama tidak punya trace tersimpan — sembunyikan panel thinking
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
    wrapper.querySelector('.message-text').textContent = 'Halo! Saya Jarvis, asisten AI pribadi Anda. Ada yang bisa saya bantu?';
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

    renderUserMessage(text || '[Gambar terlampir]');
    const refs = renderAiMessagePlaceholder();

    const payload = pendingImageBase64
        ? { text, image: pendingImageBase64 }
        : text;

    clearPendingImage();
    statusText.textContent = 'Memproses...';

    // Listener token & trace di-attach sekali per request, lalu dilepas
    // setelah selesai — karena channel IPC-nya global (bukan per-request).
    let firstTokenReceived = false;
    let rawBuffer = '';

    const onToken = (token) => {
        if (!firstTokenReceived) {
            refs.messageText.textContent = '';
            firstTokenReceived = true;
        }
        rawBuffer += token;
        refs.messageText.innerHTML = renderMarkdownLite(rawBuffer);
        scrollToBottom();
    };

    const onTrace = (step) => {
        appendTraceStepToPanel(refs, step);
        // Dua tipe trace khusus ini ditangani terpisah untuk mengisi
        // Code Preview pane, bukan cuma tampil di panel thinking.
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
        refs.thinkingHeader.querySelector('.chevron').style.display = 'inline-block';
    } catch (err) {
        refs.messageText.textContent = `❌ Terjadi kesalahan: ${err.message || err}`;
    } finally {
        statusText.textContent = 'Siap';
        isProcessing = false;
        sendBtn.disabled = false;
        // Refresh sidebar supaya judul percakapan (auto-generate dari pesan pertama) ikut update
        loadConversationList();
    }
}

sendBtn?.addEventListener('click', sendMessage);
userInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// ===================== IMAGE ATTACHMENT =====================
attachBtn?.addEventListener('click', () => imageInput.click());

imageInput?.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
        // Buang prefix "data:image/...;base64," — kirim base64 murni ke backend
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
        statusText.textContent = 'Voice input tidak didukung di perangkat ini';
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
        if (conv.id === activeConversationId) item.classList.add('active');

        item.addEventListener('click', (e) => {
            if (e.target.closest('.conv-delete-btn')) return; // biar tidak switch saat klik hapus
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

    const conversations = await window.jarvis.listConversations();
    if (conversations && conversations.length > 0) {
        // Buka percakapan paling baru secara default
        await switchToConversation(conversations[0].id);
    } else {
        await startNewConversation();
    }
}

init();