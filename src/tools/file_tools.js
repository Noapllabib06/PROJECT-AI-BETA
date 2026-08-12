/**
 * src/tools/file_tools.js
 * File System Tools - Create and Read Files
 * Format: Registry Pattern — export array of tool objects
 */
const fs = require('fs');
const path = require('path');
const os = require('os');
const logger = require('../utils/logger');

// ===================== EXPORTED TOOL LOGIC =====================

function createFile(query) {
    logger.tool('createFile', `Creating file: "${query ? query.split('|')[0] : 'N/A'}"`);
    try {
        if (!query || typeof query !== 'string') {
            return "❌ Gagal: Query tidak valid. Gunakan format: nama_file.txt|Isi konten...";
        }
        const pipeIndex = query.indexOf('|');
        let filename, content;
        if (pipeIndex === -1) {
            filename = query.trim();
            content = '';
        } else {
            filename = query.substring(0, pipeIndex).trim();
            content = query.substring(pipeIndex + 1);
        }
        if (!filename) {
            return "❌ Gagal: Nama file tidak boleh kosong.";
        }
        const sanitizedFilename = filename.replace(/[<>:"/\\|?*]/g, '_');
        const desktopPath = path.join(os.homedir(), 'Desktop');
        const filePath = path.join(desktopPath, sanitizedFilename);
        const processedContent = content
            .replace(/\\n/g, '\n')
            .replace(/\\t/g, '\t')
            .replace(/\\\\/g, '\\');
        fs.writeFileSync(filePath, processedContent, 'utf-8');
        const stats = fs.existsSync(filePath) ? fs.statSync(filePath) : null;
        const fileSizeKB = stats ? (stats.size / 1024).toFixed(2) : 0;
        logger.tool('createFile', `File created: ${filePath} (${fileSizeKB} KB)`);
        return `✅ File "${sanitizedFilename}" berhasil dibuat di Desktop (${fileSizeKB} KB).`;
    } catch (error) {
        logger.error('createFile', error);
        return `❌ Gagal membuat file: ${error.message}`;
    }
}

async function readFileTool(query) {
    logger.tool('readFileTool', `Reading file: "${query}"`);
    try {
        let filePath = query.trim();
        if (!filePath) {
            return { success: false, error: "❌ Path file tidak boleh kosong." };
        }
        if (!path.isAbsolute(filePath)) {
            let resolvedPath = path.resolve(process.cwd(), filePath);
            if (!fs.existsSync(resolvedPath)) {
                // Fallback: cek di folder Desktop karena createFile nulis ke Desktop secara default
                const desktopPath = path.join(os.homedir(), 'Desktop');
                const altPath = path.resolve(desktopPath, filePath);
                if (fs.existsSync(altPath)) {
                    filePath = altPath;
                } else {
                    filePath = resolvedPath; // kembalikan untuk pesan error default
                }
            } else {
                filePath = resolvedPath;
            }
        }
        if (!fs.existsSync(filePath)) {
            return { success: false, error: `❌ File tidak ditemukan: ${filePath}` };
        }
        const stats = fs.statSync(filePath);
        if (!stats.isFile()) {
            return { success: false, error: `❌ Path bukan file: ${filePath}` };
        }
        const textExtensions = ['.txt', '.js', '.json', '.md', '.html', '.css', '.xml', '.yaml', '.yml', '.log', '.env', '.py', '.java', '.php', '.rb', '.go', '.rs', '.sh', '.bat', '.sql', '.ts', '.jsx', '.tsx'];
        const ext = path.extname(filePath).toLowerCase();
        if (!textExtensions.includes(ext)) {
            return { success: false, error: `❌ Ekstensi file tidak didukung untuk dibaca: ${ext}` };
        }
        const MAX_SIZE = 3000;
        let content = fs.readFileSync(filePath, 'utf-8');
        if (content.length > MAX_SIZE) {
            content = content.substring(0, MAX_SIZE) + "\n\n... [TEKS DIPOTONG: File terlalu panjang]";
        }
        return { success: true, data: `📄 **Isi File: ${path.basename(filePath)}**\n\`\`\`\n${content}\n\`\`\`` };
    } catch (error) {
        logger.error('readFileTool', error);
        return { success: false, error: `❌ Gagal membaca file: ${error.message}` };
    }
}

// ===================== REGISTRY TOOLS =====================

const fileTools = [
    {
        name: "create_file",
        description: "Membuat file teks baru di Desktop. Gunakan format 'nama_file.txt|Isi konten...' dengan pipe (|) sebagai pemisah. Konten bisa multiline dengan \\n.",
        parameters: {
            type: "object",
            properties: {
                query: {
                    type: "string",
                    description: "Format: 'nama_file.txt|Isi konten...'. Contoh: 'catatan.txt|Ini adalah catatan saya' atau 'resume.txt|Nama: John\\nUsia: 25'."
                }
            },
            required: ["query"]
        },
        execute: async (args) => {
            const result = createFile(args.query || '');
            return { success: true, data: result };
        }
    },
    {
        name: "read_file",
        description: "Membaca isi file teks lokal (txt, js, json, md, html, css, dll). Mendukung path absolut atau relatif. Maksimal 3000 karakter ditampilkan.",
        parameters: {
            type: "object",
            properties: {
                query: {
                    type: "string",
                    description: "Path ke file yang ingin dibaca. Contoh: 'C:/Users/Noapllabib/Desktop/catatan.txt' atau './src/main.js'."
                }
            },
            required: ["query"]
        },
        execute: async (args) => {
            const result = await readFileTool(args.query || '');
            if (result.success) {
                return { success: true, data: result.data };
            }
            return { success: false, error: result.error };
        }
    }
];

// Backward compatibility
fileTools.createFile = createFile;
fileTools.readFileTool = readFileTool;

module.exports = fileTools;