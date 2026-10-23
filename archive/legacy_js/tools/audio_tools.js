/**
 * src/tools/audio_tools.js
 * Utilitas untuk memproses Audio (STT & TTS)
 * Membutuhkan instalasi Python: pip install openai-whisper edge-tts
 */

const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');
const logger = require('../utils/logger');

// Eksekusi perintah shell sebagai Promise
function execPromise(command, cwd) {
    return new Promise((resolve, reject) => {
        exec(command, { cwd }, (error, stdout, stderr) => {
            if (error) {
                reject(new Error(stderr || stdout || error.message));
                return;
            }
            resolve(stdout.trim());
        });
    });
}

// 1. Whisper STT (Speech-to-Text)
async function whisperSTTTool(audioPath) {
    try {
        const absolutePath = path.resolve(audioPath);
        if (!fs.existsSync(absolutePath)) {
            return `❌ File audio tidak ditemukan: ${absolutePath}`;
        }
        
        logger.info('whisperSTTTool', `Memproses audio dengan Whisper: ${absolutePath}`);
        
        // Output direktori (di samping file aslinya)
        const outputDir = path.dirname(absolutePath);
        const command = `whisper "${absolutePath}" --model tiny --output_dir "${outputDir}" --output_format txt`;
        
        await execPromise(command);
        
        // Baca file txt hasilnya
        const basename = path.basename(absolutePath, path.extname(absolutePath));
        const txtFile = path.join(outputDir, `${basename}.txt`);
        
        if (fs.existsSync(txtFile)) {
            const text = fs.readFileSync(txtFile, 'utf8');
            return `🎙️ **Hasil Transkripsi Suara (Whisper)**:\n\n"${text.trim()}"`;
        }
        
        return `❌ Transkripsi selesai tapi file teks tidak ditemukan.`;
    } catch (e) {
        logger.error('whisperSTTTool', e);
        return `❌ Gagal menjalankan Whisper. Pastikan Python & openai-whisper sudah terinstal.\nError: ${e.message}`;
    }
}

// 2. Edge-TTS (Text-to-Speech)
async function edgeTTSTool(text) {
    try {
        if (!text) return `❌ Tidak ada teks yang diberikan.`;
        
        logger.info('edgeTTSTool', `Mengubah teks ke suara (TTS)`);
        
        const outputDir = path.join(process.cwd(), 'temp');
        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir);
        }
        
        const timestamp = new Date().getTime();
        const outputPath = path.join(outputDir, `response_${timestamp}.mp3`);
        
        // id-ID-GadisNeural (suara Indonesia perempuan) atau id-ID-ArdiNeural (laki-laki)
        const voice = 'id-ID-GadisNeural';
        // Hapus tanda kutip dari teks agar aman di shell
        const safeText = text.replace(/"/g, '\\"');
        const command = `edge-tts --voice ${voice} --text "${safeText}" --write-media "${outputPath}"`;
        
        await execPromise(command);
        
        // Putar audionya otomatis di Windows
        if (process.platform === 'win32') {
            exec(`start "" "${outputPath}"`);
        }
        
        return `🔊 Suara berhasil di-generate dan sedang diputar (Disimpan di: ${outputPath})`;
    } catch (e) {
        logger.error('edgeTTSTool', e);
        return `❌ Gagal menjalankan TTS. Pastikan Python & edge-tts sudah terinstal (pip install edge-tts).\nError: ${e.message}`;
    }
}

// ===================== REGISTRY =====================
const audioTools = [
    {
        name: 'transcribe_audio',
        description: 'Mendengarkan (transkripsi) file audio/suara menjadi teks menggunakan model AI Whisper.',
        parameters: {
            type: 'object',
            properties: {
                audioPath: { type: 'string', description: 'Path absolut ke file audio (.mp3, .wav, dll)' }
            },
            required: ['audioPath']
        },
        execute: async (args) => {
            return { success: true, data: await whisperSTTTool(args.audioPath) };
        }
    },
    {
        name: 'speak_text',
        description: 'Mengubah teks menjadi suara (Text-to-Speech) agar Jarvis bisa merespons dengan audio.',
        parameters: {
            type: 'object',
            properties: {
                text: { type: 'string', description: 'Teks yang ingin diucapkan oleh Jarvis' }
            },
            required: ['text']
        },
        execute: async (args) => {
            return { success: true, data: await edgeTTSTool(args.text) };
        }
    }
];

module.exports = audioTools;
