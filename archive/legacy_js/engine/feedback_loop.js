/**
 * src/engine/feedback_loop.js
 * Sistem umpan balik untuk koreksi otomatis jika tool execution gagal
 * Memungkinkan AI mengoreksi dirinya sendiri dalam iterasi berikutnya
 */

const logger = require('../utils/logger');

/**
 * Feedback Loop Manager
 * Menangani retry dan feedback ke AI jika terjadi error
 */
class FeedbackLoop {
    constructor(maxRetries = 3) {
        this.maxRetries = maxRetries;
        this.retryCount = 0;
        this.feedbackHistory = [];
    }

    /**
     * Reset retry counter
     */
    reset() {
        this.retryCount = 0;
        this.feedbackHistory = [];
        logger.debug('FeedbackLoop', 'Reset retry counter');
    }

    /**
     * Cek apakah masih bisa retry
     */
    canRetry() {
        return this.retryCount < this.maxRetries;
    }

    /**
     * Tambah feedback ke history
     */
    addFeedback(feedback) {
        this.feedbackHistory.push({
            attempt: this.retryCount + 1,
            feedback: feedback,
            timestamp: new Date().toISOString()
        });
        this.retryCount++;
        logger.warn('FeedbackLoop', `Retry attempt ${this.retryCount}/${this.maxRetries}`);
    }

    /**
     * Generate feedback message untuk AI
     */
    generateFeedbackMessage(error, toolName, query) {
        const feedback = `
⚠️ EKSEKUSI TOOL GAGAL. Perbaiki dan coba lagi.

Tool yang dipanggil: ${toolName}
Query: ${query}

Error: ${error}

INSTRUKSI KOREKSI:
1. Analisis error di atas
2. Perbaiki query atau pilih tool yang lebih sesuai
3. Output HANYA JSON yang sudah diperbaiki

Format: {"tool": "nama_tool", "query": "isi_query_yang_sudah_diperbaiki"}

ATURAN:
- HANYA output JSON, TANPA teks lain
- Jika tool tidak bisa dieksekusi, gunakan "chat" untuk menjelaskan ke user
- Jangan ulangi tool yang sama dengan query yang sama`;

        this.addFeedback(feedback);
        return feedback;
    }

    /**
     * Get feedback history untuk debugging
     */
    getFeedbackHistory() {
        return this.feedbackHistory;
    }

    /**
     * Get current retry count
     */
    getRetryCount() {
        return this.retryCount;
    }

    /**
     * Check if should fallback to chat
     */
    shouldFallbackToChat() {
        return !this.canRetry();
    }
}

/**
 * Process tool execution dengan feedback loop
 * @param {Function} executeTool - Function yang menjalankan tool
 * @param {string} toolName - Nama tool
 * @param {string} query - Query parameter
 * @param {Function} callAI - Function untuk memanggil AI lagi dengan feedback
 * @returns {Promise<{success: boolean, result?: string, error?: string, fallback?: boolean}>}
 */
async function executeWithFeedbackLoop(executeTool, toolName, query, callAI) {
    const feedbackLoop = new FeedbackLoop(3); // Max 3 retries

    while (feedbackLoop.canRetry()) {
        try {
            logger.debug('FeedbackLoop', `Executing tool: ${toolName} (attempt ${feedbackLoop.getRetryCount() + 1})`);
            
            // Execute tool
            const result = await executeTool(toolName, query);
            
            // Check if result indicates error
            if (result && result.includes('❌')) {
                const errorMsg = result;
                logger.warn('FeedbackLoop', `Tool returned error: ${errorMsg.substring(0, 100)}`);
                
                // Generate feedback for AI
                const feedback = feedbackLoop.generateFeedbackMessage(errorMsg, toolName, query);
                
                // Ask AI to correct
                if (feedbackLoop.canRetry()) {
                    logger.info('FeedbackLoop', 'Asking AI to correct the error...');
                    const correctedOutput = await callAI(feedback);
                    
                    // Parse corrected output
                    const { parseAndValidateAIOutput } = require('./json_validator');
                    const validation = parseAndValidateAIOutput(correctedOutput);
                    
                    if (validation.success) {
                        // Update toolName and query with corrected values
                        toolName = validation.data.tool;
                        query = validation.data.query;
                        continue; // Retry with corrected parameters
                    } else {
                        logger.error('FeedbackLoop', 'AI correction failed - invalid output');
                    }
                }
                
                // If we can't retry anymore, return the error
                return {
                    success: false,
                    error: errorMsg,
                    fallback: true
                };
            }
            
            // Success!
            logger.debug('FeedbackLoop', `Tool executed successfully: ${toolName}`);
            return {
                success: true,
                result: result
            };
            
        } catch (error) {
            logger.error('FeedbackLoop', `Tool execution exception: ${error.message}`);
            
            // Generate feedback for AI
            const feedback = feedbackLoop.generateFeedbackMessage(error.message, toolName, query);
            
            // Ask AI to correct
            if (feedbackLoop.canRetry()) {
                try {
                    logger.info('FeedbackLoop', 'Asking AI to correct the exception...');
                    const correctedOutput = await callAI(feedback);
                    
                    // Parse corrected output
                    const { parseAndValidateAIOutput } = require('./json_validator');
                    const validation = parseAndValidateAIOutput(correctedOutput);
                    
                    if (validation.success) {
                        // Update toolName and query with corrected values
                        toolName = validation.data.tool;
                        query = validation.data.query;
                        continue; // Retry with corrected parameters
                    }
                } catch (callAIError) {
                    logger.error('FeedbackLoop', `Failed to get AI correction: ${callAIError.message}`);
                }
            }
            
            // If we can't retry anymore, return the error
            return {
                success: false,
                error: `Gagal menjalankan perintah setelah ${feedbackLoop.getRetryCount()} percobaan: ${error.message}`,
                fallback: true
            };
        }
    }

    // Should not reach here, but just in case
    return {
        success: false,
        error: 'Gagal menjalankan perintah. Silakan coba dengan perintah yang berbeda.',
        fallback: true
    };
}

module.exports = {
    generateErrorFeedback: (toolName, errorMessage) => {
        return `[SYSTEM FEEDBACK: INTERNAL ERROR RECOVERY]
The previous attempt to use the tool '${toolName}' failed with the following error: "${errorMessage}".

Your task is to recover from this error. Please choose one of the following actions:
1. Try a DIFFERENT tool that might achieve the same goal.
2. Try the SAME tool but with DIFFERENT, more precise, or simplified parameters.
3. If the action is impossible, use the 'chat' tool to politely inform the user about the limitation.

CRITICAL: Do not repeat the exact same tool call. Respond ONLY with a valid JSON object.`;
    }
};
