/**
 * src/tools/ocr_neural_tool.js
 * Utilitas untuk OCR Tingkat Lanjut menggunakan Model Neural (PaddleOCR) via skrip Python.
 */

const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');
const logger = require('../utils/logger');

// Eksekusi perintah shell sebagai Promise
function execPromise(command, cwd) {
    return new Promise((resolve, reject) => {
        exec(command, { cwd }, (error, stdout, stderr) => {
            // Karena skrip Python kita melempar sys.exit(1) saat error, kita tangkap di sini
            if (error) {
                // Skrip mungkin mencetak ERROR ke stdout atau stderr
                reject(new Error(stdout || stderr || error.message));
                return;
            }
            resolve(stdout.trim());
        });
    });
}

// 1. Neural OCR (PaddleOCR via Python bridge)
async function neuralOCRTool(imagePath) {
    try {
        const absolutePath = path.resolve(imagePath);
        if (!fs.existsSync(absolutePath)) {
            return `❌ File gambar tidak ditemukan: ${absolutePath}`;
        }
        
        logger.info('neuralOCRTool', `Menjalankan Neural OCR (PaddleOCR) pada: ${absolutePath}`);
        
        // Path ke skrip Python
        const scriptPath = path.join(process.cwd(), 'scripts', 'neural_ocr.py');
        const command = `python "${scriptPath}" "${absolutePath}"`;
        
        const text = await execPromise(command);
        
        let report = `🧠 **Hasil Ekstraksi Teks (Neural OCR - Tingkat Lanjut)**\n`;
        report += `File: \`${path.basename(absolutePath)}\`\n\n`;
        
        if (text && !text.includes('Tidak ada teks')) {
            report += `\`\`\`text\n${text}\n\`\`\``;
        } else {
            report += `*Tidak ada teks yang dapat dikenali.*`;
        }
        
        return report;
    } catch (e) {
        logger.error('neuralOCRTool', e);
        return `❌ Gagal menjalankan Neural OCR. Pastikan Python dan PaddleOCR sudah diinstal (pip install paddlepaddle paddleocr).\nError: ${e.message}`;
    }
}

// ===================== REGISTRY =====================
const ocrNeuralTools = [
    {
        name: 'ocr_neural_advanced',
        description: 'Membaca dan mengekstrak teks dari gambar yang rumit (tulisan tangan, nota miring, tata letak kompleks) menggunakan AI Neural OCR (PaddleOCR).',
        parameters: {
            type: 'object',
            properties: {
                imagePath: { type: 'string', description: 'Path absolut ke file gambar' }
            },
            required: ['imagePath']
        },
        execute: async (args) => {
            return { success: true, data: await neuralOCRTool(args.imagePath) };
        }
    }
];

module.exports = ocrNeuralTools;
