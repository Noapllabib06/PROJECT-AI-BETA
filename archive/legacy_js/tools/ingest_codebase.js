/**
 * src/tools/ingest_codebase.js
 * Codebase Ingestion Tool — Indeks direktori kode ke memori vektor RAG
 * Format: Registry Pattern — export array of tool objects
 */

const axios = require('axios');

async function ingestCodebaseTool(directoryPath) {
    try {
        if (!directoryPath || directoryPath.trim().length === 0) {
            return "❌ Path direktori tidak boleh kosong.";
        }

        const response = await axios.post('http://localhost:8000/ingest_directory', {
            directory_path: directoryPath.trim()
        }, {
            timeout: 120000 // Timeout 2 menit untuk proyek besar
        });

        const data = response.data;

        if (data.status === 'success') {
            return `✅ **Berhasil mengindeks direktori!**\n` +
                   `📁 File diproses: **${data.files_processed}** file\n` +
                   `🧩 Chunks diindeks: **${data.chunks_indexed}** chunk\n` +
                   `⏭️  File dilewati: ${data.files_skipped}\n` +
                   `❌ File error: ${data.files_error}\n\n` +
                   `Sekarang Jarvis dapat menjawab pertanyaan seputar kode dalam proyek tersebut.`;
        } else if (data.status === 'warning') {
            return `⚠️ **Peringatan:** ${data.message}\n` +
                   `File diproses: ${data.files_processed}, dilewati: ${data.files_skipped}.`;
        } else {
            return `❌ Gagal mengindeks direktori: ${data.message || 'Respon tidak dikenal dari server.'}`;
        }
    } catch (error) {
        if (error.code === 'ECONNREFUSED') {
            return "❌ Gagal menghubungi Service Memori. Pastikan server `local_memory.py` sudah dijalankan.";
        }
        if (error.response) {
            const status = error.response.status;
            const detail = error.response.data?.detail || 'Unknown error';
            if (status === 404) {
                return `❌ Direktori tidak ditemukan. Pastikan path yang Anda berikan valid. Detail: ${detail}`;
            }
            if (status === 400) {
                return `❌ Path yang diberikan bukan direktori yang valid. Detail: ${detail}`;
            }
            return `❌ Server error (${status}): ${detail}`;
        }
        return `❌ Gagal menjalankan perintah: ${error.message}`;
    }
}

// ===================== REGISTRY TOOLS =====================

const ingestTools = [
    {
        name: "ingest_codebase",
        description: "Mengindeks seluruh file kode dalam sebuah direktori proyek ke dalam memori vektor (RAG). Setelah diindeks, Jarvis bisa menjawab pertanyaan tentang kode di proyek tersebut.",
        parameters: {
            type: "object",
            properties: {
                query: {
                    type: "string",
                    description: "Path absolut atau relatif ke direktori proyek. Contoh: 'C:/Users/Noapllabib/Documents/my-java-project' atau './src'."
                }
            },
            required: ["query"]
        },
        execute: async (args) => {
            const result = await ingestCodebaseTool(args.query || '');
            return { success: true, data: result };
        }
    }
];

// Backward compatibility
ingestTools.ingestCodebaseTool = ingestCodebaseTool;

module.exports = ingestTools;