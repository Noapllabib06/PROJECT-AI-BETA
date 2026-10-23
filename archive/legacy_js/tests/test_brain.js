/**
 * test_brain.js
 * Script untuk menguji Memori dan State Management Jarvis
 */

const agent = require('../src/engine/agent');

async function runTest() {
    console.log("=== MEMULAI TEST FASE 3: KECERDASAN & MEMORI ===\n");

    // --- TEST 1: Menguji Memori (Konteks Percakapan) ---
    console.log("--- TEST 1: Memori Percakapan ---");
    
    let input1 = "Halo Jarvis, perkenalkan nama saya Alex. Saya sangat suka memancing.";
    console.log(`User: ${input1}`);
    let respons1 = await agent.processInput(input1);
    console.log(`Jarvis: ${respons1}\n`);

    let input2 = "Apakah kamu ingat siapa nama saya dan apa hobi saya?";
    console.log(`User: ${input2}`);
    let respons2 = await agent.processInput(input2);
    console.log(`Jarvis: ${respons2}\n`);

    // --- TEST 2: Menguji State Management ---
    console.log("--- TEST 2: Perubahan Status (State) ---");
    
    console.log("[SYSTEM] Mengubah status Jarvis menjadi: Sedang memutar lagu Lofi di YouTube...");
    // Mengubah state/status Jarvis dari luar
    agent.updateState("Sedang memutar lagu Lofi di YouTube");

    let input3 = "Jarvis, apa yang sedang kamu lakukan sekarang?";
    console.log(`User: ${input3}`);
    let respons3 = await agent.processInput(input3);
    console.log(`Jarvis: ${respons3}\n`);

    console.log("=== TESTING SELESAI ===");
}

// Jalankan fungsi test
runTest();