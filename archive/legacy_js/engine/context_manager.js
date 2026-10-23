/**
 * src/engine/context_manager.js
 * Manajemen jendela konteks dengan chunking dan semantic search
 * Mencegah kehabisan memori saat membaca konten panjang
 */

const logger = require('../utils/logger');

/**
 * Context Manager - Mengelola chunks teks untuk hemat context window
 */
class ContextManager {
    constructor(maxChunkSize = 1500, maxContextWindow = 4000) {
        this.maxChunkSize = maxChunkSize; // Ukuran maksimal per chunk (chars)
        this.maxContextWindow = maxContextWindow; // Maksimal teks yang dikirim ke AI
        this.chunks = new Map(); // Store chunks by ID
        this.chunkCounter = 0;
    }

    /**
     * Reset semua chunks
     */
    reset() {
        this.chunks.clear();
        this.chunkCounter = 0;
        logger.debug('ContextManager', 'Reset all chunks');
    }

    /**
     * Split teks panjang menjadi chunks
     * @param {string} text - Teks panjang
     * @param {string} source - Sumber teks (URL atau judul)
     * @returns {Array} Array of chunk objects
     */
    chunkText(text, source = 'unknown') {
        if (!text || text.length <= this.maxChunkSize) {
            // Teks pendek, tidak perlu di-chunk
            return [{
                id: this.generateChunkId(),
                source: source,
                text: text,
                startIndex: 0,
                endIndex: text.length,
                isSummary: true
            }];
        }

        const chunks = [];
        const sentences = text.match(/[^.!?]+[.!?]+/g) || [text];
        let currentChunk = '';
        let startIndex = 0;
        let chunkIndex = 0;

        for (let i = 0; i < sentences.length; i++) {
            const sentence = sentences[i].trim();
            
            // Jika menambahkan sentence ini melebihi maxChunkSize
            if ((currentChunk + ' ' + sentence).length > this.maxChunkSize && currentChunk.length > 0) {
                // Simpan chunk saat ini
                chunks.push({
                    id: this.generateChunkId(),
                    source: source,
                    text: currentChunk.trim(),
                    startIndex: startIndex,
                    endIndex: startIndex + currentChunk.length,
                    isSummary: chunkIndex === 0, // Chunk pertama = summary
                    isConclusion: i === sentences.length - 1 // Chunk terakhir = kesimpulan
                });

                startIndex += currentChunk.length;
                currentChunk = sentence;
                chunkIndex++;
            } else {
                currentChunk += (currentChunk ? ' ' : '') + sentence;
            }
        }

        // Simpan chunk terakhir
        if (currentChunk.trim()) {
            chunks.push({
                id: this.generateChunkId(),
                source: source,
                text: currentChunk.trim(),
                startIndex: startIndex,
                endIndex: startIndex + currentChunk.length,
                isSummary: chunkIndex === 0,
                isConclusion: true
            });
        }

        // Store chunks
        chunks.forEach(chunk => {
            this.chunks.set(chunk.id, chunk);
        });

        logger.debug('ContextManager', `Created ${chunks.length} chunks from ${source} (${text.length} chars)`);
        return chunks;
    }

    /**
     * Generate unique chunk ID
     */
    generateChunkId() {
        this.chunkCounter++;
        return `chunk_${this.chunkCounter}_${Date.now()}`;
    }

    /**
     * Cari chunk yang relevan berdasarkan query (simple keyword matching)
     * @param {string} query - Query pengguna
     * @param {number} maxChunks - Maksimal chunks yang diambil
     * @returns {Array} Array of relevant chunks
     */
    findRelevantChunks(query, maxChunks = 3) {
        if (this.chunks.size === 0) {
            return [];
        }

        const queryWords = query.toLowerCase().split(/\s+/).filter(w => w.length > 2);
        const scoredChunks = [];

        // Score setiap chunk berdasarkan keyword matching
        for (const [id, chunk] of this.chunks) {
            const textLower = chunk.text.toLowerCase();
            let score = 0;

            // Hitung berapa banyak kata query yang muncul di chunk
            for (const word of queryWords) {
                if (textLower.includes(word)) {
                    score += 1;
                }
            }

            // Bonus untuk summary (chunk pertama) dan conclusion (chunk terakhir)
            if (chunk.isSummary) score += 2;
            if (chunk.isConclusion) score += 1;

            if (score > 0) {
                scoredChunks.push({
                    id: chunk.id,
                    text: chunk.text,
                    score: score,
                    source: chunk.source,
                    isSummary: chunk.isSummary,
                    isConclusion: chunk.isConclusion
                });
            }
        }

        // Sort by score (descending)
        scoredChunks.sort((a, b) => b.score - a.score);

        // Ambil top N chunks
        const relevantChunks = scoredChunks.slice(0, maxChunks);

        // Pastikan total chars tidak melebihi maxContextWindow
        let totalChars = 0;
        const selectedChunks = [];
        
        for (const chunk of relevantChunks) {
            if (totalChars + chunk.text.length <= this.maxContextWindow) {
                selectedChunks.push(chunk);
                totalChars += chunk.text.length;
            } else {
                break;
            }
        }

        logger.debug('ContextManager', `Found ${selectedChunks.length} relevant chunks for query: "${query.substring(0, 50)}"`);
        return selectedChunks;
    }

    /**
     * Gabungkan chunks menjadi satu teks untuk AI
     * @param {Array} chunks - Array of chunks
     * @returns {string} Combined text
     */
    combineChunks(chunks) {
        if (chunks.length === 0) {
            return '';
        }

        if (chunks.length === 1) {
            return chunks[0].text;
        }

        // Gabungkan dengan separator
        const texts = chunks.map(chunk => {
            let prefix = '';
            if (chunk.isSummary) prefix = '[RINGKASAN] ';
            if (chunk.isConclusion) prefix = '[KESIMPULAN] ';
            return `${prefix}${chunk.text}`;
        });

        return texts.join('\n\n---\n\n');
    }

    /**
     * Get context untuk AI berdasarkan query
     * @param {string} query - Query pengguna
     * @param {number} maxChunks - Maksimal chunks
     * @returns {string} Context text untuk AI
     */
    getContextForAI(query, maxChunks = 3) {
        const relevantChunks = this.findRelevantChunks(query, maxChunks);
        
        if (relevantChunks.length === 0) {
            return '';
        }

        const combinedText = this.combineChunks(relevantChunks);
        
        // Add source info
        const sources = [...new Set(relevantChunks.map(c => c.source))];
        const sourceInfo = sources.length > 0 ? `\n\n[Sumber: ${sources.join(', ')}]` : '';

        return combinedText + sourceInfo;
    }

    /**
     * Get chunk by ID
     */
    getChunk(id) {
        return this.chunks.get(id) || null;
    }

    /**
     * Get all chunks
     */
    getAllChunks() {
        return Array.from(this.chunks.values());
    }

    /**
     * Get stats
     */
    getStats() {
        return {
            totalChunks: this.chunks.size,
            totalChars: Array.from(this.chunks.values()).reduce((sum, chunk) => sum + chunk.text.length, 0),
            maxChunkSize: this.maxChunkSize,
            maxContextWindow: this.maxContextWindow
        };
    }
}

/**
 * Process web content dengan chunking
 * @param {string} content - Konten web
 * @param {string} source - Sumber (URL)
 * @param {number} maxChunkSize - Ukuran chunk maksimal
 * @returns {Object} { chunks, contextForAI }
 */
function processWebContent(content, source, maxChunkSize = 1500) {
    const contextManager = new ContextManager(maxChunkSize, 4000);
    const chunks = contextManager.chunkText(content, source);
    
    return {
        chunks: chunks,
        contextManager: contextManager,
        stats: contextManager.getStats()
    };
}

/**
 * Process YouTube transcript/description dengan chunking
 * @param {string} transcript - Transkrip/deskripsi video
 * @param {string} videoTitle - Judul video
 * @param {number} maxChunkSize - Ukuran chunk maksimal
 * @returns {Object} { chunks, contextForAI }
 */
function processYouTubeContent(transcript, videoTitle, maxChunkSize = 1500) {
    const contextManager = new ContextManager(maxChunkSize, 4000);
    const chunks = contextManager.chunkText(transcript, videoTitle);
    
    return {
        chunks: chunks,
        contextManager: contextManager,
        stats: contextManager.getStats()
    };
}

module.exports = {
    ContextManager,
    processWebContent,
    processYouTubeContent
};