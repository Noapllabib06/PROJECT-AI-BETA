/**
 * src/engine/conversation_manager.js
 * Conversation Manager — Mengelola banyak percakapan terpisah,
 * masing-masing tersimpan sebagai file JSON individual di disk.
 *
 * Setiap percakapan: { id, title, createdAt, updatedAt, messages: [...] }
 * messages formatnya sama persis dengan chatHistory di agent.js
 * ({ role: 'user'|'assistant'|'system', content: '...' }).
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const logger = require('../utils/logger');

const CONVERSATIONS_DIR = path.join(__dirname, '..', '..', '.jarvis-conversations');

function ensureDir() {
    if (!fs.existsSync(CONVERSATIONS_DIR)) {
        fs.mkdirSync(CONVERSATIONS_DIR, { recursive: true });
    }
}

function filePathFor(id) {
    // Sanitasi dasar — id selalu digenerate internal (crypto.randomUUID),
    // tapi tetap dijaga agar tidak bisa path traversal kalau suatu saat
    // dipanggil dengan id dari luar.
    const safeId = String(id).replace(/[^a-zA-Z0-9-]/g, '');
    return path.join(CONVERSATIONS_DIR, `${safeId}.json`);
}

/**
 * Buat judul singkat otomatis dari pesan pertama user.
 * Sengaja TIDAK memanggil LLM di sini (biar tetap cepat & gratis VRAM) —
 * cukup potong teks pesan pertama.
 */
function generateTitle(firstMessage) {
    if (!firstMessage) return 'Percakapan Baru';
    const cleaned = firstMessage.trim().replace(/\s+/g, ' ');
    if (cleaned.length <= 42) return cleaned;
    return cleaned.substring(0, 42).trim() + '...';
}

function createConversation() {
    ensureDir();
    const id = crypto.randomUUID();
    const now = new Date().toISOString();
    const conversation = {
        id,
        title: 'Percakapan Baru',
        createdAt: now,
        updatedAt: now,
        messages: []
    };
    fs.writeFileSync(filePathFor(id), JSON.stringify(conversation, null, 2), 'utf8');
    logger.info('ConversationManager', `Percakapan baru dibuat: ${id}`);
    return conversation;
}

function loadConversation(id) {
    ensureDir();
    const fp = filePathFor(id);
    if (!fs.existsSync(fp)) {
        logger.warn('ConversationManager', `Percakapan ${id} tidak ditemukan.`);
        return null;
    }
    try {
        return JSON.parse(fs.readFileSync(fp, 'utf8'));
    } catch (error) {
        logger.error('ConversationManager', `Gagal membaca percakapan ${id}: ${error.message}`);
        return null;
    }
}

/**
 * Simpan/update percakapan. Judul otomatis di-generate dari pesan
 * pertama HANYA jika judul masih default ("Percakapan Baru") —
 * supaya tidak menimpa judul yang mungkin sudah di-custom user nanti.
 */
function saveConversation(id, messages, titleOverride = null) {
    ensureDir();
    const existing = loadConversation(id);
    const createdAt = existing?.createdAt || new Date().toISOString();

    let title = existing?.title || 'Percakapan Baru';
    if (titleOverride) {
        title = titleOverride;
    } else if (title === 'Percakapan Baru' && messages.length > 0) {
        const firstUserMsg = messages.find(m => m.role === 'user');
        if (firstUserMsg) title = generateTitle(firstUserMsg.content);
    }

    const conversation = {
        id,
        title,
        createdAt,
        updatedAt: new Date().toISOString(),
        messages
    };

    fs.writeFileSync(filePathFor(id), JSON.stringify(conversation, null, 2), 'utf8');
    return conversation;
}

function deleteConversation(id) {
    ensureDir();
    const fp = filePathFor(id);
    if (fs.existsSync(fp)) {
        fs.unlinkSync(fp);
        logger.info('ConversationManager', `Percakapan ${id} dihapus.`);
        return true;
    }
    return false;
}

/**
 * List semua percakapan, terbaru duluan. Hanya metadata ringan
 * (id, title, timestamp) — TIDAK ikut load semua messages,
 * biar sidebar tetap cepat walau ada ratusan percakapan.
 */
function listConversations() {
    ensureDir();
    const files = fs.readdirSync(CONVERSATIONS_DIR).filter(f => f.endsWith('.json'));

    const summaries = files.map(file => {
        try {
            const data = JSON.parse(fs.readFileSync(path.join(CONVERSATIONS_DIR, file), 'utf8'));
            return {
                id: data.id,
                title: data.title,
                createdAt: data.createdAt,
                updatedAt: data.updatedAt,
                messageCount: (data.messages || []).length
            };
        } catch {
            return null;
        }
    }).filter(Boolean);

    summaries.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
    return summaries;
}

module.exports = {
    createConversation,
    loadConversation,
    saveConversation,
    deleteConversation,
    listConversations,
    generateTitle
};