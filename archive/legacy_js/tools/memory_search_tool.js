const axios = require('axios');
const { OllamaEmbeddings } = require("@langchain/ollama");

// VRAM GUARD: Fungsi unload
async function _unloadModel(modelName) {
    try {
        await axios.post('http://127.0.0.1:11434/api/generate', {
            model: modelName,
            keep_alive: 0
        });
        console.log(`🧠 [VRAM_Manager] Model ${modelName} unloaded.`);
    } catch (e) {
        console.error(`❌ [VRAM_Manager] Gagal unload model ${modelName}:`, e.message);
    }
}

const memorySearchTool = {
    name: "search_memory",
    description: "Gunakan tool ini JIKA pengguna bertanya tentang masa lalu, fakta yang pernah mereka sebutkan, profil mereka, atau jika kamu butuh mengingat konteks sebelumnya.",
    parameters: {
        type: "object",
        properties: {
            query: {
                type: "string",
                description: "Kata kunci, inti pertanyaan, atau topik yang ingin dicari di dalam ingatan."
            }
        },
        required: ["query"]
    },
    execute: async ({ query }) => {
        try {
            console.log(`\n🧠 [Agent] Mencoba mengingat tentang: "${query}"...`);

            // 1. Ubah query dari Qwen menjadi bentuk Vektor (Angka) menggunakan Langchain
            const embeddings = new OllamaEmbeddings({
                model: "nomic-embed-text",
                baseUrl: "http://127.0.0.1:11434"
            });
            const queryVector = await embeddings.embedQuery(query);

            // 2. Kirim permintaan pencarian ke Server Python RAG kita
            const response = await axios.post('http://127.0.0.1:8000/search', {
                query_text: query,
                query_vector: queryVector,
                top_k: 3
            });

            const results = response.data.results;

            // 3. Evaluasi hasil pencarian
            if (!results || results.length === 0) {
                console.log("🧠 [Agent] Ingatan tidak ditemukan.");
                return "Sistem: Tidak ada informasi terkait di dalam ingatan masa lalu.";
            }

            // 4. Susun konteks untuk disuapkan kembali ke Qwen
            console.log("🧠 [Agent] Berhasil menemukan ingatan yang relevan!");
            const konteks = results.join("\n- ");

            return `Sistem menemukan informasi dari ingatan masa lalu:\n- ${konteks}\n\nGunakan informasi di atas untuk menjawab pertanyaan pengguna dengan natural.`;

        } catch (error) {
            console.error("\n❌ [Tool Error] Gagal mencari memori:", error.message);
            return `Sistem Error: Gagal mengakses database memori (${error.message})`;
        } finally {
            // VRAM GUARD: unload nomic-embed-text agar Qwen / LLaVA tidak OOM
            await _unloadModel("nomic-embed-text");
        }
    }
};

module.exports = memorySearchTool;