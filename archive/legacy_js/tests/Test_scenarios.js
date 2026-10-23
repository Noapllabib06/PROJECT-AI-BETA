/**
 * test_scenarios.js
 * Skenario pengujian untuk memvalidasi 9 fix di agent.js & prompt.js.
 * 
 * CARA PAKAI:
 * 1. Letakkan file ini di root project (sejajar dengan test_brain.js).
 * 2. PENTING — sebelum menjalankan Part A, tambahkan export berikut:
 * 
 *    Di src/engine/agent.js, di baris paling bawah, ubah:
 *      module.exports = new JarvisAgent();
 *    menjadi:
 *      const agentInstance = new JarvisAgent();
 *      module.exports = agentInstance;
 *      module.exports._determineRelevantTools = determineRelevantTools; // export untuk testing
 * 
 *    Di src/engine/prompt.js, ubah baris export paling bawah menjadi:
 *      module.exports = { buildSystemPrompt, buildToolsSection, buildFewShotExamples };
 * 
 * 3. Jalankan: node test_scenarios.js
 */

const agent = require('../src/engine/agent.js');
const promptModule = require('../src/engine/prompt.js');

let passCount = 0;
let failCount = 0;

function assert(condition, label, detail = '') {
    if (condition) {
        console.log(`✅ PASS — ${label}`);
        passCount++;
    } else {
        console.log(`❌ FAIL — ${label} ${detail ? `(${detail})` : ''}`);
        failCount++;
    }
}

console.log('\n========================================');
console.log('PART A — UNIT TEST: determineRelevantTools()');
console.log('(Fix #3 dan Fix #4 — keyword cleanup & scoring)');
console.log('========================================\n');

// --- Fix #3: keyword 'hobi' seharusnya TIDAK lagi memicu kategori WEB ---
{
    const tools = agent._determineRelevantTools('apa hobi kamu selain coding?');
    assert(
        tools.length === 0,
        "Fix #3: 'apa hobi kamu?' tidak lagi salah trigger tool WEB",
        `hasil: [${tools.join(', ')}]`
    );
}

// --- Fix #3: keyword 'purwokerto' dan 'restock' seharusnya tidak ada lagi di kategori WEB ---
{
    const tools = agent._determineRelevantTools('aku tinggal di purwokerto, kapan restock barangnya?');
    // Catatan: ini masih boleh match WEB via keyword 'kapan' (pertanyaan waktu) —
    // yang penting BUKAN karena 'purwokerto'/'restock' secara spesifik.
    // Test ini untuk observasi manual, bukan pass/fail ketat.
    console.log(`ℹ️  INFO — query lokasi netral -> tools: [${tools.join(', ')}] (cek manual: harus via keyword generik, bukan hardcode kota)`);
}

// --- Fix #4: overlap kategori WEB vs FILE — FILE harus menang karena lebih spesifik ---
{
    const tools = agent._determineRelevantTools('buka file catatan aku yang kemarin');
    const fileTools = ['create_file', 'read_file', 'ingest_codebase'];
    const hasFileTool = tools.some(t => fileTools.includes(t));
    assert(
        hasFileTool,
        'Fix #4: query "buka file catatan" tetap menyertakan tool FILE meski overlap dengan WEB',
        `hasil: [${tools.join(', ')}]`
    );
}

// --- Kasus kontrol: kategori MEDIA murni, tidak overlap ---
{
    const tools = agent._determineRelevantTools('putar lagu bohemian rhapsody');
    const mediaTools = ['search_youtube', 'play_music', 'play_video'];
    const onlyMedia = tools.every(t => mediaTools.includes(t));
    assert(
        onlyMedia && tools.length > 0,
        'Kontrol: query MEDIA murni hanya mengembalikan tool MEDIA',
        `hasil: [${tools.join(', ')}]`
    );
}

// --- Kasus kontrol: chat murni, tidak ada kategori match ---
{
    const tools = agent._determineRelevantTools('menurutmu kucing atau anjing lebih baik?');
    assert(
        tools.length === 0,
        'Kontrol: query chat murni tidak memicu tool apapun',
        `hasil: [${tools.join(', ')}]`
    );
}

console.log('\n========================================');
console.log('PART B — UNIT TEST: buildFewShotExamples() & buildSystemPrompt()');
console.log('(Fix #6 dan Fix #7 — dinamisasi few-shot & web rules)');
console.log('========================================\n');

// --- Fix #6: few-shot HANYA berisi contoh untuk tool yang benar-benar dikirim ---
{
    const fakeTools = [{ function: { name: 'play_music', description: 'putar musik', parameters: { properties: {} } } }];
    const fewShot = promptModule.buildFewShotExamples(fakeTools);
    const mentionsSearchWeb = fewShot.includes('search_web');
    const mentionsPlayMusic = fewShot.includes('play_music');
    assert(
        !mentionsSearchWeb && mentionsPlayMusic,
        'Fix #6: few-shot hanya menampilkan contoh tool yang relevan (play_music), bukan search_web yang tidak dikirim'
    );
    const hasNegativeExample = fewShot.includes('cara bikin kopi');
    assert(
        hasNegativeExample,
        'Fix #6: contoh negatif (chat biasa) selalu tersertakan apapun tool yang dikirim'
    );
}

// --- Fix #7: WEB_ANSWER_RULES hanya muncul kalau search_web/read_webpage ada di relevantTools ---
{
    const toolsWithWeb = [{ function: { name: 'search_web', description: '', parameters: { properties: {} } } }];
    const toolsWithoutWeb = [{ function: { name: 'play_music', description: '', parameters: { properties: {} } } }];

    const promptWithWeb = promptModule.buildSystemPrompt(toolsWithWeb, '');
    const promptWithoutWeb = promptModule.buildSystemPrompt(toolsWithoutWeb, '');

    assert(
        promptWithWeb.includes('ATURAN MENJAWAB HASIL PENCARIAN WEB'),
        'Fix #7: WEB_ANSWER_RULES muncul saat search_web ada di tools'
    );
    assert(
        !promptWithoutWeb.includes('ATURAN MENJAWAB HASIL PENCARIAN WEB'),
        'Fix #7: WEB_ANSWER_RULES TIDAK muncul saat search_web tidak ada di tools (mengurangi noise prompt)'
    );
}

// --- Fix #8: aturan kasus ambigu ada di TOOL_DECISION_RULES ---
{
    const prompt = promptModule.buildSystemPrompt([], '');
    assert(
        prompt.toLowerCase().includes('ragu'),
        'Fix #8: instruksi eksplisit untuk kasus ambigu ("jika ragu...") ada di system prompt'
    );
}

console.log('\n========================================');
console.log(`RINGKASAN UNIT TEST: ${passCount} PASS, ${failCount} FAIL`);
console.log('========================================\n');


console.log('\n========================================');
console.log('PART C — SKENARIO END-TO-END (perlu Ollama & jalankan manual)');
console.log('(Fix #1, #2 — cleanInput & anti-duplikasi retry)');
console.log('========================================\n');
console.log(`
Jalankan skenario berikut satu-satu via agent.processInput(...) dan cek manual:

--- Skenario 1: cleanInput() diterapkan (Fix #1) ---
Input   : "kak tolong cariin berita AI terbaru dong"
Expected: setelah dibersihkan jadi "cariin berita AI terbaru dong" (prefix 'kak tolong' hilang)
Cara cek: tambahkan console.log(cleanedInput) sementara di dalam _executePipeline
          untuk verifikasi prefix benar-benar terpotong sebelum masuk ke chatHistory.

--- Skenario 2: Tidak ada duplikasi chatHistory saat retry (Fix #2) ---
Langkah:
  1. Buat kondisi tool sengaja gagal (misal matikan koneksi internet untuk search_web,
     atau modifikasi sementara salah satu tool agar selalu return error).
  2. Jalankan: agent.processInput("cari berita teknologi terbaru")
  3. Setelah selesai (baik retry berhasil maupun fallback final), inspeksi agent.chatHistory:
     console.log(JSON.stringify(agent.chatHistory, null, 2));
Expected: tidak ada 2 entri berturut-turut dengan role:'user' dan content PERSIS SAMA
          ("cari berita teknologi terbaru" muncul HANYA SEKALI, bukan dua kali).
Sebelum fix: kamu akan lihat pola [user: "cari berita..."] -> [user: feedback] -> [user: "cari berita..." lagi]
Setelah fix: pola menjadi [user: "cari berita..."] -> [user: feedback] -> (tidak ada duplikasi)

--- Skenario 3: Kasus ambigu default ke chat (Fix #8, perlu verifikasi perilaku LLM nyata) ---
Input   : "gimana caranya biar internetnya cepet?"
          (ambigu: bisa dianggap butuh search_web, atau cukup dijawab dari pengetahuan umum)
Expected: model sebaiknya cenderung {"tool": "chat", ...} dengan jawaban umum,
          KECUALI user eksplisit minta info spesifik/real-time.
Catatan : ini bukan pass/fail ketat karena tergantung reasoning model 7B — 
          jalankan 3-5x untuk lihat konsistensi keputusan.

--- Skenario 4: Overlap kategori WEB vs FILE dalam konteks nyata (Fix #4) ---
Input   : "buka file laporan.txt yang aku buat kemarin"
Expected: tool yang dipilih model adalah "read_file", BUKAN "open_website" atau "search_web".
Cek     : console.log hasil parsing { tool, query } di dalam _executePipeline.

--- Skenario 5: Few-shot tidak menyesatkan model ke tool yang tidak dikirim (Fix #6) ---
Input   : "putar lagu ​​misery dari nsb" (hanya trigger kategori MEDIA)
Expected: tool yang dipilih adalah salah satu dari [search_youtube, play_music, play_video],
          BUKAN search_web / create_file / read_file (yang seharusnya tidak ada di tools terkirim).
Cek     : bandingkan dengan tools yang benar-benar dikirim ke buildSystemPrompt
          (tambahkan console.log(relevantToolNames) sementara di _executePipeline).
`);

console.log('\n========================================');
console.log('PART D — REGRESSION CHECK (pastikan fix tidak merusak fitur lama)');
console.log('========================================\n');
console.log(`
Jalankan ulang skenario yang SUDAH BENAR sebelum fix, pastikan masih benar:

1. "cari berita teknologi terbaru"     -> tool: search_web
2. "buka youtube"                       -> tool: open_website
3. "putar tutorial volumetrik blender"  -> tool: search_youtube
4. "menurutmu kucing atau anjing?"      -> tool: chat
5. "siapa presiden indonesia?"          -> tool: chat (bukan search_web, kecuali sengaja diminta info real-time)

Jika salah satu dari 5 kasus di atas berubah perilaku SETELAH fix diterapkan,
itu tanda regresi — cek ulang bagian Fix #4 (scoring) atau Fix #6 (few-shot dinamis).
`);