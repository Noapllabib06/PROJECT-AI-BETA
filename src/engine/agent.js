/**
 * src/engine/agent.js
 * Mesin utama — Tool Registry Pattern + Dynamic Tool Routing.
 * 
 * Alur:
 * 1. Registry memuat semua tool dari src/tools/ secara otomatis
 * 2. Input user dianalisis untuk menentukan kategori tool yang relevan (scoring-based)
 * 3. Hanya tool yang relevan (max 3-5) yang disertakan dalam system prompt
 * 4. LLM output JSON { tool, query } — parsing standar
 * 5. Eksekusi tool via registry.execute()
 * 6. Jika gagal, Micro ReAct loop maksimal 1 retry
 *
 * UPDATE (Chat History + Thinking Process):
 * - Setiap percakapan sekarang punya conversationId, history-nya
 *   di-load/save ke disk lewat conversation_manager.js (bukan cuma
 *   di RAM lagi seperti sebelumnya).
 * - Ditambahkan onTraceCallback: mengirim event terstruktur di setiap
 *   tahap pipeline (routing, tool call, retry, hasil) supaya UI bisa
 *   menampilkan panel "Thinking Process" yang detail.
 */

const { ChatOllama } = require("@langchain/ollama");
const _prompt = require("./prompt.js");
const { PERSONA } = _prompt;
const logger = require("../utils/logger");
const registry = require("../tools/registry");
const { generateErrorFeedback } = require("./feedback_loop");
const json_validator = require("./json_validator");
const axios = require("axios");
const conversationManager = require("./conversation_manager");

// Muat semua tool dari registry sekali saat startup
registry.loadAll();

// ===================== DYNAMIC TOOL ROUTING =====================
const TOOL_CATEGORIES = {
    WEB: {
        keywords: ['cari', 'berita', 'web', 'google', 'search', 
                   'info', 'informasi', 'tentang', 'apa itu', 'siapa', 'kapan', 'dimana', 'mengapa',
                   'buka', 'open', 'website', 'situs', 'halaman', 'browser', 'maps', 'lokasi',
                   'alamat', 'berikan'],
        tools: ['search_web', 'open_website', 'read_webpage', 'research_and_summarize']
    },
    MEDIA: {
        keywords: ['putar', 'lagu', 'video', 'tutorial', 'youtube', 'musik', 'music', 'play', 
                   'nonton', 'tonton', 'dengerin', 'dengarkan', 'mainkan', 'stream',
                   'channel', 'chanel', 'kanal'],
        tools: ['search_youtube', 'play_music', 'play_video', 'open_youtube_channel']
    },
    FILE: {
        keywords: ['berkas', 'file', 'tulis', 'baca', 'kode', 'catatan', 'dokumen', 'document',
                   'buka file', 'folder', 'proyek', 'project', 'screenshot', 'tangkap layar', 
                   'capture layar', 'ambil gambar layar', 'indeks kode', 'codebase', 'foto',
                   'ada apa di layar', 'jelaskan layar', 'analisa layar', 'analisa screenshot',
                   'apa yang terlihat', 'lihat layar saya'],
        tools: ['create_file', 'read_file', 'ingest_codebase', 'take_screenshot', 'analyze_screen']
    },
    MEMORY: {
        keywords: ['ingat', 'memori', 'simpan', 'lupa', 'ingatan', 'remember', 'forget', 'memory', 'save', 'past'],
        tools: ['save_memory', 'search_memory']
    },
    APP: {
        keywords: ['kalkulator', 'calculator', 'notepad', 'catatan', 'wordpad', 'paint',
                   'file explorer', 'task manager', 'pengelola tugas', 'control panel',
                   'panel kontrol', 'command prompt', 'powershell', 'vscode', 'visual studio code',
                   'discord', 'spotify', 'steam', 'telegram', 'snipping tool',
                   'buka aplikasi', 'jalankan aplikasi', 'aplikasi',
                   'volume', 'suara', 'kencangkan', 'pelankan', 'naikkan volume',
                   'turunkan volume', 'mute', 'unmute'],
        tools: ['open_app', 'control_volume']
    },
    EMAIL: {
        keywords: ['email', 'e-mail', 'gmail', 'inbox', 'surel',
                   'cek email', 'ada email', 'email baru', 'email masuk',
                   'outlook', 'yahoo mail'],
        tools: ['check_email']
    },
    CREDENTIALS: {
        keywords: ['kredensial', 'credential', 'password', 'kata sandi', 'sandi',
                   'login', 'akun', 'simpan password', 'simpan kredensial',
                   'simpan akun', 'lupa password', 'hapus kredensial',
                   'daftar kredensial', 'daftar akun tersimpan'],
        tools: ['save_credential', 'list_credentials', 'delete_credential']
    }
};

const SENSITIVE_CONTENT_PATTERN = /password|kredensial|credential|kata sandi|\bsandi\b|api[_\s]?key|token|secret|rahasia|\bpin\b|save_credential/i;

function isSensitiveContent(text) {
    if (!text || typeof text !== 'string') return false;
    return SENSITIVE_CONTENT_PATTERN.test(text);
}

function determineRelevantTools(userInput) {
    if (!userInput || typeof userInput !== 'string') return [];

    const lowerInput = userInput.toLowerCase();
    const categoryScores = {};

    for (const [categoryName, category] of Object.entries(TOOL_CATEGORIES)) {
        const matchCount = category.keywords.filter(kw => lowerInput.includes(kw)).length;
        if (matchCount > 0) categoryScores[categoryName] = matchCount;
    }

    if (Object.keys(categoryScores).length === 0) {
        logger.debug('ToolRouter', 'No categories matched — pure chat mode');
        return { tools: [], categoryScores: {} };
    }

    const sortedCategories = Object.entries(categoryScores).sort((a, b) => b[1] - a[1]);
    const selectedTools = new Set();
    for (const [categoryName] of sortedCategories) {
        TOOL_CATEGORIES[categoryName].tools.forEach(t => selectedTools.add(t));
    }

    const limitedTools = Array.from(selectedTools).slice(0, 5);
    
    logger.debug('ToolRouter', `Category scores: ${JSON.stringify(categoryScores)} -> Tools: [${limitedTools.join(', ')}]`);
    
    return { tools: limitedTools, categoryScores };
}

function getFilteredToolDefinitions(toolNames) {
    if (!toolNames || toolNames.length === 0) return [];
    
    const allDefs = registry.getToolDefinitions();
    return allDefs.filter(def => {
        const name = (def.function || def).name;
        return toolNames.includes(name);
    });
}

const STALE_KNOWLEDGE_KEYWORDS = [
    'presiden', 'wakil presiden', 'menteri', 'gubernur', 'walikota', 'bupati',
    'ceo', 'direktur utama', 'ketua umum', 'kapolri', 'panglima',
    'harga', 'kurs', 'nilai tukar', 'saham',
    'saat ini', 'sekarang', 'terbaru', 'terkini'
];

function requiresForcedWebSearch(userInput) {
    const lower = userInput.toLowerCase();
    return STALE_KNOWLEDGE_KEYWORDS.some(kw => lower.includes(kw));
}

/**
 * Helper kecil untuk mengirim event trace ke UI (jika callback disediakan).
 * Dipanggil di setiap tahap penting pipeline. Aman dipanggil meski
 * onTraceCallback null/undefined (no-op).
 */
function emitTrace(onTraceCallback, step) {
    if (typeof onTraceCallback === 'function') {
        try {
            onTraceCallback({ timestamp: Date.now(), ...step });
        } catch (e) {
            logger.error('Agent.trace', `Gagal emit trace: ${e.message}`);
        }
    }
}

// ===================== AGENT CLASS =====================

class JarvisAgent {
    constructor() {
        this.model = new ChatOllama({
            model: "qwen2.5:7b",
            temperature: 0.1,
            num_ctx: 32000,
        });

        this.visionModel = new ChatOllama({
            model: "llava:7b",
            temperature: 0.1,
            num_ctx: 8000,
        });
        
        this.chatHistory = [];
        this.maxChatHistory = 15;
        this.isCompacting = false;
        this.currentState = "Menunggu perintah pengguna (Idle)"; 
        this.lastToolOutput = null;
        this.lastTool = null;
        this.lastQuery = null;
        this.createdFilesInSession = new Set();

        // ID percakapan aktif saat ini. Jika null, agent berjalan
        // dalam mode "tanpa persistence" (backward-compatible, chatHistory
        // cuma di RAM seperti versi lama) — supaya kode lama yang belum
        // sempat kirim conversationId tidak langsung rusak.
        this.activeConversationId = null;
        
        logger.info('JarvisAgent', 'Agent initialized with Ollama model: qwen2.5:7b');
    }

    updateState(newState) {
        this.currentState = newState;
        logger.debug('JarvisAgent', `State updated: "${newState}"`);
    }

    /**
     * Ganti percakapan aktif — load history dari disk ke this.chatHistory.
     * Dipanggil dari main.js saat user klik percakapan lain di sidebar,
     * atau saat mulai percakapan baru.
     */
    switchConversation(conversationId) {
        if (!conversationId) {
            this.activeConversationId = null;
            this.chatHistory = [];
            return;
        }
        const conv = conversationManager.loadConversation(conversationId);
        if (!conv) {
            logger.warn('JarvisAgent', `Percakapan ${conversationId} tidak ditemukan, mulai kosong.`);
            this.activeConversationId = conversationId;
            this.chatHistory = [];
            return;
        }
        this.activeConversationId = conversationId;
        this.chatHistory = conv.messages || [];
        logger.info('JarvisAgent', `Beralih ke percakapan ${conversationId} (${this.chatHistory.length} pesan).`);
    }

    /**
     * Simpan chatHistory saat ini ke disk, jika ada percakapan aktif.
     */
    _persistConversation() {
        if (!this.activeConversationId) return;
        try {
            conversationManager.saveConversation(this.activeConversationId, this.chatHistory);
        } catch (e) {
            logger.error('JarvisAgent', `Gagal menyimpan percakapan: ${e.message}`);
        }
    }

    async _unloadModel(modelName) {
        try {
            await axios.post('http://127.0.0.1:11434/api/generate', {
                model: modelName,
                keep_alive: 0
            });
            logger.debug('VRAM_Manager', `Model ${modelName} unloaded to free VRAM.`);
        } catch (e) {
            logger.error('VRAM_Manager', `Gagal unload model ${modelName}: ${e.message}`);
        }
    }

    async _extractFactsBackground(userInput) {
        try {
            if (isSensitiveContent(userInput)) {
                logger.debug('FactExtractor', 'Input mengandung kata sensitif, dilewati demi keamanan.');
                return;
            }

            const prompt = `Ekstrak fakta permanen tentang pengguna dari pesan ini (jika ada). 
            Jika tidak ada informasi penting permanen (seperti nama, hobi, pekerjaan, preferensi), kembalikan tepat kata "NONE" tanpa tanda kutip.
Pesan: "${userInput}"`;

            const response = await this.model.invoke([{ role: 'user', content: prompt }]);
            const result = (response.content || "").trim();

            if (result && result !== "NONE" && result.length > 0 && !isSensitiveContent(result)) {
                const memory_manager = require('./memory_manager');
                memory_manager.addFacts(result);
                logger.debug('FactExtractor', `Fakta baru ditemukan: ${result}`);
            } else if (isSensitiveContent(result)) {
                logger.debug('FactExtractor', 'Hasil ekstraksi mengandung kata sensitif, dilewati demi keamanan.');
            }
        } catch (e) {
            logger.error('FactExtractor', 'Gagal mengekstrak fakta: ' + e.message);
        }
    }

    async _compactHistory() {
        if (this.isCompacting || this.chatHistory.length <= 10) return;
        this.isCompacting = true;

        try {
            const toCompact = this.chatHistory.slice(0, 4);
            const conversationText = toCompact.map(m => `${m.role}: ${m.content}`).join('\n');
            const prompt = `Buatlah ringkasan singkat tapi padat dari 4 pesan percakapan berikut:\n${conversationText}\n\nRingkasan harus mempertahankan konteks utama dan informasi penting. JANGAN menjawab percakapan tersebut, cukup ringkas saja.`;

            logger.debug('AutoCompaction', 'Memulai peringkasan background...');
            const response = await this.model.invoke([{ role: 'user', content: prompt }]);
            const summary = (response.content || "").trim();

            if (summary) {
                this.chatHistory.splice(0, 4, { role: 'system', content: `[Ringkasan percakapan sebelumnya]: ${summary}` });
                logger.info('AutoCompaction', 'Berhasil meringkas history chat.');
                this._persistConversation();
            }
        } catch (e) {
            logger.error('AutoCompaction', 'Gagal meringkas history: ' + e.message);
        } finally {
            this.isCompacting = false;
        }
    }

    cleanInput(input) {
        let cleaned = input.trim();
        cleaned = cleaned.replace(/^(bisa\s+(kamu|anda|kak)\s+)/i, '');
        cleaned = cleaned.replace(/^(tolong\s+(kamu|anda|kak)?\s*)/i, '');
        cleaned = cleaned.replace(/^(kak\s+)/i, '');
        cleaned = cleaned.replace(/^(coba\s+(kamu|anda)?\s*)/i, '');
        cleaned = cleaned.replace(/^((saya|aku)\s+(mau|ingin|minta)\s+)/i, '');
        return cleaned.trim();
    }

    /**
     * One-Shot Router with Dynamic Tool Routing + Micro ReAct
     * UPDATE: sekarang menerima onTraceCallback untuk mengirim
     * langkah-langkah detail (Thinking Process) ke UI.
     */
    async _executePipeline(userInput, { onTokenCallback = null, onTraceCallback = null, startTime = null, retryCount = 0 } = {}) {
        const t0 = startTime || Date.now();

        if (retryCount === 0) {
            await this._unloadModel("llava:7b");
        }

        try {
            const cleanedInput = this.cleanInput(userInput);
            
            if (retryCount === 0) {
                this.chatHistory.push({ role: 'user', content: cleanedInput });
                if (this.chatHistory.length > this.maxChatHistory) this.chatHistory.shift();
            }

            // B. Dynamic Tool Routing
            const routingResult = determineRelevantTools(cleanedInput);
            const relevantToolNames = routingResult.tools;
            const filteredToolDefs = getFilteredToolDefinitions(relevantToolNames);

            emitTrace(onTraceCallback, {
                type: 'routing',
                retryAttempt: retryCount,
                categoryScores: routingResult.categoryScores,
                toolsConsidered: relevantToolNames
            });

            const systemPrompt = _prompt.buildSystemPrompt(filteredToolDefs, this.currentState);
            
            const messages = [
                { role: 'system', content: systemPrompt },
                ...this.chatHistory
            ];

            // D. Panggil Ollama API
            let aiOutput = "";
            try {
                if (onTokenCallback) {
                    onTokenCallback("Memproses...\n");
                    const stream = await this.model.stream(messages);
                    for await (const chunk of stream) {
                        aiOutput += (chunk.content || "");
                        // Add reasoning trace in real-time
                        emitTrace(onTraceCallback, { type: 'reasoning', content: aiOutput });
                    }
                } else {
                    const response = await this.model.invoke(messages);
                    aiOutput = (response.content || "").trim();
                }
            } catch (e) {
                logger.logError('Agent.callLLM', e);
                const msg = "❌ Maaf, gagal memanggil model AI.";
                if (onTokenCallback) onTokenCallback(msg);
                emitTrace(onTraceCallback, { type: 'error', message: 'Gagal memanggil model AI' });
                return msg;
            }

            this.chatHistory.push({ role: 'assistant', content: aiOutput });
            if (this.chatHistory.length > this.maxChatHistory) this.chatHistory.shift();

            const parseResult = json_validator.parseAndValidateAIOutput(aiOutput);
            
            let toolsToExecute = [];
            if (!parseResult.success) {
                const cleaned = aiOutput.replace(/^["'\s]+|["'\s]+$/g, '');
                if (onTokenCallback) onTokenCallback(cleaned);
                emitTrace(onTraceCallback, { type: 'chat_response', retryAttempt: retryCount });
                logger.jarvis(`${cleaned.substring(0, 200)} (${Date.now() - t0}ms)`);
                this._persistConversation();
                return cleaned;
            } else {
                toolsToExecute = parseResult.data;
            }

            const SYNTHESIS_REQUIRED_TOOLS = ['search_web', 'read_webpage', 'research_and_summarize', 'save_memory', 'search_memory'];
            let needsSynthesis = false;
            let rawSynthesisData = "";
            let finalOutput = "";

            if (toolsToExecute.length === 1 && toolsToExecute[0].tool === 'chat') {
                let query = toolsToExecute[0].query;
                
                if (requiresForcedWebSearch(cleanedInput)) {
                    logger.warn('StaleKnowledgeGuard', `Model coba jawab langsung untuk query rawan-basi: "${cleanedInput}". Override ke search_web.`);
                    emitTrace(onTraceCallback, { type: 'stale_knowledge_override', originalTool: 'chat', overrideTo: 'search_web' });
                    toolsToExecute[0].tool = 'search_web';
                    toolsToExecute[0].query = cleanedInput;
                } else {
                    if (onTokenCallback) onTokenCallback(query);
                    emitTrace(onTraceCallback, { type: 'chat_response', retryAttempt: retryCount });
                    logger.jarvis(`${query.substring(0, 200)} (${Date.now() - t0}ms)`);
                    this._persistConversation();
                    return query;
                }
            }

            const toolNames = toolsToExecute.map(t => t.tool).join(', ');
            if (onTokenCallback) onTokenCallback(`Menjalankan: ${toolNames}...\n`);
            emitTrace(onTraceCallback, {
                type: 'tool_call',
                retryAttempt: retryCount,
                tools: toolsToExecute.map(t => ({ tool: t.tool, query: t.query }))
            });

            const executionPromises = toolsToExecute.map(async (tObj) => {
                const tName = tObj.tool;
                const tQuery = tObj.query;

                // ===== INTERCEPT: create_file jadi mode DRAFT =====
                // Tidak menulis ke disk langsung. Parse "filename|content",
                // kirim ke Code Preview via trace, tunggu konfirmasi user
                // lewat IPC terpisah (confirm-save-file) di main.js.
                if (tName === 'create_file') {
                    const sepIndex = tQuery.indexOf('|');
                    if (sepIndex === -1) {
                        return {
                            tool: tName,
                            success: false,
                            error: 'Format salah. Query create_file harus "namafile|isi_konten".'
                        };
                    }
                    const filename = tQuery.substring(0, sepIndex).trim();
                    const content = tQuery.substring(sepIndex + 1);

                    emitTrace(onTraceCallback, {
                        type: 'file_draft',
                        filename,
                        content
                    });

                    return {
                        tool: tName,
                        success: true,
                        data: `📄 Draft file **${filename}** siap ditinjau di Code Preview. Cek panel di kanan, edit jika perlu, lalu klik **Simpan** untuk menulis permanen, atau **Batalkan** untuk membuang draft ini.`,
                        error: null
                    };
                }

                try {
                    const execResult = await registry.execute(tName, { query: tQuery });

                    // read_file berhasil -> tampilkan juga isinya di Code Preview
                    // (read-only, tidak butuh konfirmasi karena tidak mengubah apa pun)
                    if (tName === 'read_file' && execResult.success) {
                        emitTrace(onTraceCallback, {
                            type: 'file_view',
                            filename: tQuery,
                            content: execResult.data
                        });
                    }

                    return {
                        tool: tName,
                        success: execResult.success,
                        data: execResult.success ? execResult.data : null,
                        error: execResult.success ? null : execResult.error
                    };
                } catch (execError) {
                    return {
                        tool: tName,
                        success: false,
                        error: execError.message || String(execError)
                    };
                }
            });

            const results = await Promise.all(executionPromises);

            emitTrace(onTraceCallback, {
                type: 'tool_result',
                retryAttempt: retryCount,
                results: results.map(r => ({ tool: r.tool, success: r.success, error: r.error || null }))
            });
            
            let errorCount = 0;
            let lastError = "";

            for (const res of results) {
                const isError = !res.success || (typeof res.data === 'string' && res.data.startsWith('❌'));
                
                if (isError) {
                    errorCount++;
                    lastError = res.error || (typeof res.data === 'string' ? res.data.replace(/^❌\s*/, '') : 'Unknown error');
                    finalOutput += `❌ Gagal eksekusi ${res.tool}: ${lastError}\n`;
                } else {
                    if (SYNTHESIS_REQUIRED_TOOLS.includes(res.tool) && typeof res.data === 'string') {
                        needsSynthesis = true;
                        rawSynthesisData += `\n--- Hasil dari ${res.tool} ---\n${res.data}\n`;
                    } else {
                        if (typeof res.data === 'string') {
                            finalOutput += `${res.data}\n`;
                        } else {
                            finalOutput += `✅ ${res.tool} dieksekusi.\n`;
                        }
                    }
                }
            }

            if (errorCount > 0 && errorCount === results.length) {
                if (retryCount < 1) {
                    logger.warn('MicroReAct', `Semua tool gagal. Injecting feedback & retrying (retryCount=${retryCount})...`);
                    emitTrace(onTraceCallback, { type: 'retry', attempt: retryCount + 1, reason: lastError });
                    const feedbackPrompt = json_validator.generateFeedbackMessage(aiOutput, lastError);
                    this.chatHistory.push({ role: 'user', content: feedbackPrompt });
                    
                    if (this.chatHistory.length > this.maxChatHistory) this.chatHistory.shift();
                    
                    return await this._executePipeline(userInput, {
                        onTokenCallback,
                        onTraceCallback,
                        startTime: t0,
                        retryCount: retryCount + 1
                    });
                } else {
                    const fallbackMsg = `Maaf, saya tidak dapat menyelesaikan perintah Anda: ${lastError}`;
                    logger.warn('MicroReAct', `Final fallback after ${retryCount} retries.`);
                    emitTrace(onTraceCallback, { type: 'final_fallback', reason: lastError });
                    if (onTokenCallback) onTokenCallback(fallbackMsg);
                    this._persistConversation();
                    return fallbackMsg;
                }
            }

            if (needsSynthesis) {
                if (onTokenCallback) onTokenCallback('\nMerangkum hasil...\n');
                emitTrace(onTraceCallback, { type: 'synthesis_start' });

                const synthesisPrompt = `Berikut hasil mentah dari tool untuk query "${cleanedInput}":

${rawSynthesisData}

Tugas Anda:
1. Rangkum informasi dari hasil mentah di atas dengan DETAIL dan LENGKAP.
2. Jawab langsung dalam bahasa natural, BUKAN format JSON.
3. Jika hasil pencarian tidak relevan, katakan terus terang bahwa informasi yang ditemukan kurang relevan/kurang update.`;

                try {
                    const currentTime = new Date().toLocaleString('id-ID', {
                        timeZone: 'Asia/Jakarta',
                        weekday: 'long',
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit'
                    });
                    const synthesisResponse = await this.model.invoke([
                        { role: 'system', content: _prompt.PERSONA + '\n\n' + _prompt.GENERAL_ANSWER_RULES + `\n\nWaktu sistem saat ini: ${currentTime} WIB.` },
                        { role: 'user', content: synthesisPrompt }
                    ]);
                    const synthesized = (synthesisResponse.content || '').trim();

                    // Hilangkan finalOutput (yang isinya "✅ search_web dieksekusi") 
                    // agar chat tidak kotor dengan log eksekusi. Cukup kirim synthesized.
                    finalOutput = synthesized;
                    
                    if (onTokenCallback) onTokenCallback(finalOutput);
                    emitTrace(onTraceCallback, { type: 'done', retryAttempt: retryCount });
                    logger.jarvis(`[synthesized] ${synthesized.substring(0, 200)} (${Date.now() - t0}ms)`);
                    this._persistConversation();
                    return finalOutput;
                } catch (synthErr) {
                    logger.error('Agent.synthesis', synthErr);
                    const fallbackSynthesis = rawSynthesisData.substring(0, 500) + '... (Synthesis failed)';
                    if (onTokenCallback) onTokenCallback(fallbackSynthesis);
                    emitTrace(onTraceCallback, { type: 'error', message: 'Synthesis gagal' });
                    this._persistConversation();
                    return fallbackSynthesis;
                }
            }

            if (onTokenCallback) onTokenCallback(finalOutput.trim());
            emitTrace(onTraceCallback, { type: 'done', retryAttempt: retryCount });
            logger.jarvis(`${finalOutput.substring(0, 200)} (${Date.now() - t0}ms)`);
            this._persistConversation();
            return finalOutput.trim();

        } catch (error) {
            logger.logError('Agent.router', error);
            const msg = `⚠️ System Exception: ${error.message}`;
            if (onTokenCallback) onTokenCallback(msg);
            emitTrace(onTraceCallback, { type: 'error', message: error.message });
            return msg;
        } finally {
            this.createdFilesInSession.clear();
        }
    }

    async _executeVision(userInput, imageBase64, onTokenCallback) {
        this.updateState('Menganalisis gambar...');
        
        await this._unloadModel("qwen2.5:7b");
        
        try {
            const promptText = userInput || "Tolong jelaskan secara detail apa yang ada di gambar ini.";
            const messages = [
                {
                    role: 'user',
                    content: [
                        { type: 'text', text: promptText },
                        { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${imageBase64}` } }
                    ]
                }
            ];

            const response = await this.visionModel.invoke(messages);
            const content = (response.content || "").trim();
            
            if (onTokenCallback) {
                onTokenCallback(content);
            }
            logger.jarvis(`[Vision] ${content}`);
            
            this.chatHistory.push({ role: 'user', content: `[User mengirim gambar] ${promptText}` });
            this.chatHistory.push({ role: 'assistant', content });
            this._persistConversation();
            
            return content;
        } catch (error) {
            logger.error('Agent.vision', error);
            const msg = `❌ Gagal menganalisis gambar: pastikan model 'llava:7b' sudah terinstal di Ollama. Error: ${error.message}`;
            if (onTokenCallback) onTokenCallback(msg);
            return msg;
        } finally {
            this.updateState('idle');
            await this._unloadModel("llava:7b");
        }
    }

    /**
     * Proses input tanpa streaming.
     * UPDATE: menerima conversationId (opsional) dan onTraceCallback (opsional).
     */
    async processInput(payload, conversationId = null, onTraceCallback = null) {
        let userInput = payload;
        let imageBase64 = null;
        
        if (typeof payload === 'object' && payload !== null) {
            userInput = payload.text || "";
            imageBase64 = payload.image;
        }

        if (conversationId && conversationId !== this.activeConversationId) {
            this.switchConversation(conversationId);
        }

        logger.user(userInput || "[Image Upload]");
        this._extractFactsBackground(userInput);

        if (imageBase64) {
            const res = await this._executeVision(userInput, imageBase64, null);
            this._compactHistory();
            return res;
        }

        const res = await this._executePipeline(userInput, { onTokenCallback: null, onTraceCallback });
        this._compactHistory();
        return res;
    }

    /**
     * Proses input dengan streaming.
     * UPDATE: menerima conversationId (opsional) dan onTraceCallback (opsional).
     */
    async processInputStream(payload, onTokenCallback, conversationId = null, onTraceCallback = null) {
        let userInput = payload;
        let imageBase64 = null;
        
        if (typeof payload === 'object' && payload !== null) {
            userInput = payload.text || "";
            imageBase64 = payload.image;
        }

        if (conversationId && conversationId !== this.activeConversationId) {
            this.switchConversation(conversationId);
        }

        logger.user(userInput || "[Image Upload]");
        this._extractFactsBackground(userInput);

        if (imageBase64) {
            const res = await this._executeVision(userInput, imageBase64, onTokenCallback);
            this._compactHistory();
            return res;
        }

        const res = await this._executePipeline(userInput, { onTokenCallback, onTraceCallback });
        this._compactHistory();
        return res;
    }
}

const agentInstance = new JarvisAgent();
module.exports = agentInstance;
module.exports._determineRelevantTools = determineRelevantTools;