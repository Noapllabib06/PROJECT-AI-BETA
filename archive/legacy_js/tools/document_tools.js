/**
 * src/tools/document_tools.js
 * Utilitas untuk membaca dokumen (PDF/Docx), mencari secara semantik (RAG) di Obsidian Vault, dan melakukan OCR.
 */

const fs = require('fs');
const path = require('path');
const pdfParse = require('pdf-parse');
const mammoth = require('mammoth');
const Tesseract = require('tesseract.js');
const { OllamaEmbeddings } = require('@langchain/ollama');
const logger = require('../utils/logger');

// 1. Helper: Ekstraktor Teks
async function extractTextFromFile(filePath) {
    const ext = path.extname(filePath).toLowerCase();
    if (!fs.existsSync(filePath)) {
        throw new Error(`File tidak ditemukan: ${filePath}`);
    }

    if (ext === '.pdf') {
        const dataBuffer = fs.readFileSync(filePath);
        const data = await pdfParse(dataBuffer);
        return data.text;
    } else if (ext === '.docx') {
        const result = await mammoth.extractRawText({ path: filePath });
        return result.value;
    } else if (ext === '.md' || ext === '.txt') {
        return fs.readFileSync(filePath, 'utf8');
    } else {
        throw new Error(`Format file tidak didukung: ${ext}`);
    }
}

// 2. Helper: Text Splitter & Cosine Similarity (Pure JS)
function chunkText(text, chunkSize = 1000, chunkOverlap = 200) {
    const chunks = [];
    let i = 0;
    while (i < text.length) {
        chunks.push(text.substring(i, i + chunkSize));
        i += (chunkSize - chunkOverlap);
    }
    return chunks;
}

function cosineSimilarity(vecA, vecB) {
    let dotProduct = 0;
    let normA = 0;
    let normB = 0;
    for (let i = 0; i < vecA.length; i++) {
        dotProduct += vecA[i] * vecB[i];
        normA += vecA[i] * vecA[i];
        normB += vecB[i] * vecB[i];
    }
    if (normA === 0 || normB === 0) return 0;
    return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
}

async function performSemanticSearch(query, docsArray, topK = 3) {
    const embeddings = new OllamaEmbeddings({ model: 'nomic-embed-text' });
    
    // Embed query
    const queryVector = await embeddings.embedQuery(query);
    
    // Embed semua chunks
    const textsToEmbed = docsArray.map(d => d.content);
    const docVectors = await embeddings.embedDocuments(textsToEmbed);
    
    const scores = [];
    for (let i = 0; i < docVectors.length; i++) {
        const score = cosineSimilarity(queryVector, docVectors[i]);
        scores.push({ doc: docsArray[i], score });
    }
    
    scores.sort((a, b) => b.score - a.score);
    return scores.slice(0, topK);
}

// 3. Fungsi RAG / Semantic Search di File
async function documentRagTool(filePath, query) {
    try {
        const absolutePath = path.resolve(filePath);
        logger.info('documentRagTool', `Mengekstrak teks dari: ${absolutePath}`);
        
        const rawText = await extractTextFromFile(absolutePath);
        const chunks = chunkText(rawText, 1000, 200);
        
        const docsArray = chunks.map(c => ({ content: c, source: absolutePath }));
        const results = await performSemanticSearch(query, docsArray, 3);
        
        let report = `📄 **Hasil RAG Pencarian Dokumen**\n`;
        report += `File: \`${path.basename(absolutePath)}\`\n`;
        report += `Pertanyaan: *${query}*\n\n`;
        
        if (results.length === 0 || results[0].score < 0.3) {
            report += `❌ Tidak ditemukan informasi yang sangat relevan di dalam dokumen.`;
        } else {
            results.forEach((res, i) => {
                report += `**Kutipan ${i + 1} (Score: ${res.score.toFixed(2)}):**\n> ${res.doc.content.replace(/\n/g, ' ')}\n\n`;
            });
        }
        
        return report;
    } catch (e) {
        logger.error('documentRagTool', e);
        return `❌ Gagal memproses dokumen: ${e.message}`;
    }
}

// 4. Fungsi Semantic Search untuk Obsidian Vault
async function obsidianSearchTool(vaultPath, query) {
    try {
        let targetVault = vaultPath;
        if (!targetVault) {
            targetVault = path.join(process.env.USERPROFILE || process.env.HOME, 'Documents', 'Obsidian');
        }
        
        if (!fs.existsSync(targetVault)) {
            return `❌ Obsidian Vault tidak ditemukan di: ${targetVault}`;
        }
        
        logger.info('obsidianSearchTool', `Memindai vault di: ${targetVault}`);
        
        const mdFiles = [];
        const scanDir = (dir) => {
            const files = fs.readdirSync(dir);
            for (const file of files) {
                const fullPath = path.join(dir, file);
                const stat = fs.statSync(fullPath);
                if (stat.isDirectory() && !file.startsWith('.')) {
                    scanDir(fullPath);
                } else if (file.endsWith('.md')) {
                    mdFiles.push(fullPath);
                }
            }
        };
        
        scanDir(targetVault);
        
        if (mdFiles.length === 0) {
            return `❌ Tidak ada file markdown di dalam Vault: ${targetVault}`;
        }
        
        const maxFiles = Math.min(mdFiles.length, 100);
        const docsArray = [];
        for (let i = 0; i < maxFiles; i++) {
            const content = fs.readFileSync(mdFiles[i], 'utf8');
            const chunks = chunkText(content, 500, 100);
            chunks.forEach(c => {
                docsArray.push({ content: c, source: mdFiles[i] });
            });
        }
        
        const results = await performSemanticSearch(query, docsArray, 4);
        
        let report = `📓 **Hasil Pencarian Semantic Obsidian Vault**\n`;
        report += `Query: *${query}*\n\n`;
        
        if (results.length === 0 || results[0].score < 0.3) {
            report += `❌ Tidak ditemukan catatan relevan.`;
        } else {
            results.forEach((res, i) => {
                const filename = path.basename(res.doc.source);
                report += `**Dari file [${filename}]:**\n> ${res.doc.content.replace(/\n/g, ' ')}\n\n`;
            });
        }
        
        return report;
        
    } catch (e) {
        logger.error('obsidianSearchTool', e);
        return `❌ Gagal mencari di Obsidian Vault: ${e.message}`;
    }
}

// 5. Fungsi OCR dengan Tesseract
async function ocrImageTool(imagePath) {
    try {
        const absolutePath = path.resolve(imagePath);
        if (!fs.existsSync(absolutePath)) {
            return `❌ File gambar tidak ditemukan: ${absolutePath}`;
        }
        
        logger.info('ocrImageTool', `Menjalankan Tesseract OCR pada: ${absolutePath}`);
        
        const result = await Tesseract.recognize(absolutePath, 'eng+ind', {
            logger: m => console.log(`[OCR] ${m.status}: ${Math.round(m.progress * 100)}%`)
        });
        
        const text = result.data.text.trim();
        
        let report = `👁️ **Hasil Ekstraksi Teks (OCR)**\n`;
        report += `File: \`${path.basename(absolutePath)}\`\n\n`;
        if (text) {
            report += `\`\`\`text\n${text}\n\`\`\``;
        } else {
            report += `*Tidak ada teks yang terdeteksi di gambar ini.*`;
        }
        
        return report;
    } catch (e) {
        logger.error('ocrImageTool', e);
        return `❌ Gagal melakukan OCR: ${e.message}`;
    }
}

// ===================== REGISTRY =====================
const documentTools = [
    {
        name: 'read_document_rag',
        description: 'Membaca dan mencari informasi dari dalam file PDF atau DOCX berdasarkan pertanyaan (Semantic Search/RAG).',
        keywords: ['baca pdf', 'baca file', 'baca dokumen', 'cari di pdf', 'isi dokumen', 'jurnal', 'docx'],
        parameters: {
            type: 'object',
            properties: {
                filePath: { type: 'string', description: 'Path absolut ke file PDF atau DOCX' },
                query: { type: 'string', description: 'Pertanyaan atau kata kunci pencarian terkait isi dokumen' }
            },
            required: ['filePath', 'query']
        },
        execute: async (args) => {
            return { success: true, data: await documentRagTool(args.filePath, args.query) };
        }
    },
    {
        name: 'search_obsidian_vault',
        description: 'Mencari catatan atau pengetahuan di dalam Obsidian Vault Anda menggunakan pencarian semantik (makna kalimat).',
        keywords: ['obsidian', 'catatan obsidian', 'cari di obsidian', 'vault', 'baca catatan'],
        parameters: {
            type: 'object',
            properties: {
                query: { type: 'string', description: 'Pertanyaan atau konsep yang ingin dicari' },
                vaultPath: { type: 'string', description: 'Opsional. Path ke direktori Obsidian Vault Anda. Biarkan kosong untuk auto-detect.' }
            },
            required: ['query']
        },
        execute: async (args) => {
            return { success: true, data: await obsidianSearchTool(args.vaultPath, args.query) };
        }
    },
    {
        name: 'ocr_extract_text',
        description: 'Membaca dan mengekstrak teks dari sebuah file gambar (.png, .jpg, hasil scanner) menggunakan Tesseract OCR.',
        keywords: ['baca gambar', 'ekstrak teks', 'teks di gambar', 'ocr', 'tesseract', 'tulisan di foto'],
        parameters: {
            type: 'object',
            properties: {
                imagePath: { type: 'string', description: 'Path absolut ke file gambar' }
            },
            required: ['imagePath']
        },
        execute: async (args) => {
            return { success: true, data: await ocrImageTool(args.imagePath) };
        }
    }
];

module.exports = documentTools;
