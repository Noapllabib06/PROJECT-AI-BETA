/**
 * src/tools/git_tools.js
 * Utilitas untuk mengelola repositori Git dan melakukan pemindaian kebocoran kredensial (Security Scan).
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

// ===================== GIT STATUS TOOL =====================
async function gitStatusTool(repoPath) {
    try {
        const targetPath = repoPath || process.cwd();
        
        // Pastikan direktori merupakan repositori git
        if (!fs.existsSync(path.join(targetPath, '.git'))) {
            return `❌ Direktori ${targetPath} bukan repositori Git.`;
        }
        
        const branch = await execPromise('git rev-parse --abbrev-ref HEAD', targetPath);
        const status = await execPromise('git status --short', targetPath);
        
        let report = `🌿 **Git Status (Branch: ${branch})**\n`;
        report += `Lokasi: ${targetPath}\n\n`;
        
        if (!status) {
            report += `✨ Working tree clean. Tidak ada perubahan.`;
        } else {
            report += `Daftar perubahan:\n`;
            const lines = status.split('\n');
            lines.forEach(line => {
                report += `- \`${line}\`\n`;
            });
        }
        
        return report;
    } catch (e) {
        logger.error('gitStatusTool', e);
        return `❌ Gagal menjalankan git status: ${e.message}`;
    }
}

// ===================== GIT SECURITY SCAN TOOL =====================
async function gitSecurityScanTool(repoPath) {
    try {
        const targetPath = repoPath || process.cwd();
        
        if (!fs.existsSync(path.join(targetPath, '.git'))) {
            return `❌ Direktori ${targetPath} bukan repositori Git.`;
        }
        
        // Simple regex pattern untuk mendeteksi potensi kredensial
        // Hanya memindai perubahan yang belum di-commit (staged atau unstaged)
        const diff = await execPromise('git diff HEAD', targetPath);
        
        if (!diff) {
            return `🛡️ **Security Scan:** Tidak ada perubahan kode baru untuk dipindai.`;
        }
        
        const sensitivePatterns = [
            /(?:api[_\-]?key|apikey)["'\s:=]+(["'][a-zA-Z0-9_\-]{10,}["'])/i,
            /(?:password|passwd|pwd)["'\s:=]+(["'][^"']{6,}["'])/i,
            /(?:secret|token|auth)["'\s:=]+(["'][a-zA-Z0-9_\-]{16,}["'])/i,
            /([a-zA-Z0-9_-]+\.pem)/i
        ];
        
        const lines = diff.split('\n');
        const findings = [];
        
        let currentFile = '';
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            
            if (line.startsWith('+++ b/')) {
                currentFile = line.substring(6);
            } else if (line.startsWith('+') && !line.startsWith('+++')) {
                // Periksa setiap baris yang ditambahkan
                const content = line.substring(1);
                
                for (const pattern of sensitivePatterns) {
                    if (pattern.test(content)) {
                        findings.push(`- Terdeteksi potensi kredensial di file **${currentFile}**:\n  \`${content.trim()}\``);
                        break;
                    }
                }
            }
        }
        
        if (findings.length === 0) {
            return `✅ **Security Scan (Pre-commit):** Aman. Tidak terdeteksi adanya hardcoded secret/kredensial pada perubahan saat ini.`;
        } else {
            let report = `🚨 **PERINGATAN SECURITY SCAN** 🚨\n`;
            report += `Ditemukan potensi kebocoran kredensial/rahasia di perubahan yang belum di-commit:\n\n`;
            report += findings.join('\n\n');
            report += `\n\n⚠️ Harap hapus kredensial ini dan gunakan environment variables (.env) sebelum melakukan commit!`;
            return report;
        }
    } catch (e) {
        logger.error('gitSecurityScanTool', e);
        return `❌ Gagal melakukan security scan: ${e.message}`;
    }
}

// ===================== REGISTRY =====================
const gitTools = [
    {
        name: 'git_status',
        description: 'Mengecek status Git (branch, file yang berubah, untracked) dari sebuah repositori.',
        parameters: {
            type: 'object',
            properties: {
                repoPath: { type: 'string', description: 'Path absolut repositori Git. Kosongkan untuk menggunakan direktori saat ini.' }
            }
        },
        execute: async (args) => {
            return { success: true, data: await gitStatusTool(args.repoPath) };
        }
    },
    {
        name: 'git_security_scan',
        description: 'Memindai (scan) repositori Git dari perubahan kode yang belum di-commit untuk mencari kebocoran password, API key, atau token rahasia.',
        parameters: {
            type: 'object',
            properties: {
                repoPath: { type: 'string', description: 'Path absolut repositori Git. Kosongkan untuk menggunakan direktori saat ini.' }
            }
        },
        execute: async (args) => {
            return { success: true, data: await gitSecurityScanTool(args.repoPath) };
        }
    }
];

module.exports = gitTools;
