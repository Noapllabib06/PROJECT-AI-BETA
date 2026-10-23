// src/utils/logger.js
// Logging System Terpusat untuk maintain & debugging Jarvis AI Agent
// Log disimpan di file dan juga bisa ditampilkan di console

const fs = require('fs');
const path = require('path');

// Level log
const LOG_LEVELS = {
    DEBUG: { priority: 0, label: '🐛 DEBUG', color: '\x1b[36m' },
    INFO: { priority: 1, label: 'ℹ️ INFO', color: '\x1b[32m' },
    TOOL: { priority: 2, label: '🔧 TOOL', color: '\x1b[33m' },
    WARN: { priority: 3, label: '⚠️ WARN', color: '\x1b[33m' },
    ERROR: { priority: 4, label: '❌ ERROR', color: '\x1b[31m' },
    USER: { priority: 1, label: '👤 USER', color: '\x1b[36m' },
    JARVIS: { priority: 1, label: '🤖 JARVIS', color: '\x1b[35m' },
};

class JarvisLogger {
    constructor() {
        this.logDir = path.join(__dirname, '..', '..', 'logs');
        this.logFile = path.join(this.logDir, `jarvis-${this.getDateString()}.log`);
        this.minPriority = 0; // Tampilkan semua level
        this.sessionId = Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
        this.logCount = 0;
        
        // Buat folder logs jika belum ada
        if (!fs.existsSync(this.logDir)) {
            fs.mkdirSync(this.logDir, { recursive: true });
        }
        
        // Header log file
        this.writeToFile(`\n\n`);
        this.writeToFile(`╔══════════════════════════════════════════════════╗`);
        this.writeToFile(`║         JARVIS AI AGENT - LOG SESSION           ║`);
        this.writeToFile(`║  Session ID: ${this.sessionId.padEnd(34)}║`);
        this.writeToFile(`║  Date: ${new Date().toLocaleString('id-ID').padEnd(36)}║`);
        this.writeToFile(`║  PID: ${process.pid.toString().padEnd(38)}║`);
        this.writeToFile(`╚══════════════════════════════════════════════════╝`);
        this.writeToFile(`\n`);
        
        this.info('Logger', 'Logging system initialized');
    }

    /**
     * Dapatkan string tanggal untuk nama file
     */
    getDateString() {
        const now = new Date();
        return `${now.getFullYear()}-${(now.getMonth()+1).toString().padStart(2,'0')}-${now.getDate().toString().padStart(2,'0')}`;
    }

    /**
     * Dapatkan timestamp untuk log
     */
    getTimestamp() {
        const now = new Date();
        return now.toTimeString().split(' ')[0] + '.' + now.getMilliseconds().toString().padStart(3, '0');
    }

    /**
     * Format pesan log
     */
    formatLog(level, source, message, data = null) {
        const timestamp = this.getTimestamp();
        const levelInfo = LOG_LEVELS[level] || LOG_LEVELS.INFO;
        let logMsg = `[${timestamp}] [${levelInfo.label}] [${source}] ${message}`;
        
        if (data) {
            try {
                const dataStr = typeof data === 'object' ? JSON.stringify(data, null, 2) : data;
                logMsg += `\n${' '.repeat(10)}└─ Data: ${dataStr}`;
            } catch (e) {
                logMsg += `\n${' '.repeat(10)}└─ Data: [Circular/Error]`;
            }
        }
        
        return { logMsg, timestamp, level, source, message, data };
    }

    /**
     * Tulis ke file log
     */
    writeToFile(text) {
        try {
            fs.appendFileSync(this.logFile, text + '\n', 'utf8');
        } catch (e) {
            console.error(`[LOGGER] Failed to write to log file: ${e.message}`);
        }
    }

    /**
     * Log dengan level tertentu
     */
    log(level, source, message, data = null) {
        const formatted = this.formatLog(level, source, message, data);
        
        // Tulis ke file
        this.writeToFile(formatted.logMsg);
        
        // Tampilkan di console dengan warna
        const levelInfo = LOG_LEVELS[level] || LOG_LEVELS.INFO;
        const reset = '\x1b[0m';
        console.log(`${levelInfo.color}${formatted.logMsg}${reset}`);
        
        this.logCount++;
        
        // Auto-rotate file setiap 1000 logs
        if (this.logCount >= 1000) {
            this.rotateLog();
        }
    }

    /**
     * Rotate log file
     */
    rotateLog() {
        try {
            const oldFile = this.logFile;
            const newFile = path.join(this.logDir, `jarvis-${this.getDateString()}-${this.sessionId}.log`);
            if (fs.existsSync(oldFile)) {
                fs.renameSync(oldFile, newFile);
                console.log(`[LOGGER] Log rotated to: ${newFile}`);
            }
            this.logCount = 0;
            
            // Buat file baru
            this.logFile = path.join(this.logDir, `jarvis-${this.getDateString()}.log`);
            this.writeToFile(`\n[LOG ROTATED - Previous: ${path.basename(newFile)}]\n`);
        } catch (e) {
            console.error(`[LOGGER] Rotate failed: ${e.message}`);
        }
    }

    // === Shortcut methods ===
    debug(source, message, data = null) {
        this.log('DEBUG', source, message, data);
    }

    info(source, message, data = null) {
        this.log('INFO', source, message, data);
    }

    tool(source, message, data = null) {
        this.log('TOOL', source, message, data);
    }

    warn(source, message, data = null) {
        this.log('WARN', source, message, data);
    }

    error(source, message, data = null) {
        this.log('ERROR', source, message, data);
    }

    user(message) {
        this.log('USER', 'User', message);
    }

    jarvis(message) {
        this.log('JARVIS', 'Jarvis', message);
    }

    /**
     * Log eksekusi tool dengan detail
     */
    logToolExecution(toolName, query, result, duration) {
        this.tool('ToolExecutor', `Executed "${toolName}"`, {
            query: query,
            resultLength: result?.length || 0,
            duration: `${duration}ms`,
            success: !result?.startsWith('❌')
        });
    }

    /**
     * Log intent detection
     */
    logIntent(input, detectedTool, query) {
        this.debug('IntentDetector', `Input: "${input.substring(0, 100)}"`, {
            detectedTool,
            query: query?.substring(0, 100)
        });
    }

    /**
     * Log error dengan stack trace
     */
    logError(source, error, context = null) {
        this.error(source, error.message || error, {
            stack: error.stack?.substring(0, 500),
            context
        });
    }
}

// Singleton instance
const logger = new JarvisLogger();

module.exports = logger;