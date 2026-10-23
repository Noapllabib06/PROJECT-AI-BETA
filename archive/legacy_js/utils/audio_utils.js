// src/utils/audio_utils.js
// Fungsi pembantu untuk pengolahan suara (TTS/STT)

/**
 * Text-to-Speech: Mengubah teks menjadi suara
 * @param {string} text - Teks yang akan diucapkan
 * @param {string} lang - Bahasa (default: 'id-ID')
 * @returns {Promise<void>}
 */
function speakText(text, lang = 'id-ID') {
    return new Promise((resolve, reject) => {
        if (!('speechSynthesis' in window)) {
            console.warn('SpeechSynthesis tidak didukung di browser ini.');
            reject(new Error('SpeechSynthesis not supported'));
            return;
        }

        // Hentikan speech yang sedang berlangsung
        window.speechSynthesis.cancel();

        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = lang;
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        utterance.volume = 1.0;

        // Cari suara bahasa Indonesia jika tersedia
        const voices = window.speechSynthesis.getVoices();
        const indonesianVoice = voices.find(voice => voice.lang.startsWith('id'));
        if (indonesianVoice) {
            utterance.voice = indonesianVoice;
        }

        utterance.onend = () => resolve();
        utterance.onerror = (error) => reject(error);

        window.speechSynthesis.speak(utterance);
    });
}

/**
 * Speech-to-Text: Mengubah suara menjadi teks
 * @param {string} lang - Bahasa (default: 'id-ID')
 * @returns {Promise<string>} - Teks hasil transkripsi
 */
function listenSpeech(lang = 'id-ID') {
    return new Promise((resolve, reject) => {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        
        if (!SpeechRecognition) {
            reject(new Error('SpeechRecognition tidak didukung di browser ini.'));
            return;
        }

        const recognition = new SpeechRecognition();
        recognition.lang = lang;
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            resolve(transcript);
        };

        recognition.onerror = (event) => {
            reject(new Error(`Speech recognition error: ${event.error}`));
        };

        recognition.onend = () => {
            // Jika selesai tanpa hasil, reject
            reject(new Error('Tidak ada suara terdeteksi.'));
        };

        recognition.start();
    });
}

/**
 * Deteksi apakah browser mendukung TTS
 * @returns {boolean}
 */
function isTTSSupported() {
    return 'speechSynthesis' in window;
}

/**
 * Deteksi apakah browser mendukung STT
 * @returns {boolean}
 */
function isSTTSupported() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    return !!SpeechRecognition;
}

module.exports = {
    speakText,
    listenSpeech,
    isTTSSupported,
    isSTTSupported
};