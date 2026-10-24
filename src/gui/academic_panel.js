/**
 * src/gui/academic_panel.js
 * Academic Hub & Multi-Course Navigation for JARVIS.
 * 
 * Provides:
 * - Dynamic course detection from /api/academic/courses (scanned from data/kuliah/).
 * - Interactive sidebar accordion with course badges, lecture file counts, and status indicators.
 * - 1-Click Action Triggers:
 *   - "Rangkum Semester" -> executes summarize_course_materials from P1 to Px.
 *   - "Kuis Ujian (UTS/UAS)" -> generates exam practice questions.
 *   - "Tanya Materi" -> sets active course context chip in chat input.
 *   - "Sinkronisasi / Ingest" -> indexes newly uploaded slides.
 */

(function () {
    let enrolledCourses = [];
    let activeCourseFilter = null;

    /**
     * Inisialisasi Academic Panel di UI.
     */
    async function initAcademicPanel() {
        const container = document.getElementById('academicHubContainer');
        if (!container) return;

        await loadCourses();
    }

    /**
     * Memuat daftar mata kuliah dari API backend.
     */
    async function loadCourses() {
        const listEl = document.getElementById('academicCourseList');
        const countBadge = document.getElementById('academicCountBadge');
        if (!listEl) return;

        try {
            const resp = await fetch('/api/academic/courses');
            if (!resp.ok) throw new Error('Gagal memuat mata kuliah');
            const data = await resp.json();
            enrolledCourses = data.courses || [];

            if (countBadge) {
                countBadge.textContent = `${enrolledCourses.length} Matkul`;
            }

            renderCourseList(enrolledCourses);
        } catch (err) {
            console.warn('[AcademicPanel] Warning:', err);
            if (listEl) {
                listEl.innerHTML = `
                    <div class="px-3 py-2 text-xs text-secondary italic">
                        Belum dapat memuat daftar mata kuliah.
                    </div>
                `;
            }
        }
    }

    /**
     * Render daftar mata kuliah di sidebar.
     */
    function renderCourseList(courses) {
        const listEl = document.getElementById('academicCourseList');
        if (!listEl) return;

        if (courses.length === 0) {
            listEl.innerHTML = `
                <div class="px-3 py-2 text-xs text-secondary text-center">
                    Belum ada folder di <code>data/kuliah/</code>.
                </div>
            `;
            return;
        }

        listEl.innerHTML = courses.map((course, idx) => {
            const isCloud = course.folder.toLowerCase().includes('cloud');
            const icon = isCloud ? 'cloud' : 'menu_book';
            return `
                <div class="academic-course-card group rounded-xl border border-border-subtle/70 bg-surface-container-low/60 hover:bg-surface-container hover:border-action-orange-vibrant/40 transition-all p-2.5 space-y-2">
                    <div class="flex items-center justify-between cursor-pointer" onclick="window.AcademicPanel.toggleDetails('${course.folder}')">
                        <div class="flex items-center gap-2 min-w-0">
                            <span class="material-symbols-outlined text-action-orange-vibrant text-[18px] flex-shrink-0">${icon}</span>
                            <span class="text-xs font-semibold text-on-surface truncate group-hover:text-action-orange-vibrant transition-colors" title="${course.name}">
                                ${course.name}
                            </span>
                        </div>
                        <span class="text-[10px] font-mono font-medium px-2 py-0.5 rounded-full bg-surface-container-high text-secondary flex-shrink-0">
                            ${course.files_count} file
                        </span>
                    </div>

                    <!-- Quick Action Buttons -->
                    <div id="course-actions-${course.folder}" class="hidden pt-1.5 border-t border-border-subtle/50 grid grid-cols-2 gap-1.5 text-[11px]">
                        <button onclick="window.AcademicPanel.triggerAction('${course.name}', 'summary')" 
                                class="flex items-center justify-center gap-1 py-1 px-1.5 rounded-lg bg-surface-container-high hover:bg-action-orange-vibrant/10 hover:text-action-orange-vibrant transition-colors font-medium text-secondary"
                                title="Rangkum seluruh materi dari P1 sampai akhir">
                            <span class="material-symbols-outlined text-[14px]">auto_stories</span> Rangkum
                        </button>
                        <button onclick="window.AcademicPanel.triggerAction('${course.name}', 'quiz')" 
                                class="flex items-center justify-center gap-1 py-1 px-1.5 rounded-lg bg-surface-container-high hover:bg-action-orange-vibrant/10 hover:text-action-orange-vibrant transition-colors font-medium text-secondary"
                                title="Buatkan kuis latihan ujian">
                            <span class="material-symbols-outlined text-[14px]">quiz</span> Kuis UTS
                        </button>
                        <button onclick="window.AcademicPanel.triggerAction('${course.name}', 'search')" 
                                class="flex items-center justify-center gap-1 py-1 px-1.5 rounded-lg bg-surface-container-high hover:bg-action-orange-vibrant/10 hover:text-action-orange-vibrant transition-colors font-medium text-secondary"
                                title="Tanya materi spesifik">
                            <span class="material-symbols-outlined text-[14px]">search</span> Tanya
                        </button>
                        <button onclick="window.AcademicPanel.triggerAction('${course.name}', 'ingest')" 
                                class="flex items-center justify-center gap-1 py-1 px-1.5 rounded-lg bg-surface-container-high hover:bg-action-orange-vibrant/10 hover:text-action-orange-vibrant transition-colors font-medium text-secondary"
                                title="Indeks ulang materi slide">
                            <span class="material-symbols-outlined text-[14px]">sync</span> Ingest
                        </button>
                    </div>
                </div>
            `;
        }).join('');
    }

    /**
     * Buka/tutup aksi cepat per mata kuliah.
     */
    function toggleDetails(folder) {
        const el = document.getElementById(`course-actions-${folder}`);
        if (!el) return;
        el.classList.toggle('hidden');
    }

    /**
     * Menjalankan aksi cepat untuk mata kuliah.
     */
    function triggerAction(courseName, action) {
        const inputEl = document.getElementById('userInput');
        const sendBtn = document.getElementById('sendBtn');
        if (!inputEl) return;

        let queryText = '';
        if (action === 'summary') {
            queryText = `Tolong rangkum seluruh materi kuliah ${courseName} dari P1 sampai akhir dan jelaskan benang merahnya`;
        } else if (action === 'quiz') {
            queryText = `Buatkan kuis latihan ujian komprehensif (3 soal pilihan ganda & 1 studi kasus) berdasarkan materi kuliah ${courseName}`;
        } else if (action === 'ingest') {
            queryText = `Tolong ingest materi kuliah ${courseName}`;
        } else if (action === 'search') {
            inputEl.value = `Jelaskan materi pertemuan 1 ${courseName} tentang `;
            inputEl.focus();
            return;
        }

        if (queryText) {
            inputEl.value = queryText;
            if (sendBtn) {
                sendBtn.click();
            }
        }
    }

    // Expose to window
    window.AcademicPanel = {
        initAcademicPanel,
        loadCourses,
        toggleDetails,
        triggerAction
    };

    // Auto-init on DOMContentLoaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAcademicPanel);
    } else {
        initAcademicPanel();
    }
})();
