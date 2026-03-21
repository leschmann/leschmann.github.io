const sidebar = document.getElementById('sidebar');
const grid = document.getElementById('movieGrid');
const countDisplay = document.getElementById('movieCount');
const searchInput = document.getElementById('searchInput');
const sortSelect = document.getElementById('sortSelect');
const ratingSlider = document.getElementById('ratingSlider');
const ratingVal = document.getElementById('ratingVal');
const minDuration = document.getElementById('minDuration');
const maxDuration = document.getElementById('maxDuration');
const genreContainer = document.getElementById('genreContainer');
const logicRadios = document.querySelectorAll('input[name="genreLogic"]');

// 🔥 NEUE Selektoren für Audio & Subs
const audioLangContainer = document.getElementById('audioLangContainer');
const subLangContainer = document.getElementById('subLangContainer');
const audioLogicRadios = document.querySelectorAll('input[name="audioLogic"]');
const subLogicRadios = document.querySelectorAll('input[name="subLogic"]');

const directorFilter = document.getElementById('directorFilter');
const starFilter = document.getElementById('starFilter');
const sizeSlider = document.getElementById('sizeSlider');
const modal = document.getElementById('movieModal');

// --- MOBILE INITIALIZATION ---
if (window.innerWidth <= 800) {
    sidebar.classList.add('hidden');
    document.documentElement.style.setProperty('--card-size', '140px');
    sizeSlider.value = 140;
}

window.toggleSidebar = function() {
    sidebar.classList.toggle('hidden');
};

sizeSlider.addEventListener('input', (e) => {
    document.documentElement.style.setProperty('--card-size', `${e.target.value}px`);
});

// --- MODAL OVERLAY LOGIC ---
window.openModal = function(imdbId) {
    const m = allMovies.find(movie => movie.imdb_id === imdbId);
    if (!m) return;

    document.getElementById('modalImg').src = m.img_uri;
    document.getElementById('modalTitle').textContent = `${m.title} (${m.year > 0 ? m.year : '?'})`;
    document.getElementById('modalMeta').innerHTML = `
        <span>⭐ ${m.imdb_rating_str}</span>
        <span>${m.fsk_rating}</span>
        <span>${m.duration_str}</span>
    `;
    document.getElementById('modalGenres').textContent = m.genres_str;
    document.getElementById('modalPlot').textContent = m.outline;

    // 🔥 Audio und Subs im Popup anzeigen
    const audioStr = m.audio_languages_english && m.audio_languages_english.length > 0 ? m.audio_languages_english.join(', ') : 'Unknown';
    const subStr = m.subtitles_languages_english && m.subtitles_languages_english.length > 0 ? m.subtitles_languages_english.join(', ') : 'None';

    document.getElementById('modalCredits').innerHTML = `
        <strong>Director:</strong> ${m.director}<br>
        <strong>Stars:</strong> ${m.stars}<br><br>
        <strong>Audio:</strong> ${audioStr}<br>
        <strong>Subtitles:</strong> ${subStr}<br><br>
        <strong>Location:</strong> ${m.folder_location}<br>
        <strong>Collection #:</strong> ${m.num}
    `;

    const copyBtn = document.getElementById('modalCopyBtn');
    copyBtn.onclick = () => {
        navigator.clipboard.writeText(m.folder_path).then(() => {
            copyBtn.textContent = '✅ Copied!';
            setTimeout(() => copyBtn.textContent = '📋 Copy Path', 2000);
        });
    };

    document.getElementById('modalLink').href = `https://www.imdb.com/title/${m.imdb_id}/`;

    modal.classList.add('show');
    document.body.style.overflow = 'hidden';
};

window.closeModal = function(event) {
    if (event && event.target !== modal) return;
    modal.classList.remove('show');
    document.body.style.overflow = '';
};

function initFilters() {
    // Genres init
    allGenres.forEach(genre => {
        const label = document.createElement('label');
        label.className = 'genre-item';
        label.innerHTML = `<input type="checkbox" value="${genre}" class="genre-checkbox"> ${genre}`;
        genreContainer.appendChild(label);
    });
    document.querySelectorAll('.genre-checkbox').forEach(cb => cb.addEventListener('change', updateGallery));

    // 🔥 Audio init
    allAudioLanguagesEnglish.forEach(lang => {
        if (!lang || lang === 'Unknown') return; // Überspringe unbekannte Sprachen im Filter
        const label = document.createElement('label');
        label.className = 'genre-item';
        label.innerHTML = `<input type="checkbox" value="${lang}" class="audio-checkbox"> ${lang}`;
        audioLangContainer.appendChild(label);
    });
    document.querySelectorAll('.audio-checkbox').forEach(cb => cb.addEventListener('change', updateGallery));

    // 🔥 Subs init
    allSubtitleLanguagesEnglish.forEach(lang => {
        if (!lang || lang === 'Unknown') return;
        const label = document.createElement('label');
        label.className = 'genre-item';
        label.innerHTML = `<input type="checkbox" value="${lang}" class="sub-checkbox"> ${lang}`;
        subLangContainer.appendChild(label);
    });
    document.querySelectorAll('.sub-checkbox').forEach(cb => cb.addEventListener('change', updateGallery));

    // Event Listener für die neuen AND/OR Radios
    audioLogicRadios.forEach(radio => radio.addEventListener('change', updateGallery));
    subLogicRadios.forEach(radio => radio.addEventListener('change', updateGallery));

    // Directors & Stars init
    allDirectors.forEach(director => {
        const opt = document.createElement('option');
        opt.value = director;
        opt.textContent = director;
        directorFilter.appendChild(opt);
    });
    directorFilter.addEventListener('change', updateGallery);

    allStars.forEach(star => {
        const opt = document.createElement('option');
        opt.value = star;
        opt.textContent = star;
        starFilter.appendChild(opt);
    });
    starFilter.addEventListener('change', updateGallery);
}

function renderMovies(movies) {
    grid.innerHTML = '';
    countDisplay.textContent = `${movies.length} Movie${movies.length !== 1 ? 's' : ''}`;

    movies.forEach(movie => {
        const fullTitle = `${movie.title} (${movie.year > 0 ? movie.year : '?'})`;

        const card = document.createElement('div');
        card.className = 'movie-card';
        card.setAttribute('onclick', `openModal('${movie.imdb_id}')`);

        card.innerHTML = `
            <img src="${movie.img_uri}" class="cover-img" alt="Cover" onerror="this.onerror=null; this.src='https://via.placeholder.com/300x450/000000/FFFFFF/?text=No+Cover';">
            <div class="movie-info">
                <div class="title" title="${fullTitle}">${fullTitle}</div>
                <div class="meta">
                    <span>⭐ ${movie.imdb_rating_str}</span>
                    <span>${movie.fsk_rating}</span>
                    <span>${movie.duration_str}</span>
                </div>
                <div class="genres" title="${movie.genres_str}">${movie.genres_str}</div>
            </div>
        `;
        grid.appendChild(card);
    });
}

function updateGallery() {
    const searchQuery = searchInput.value.toLowerCase().trim();
    const minRat = parseFloat(ratingSlider.value);
    const minDur = parseInt(minDuration.value) || 0;
    const maxDur = parseInt(maxDuration.value) || 9999;

    const checkedGenres = Array.from(document.querySelectorAll('.genre-checkbox:checked')).map(cb => cb.value);
    const genreLogic = document.querySelector('input[name="genreLogic"]:checked').value;

    // 🔥 Audio und Sub ausgewählte Checkboxen sammeln
    const checkedAudio = Array.from(document.querySelectorAll('.audio-checkbox:checked')).map(cb => cb.value);
    const audioLogic = document.querySelector('input[name="audioLogic"]:checked').value;

    const checkedSubs = Array.from(document.querySelectorAll('.sub-checkbox:checked')).map(cb => cb.value);
    const subLogic = document.querySelector('input[name="subLogic"]:checked').value;

    const selDirector = directorFilter.value;
    const selStar = starFilter.value;

    let filtered = allMovies.filter(m => {
        // Search
        if (searchQuery) {
            const inTitle = m.title.toLowerCase().includes(searchQuery);
            const inYear = String(m.year).includes(searchQuery);
            const inOutline = m.outline.toLowerCase().includes(searchQuery);
            const inDirector = m.director.toLowerCase().includes(searchQuery);
            const inStars = m.stars.toLowerCase().includes(searchQuery);
            if (!inTitle && !inYear && !inOutline && !inDirector && !inStars) return false;
        }

        if (m.imdb_rating_val < minRat) return false;
        if (m.duration_min > 0 && (m.duration_min < minDur || m.duration_min > maxDur)) return false;
        if (selDirector && !m.director.includes(selDirector)) return false;
        if (selStar && !m.stars.includes(selStar)) return false;

        // Genres Filter
        if (checkedGenres.length > 0) {
            if (genreLogic === 'OR') {
                if (!checkedGenres.some(g => m.genres_list.includes(g))) return false;
            } else if (genreLogic === 'AND') {
                if (!checkedGenres.every(g => m.genres_list.includes(g))) return false;
            }
        }

        // 🔥 Audio Filter
        if (checkedAudio.length > 0) {
            const mAudio = m.audio_languages_english || [];
            if (audioLogic === 'OR') {
                if (!checkedAudio.some(l => mAudio.includes(l))) return false;
            } else if (audioLogic === 'AND') {
                if (!checkedAudio.every(l => mAudio.includes(l))) return false;
            }
        }

        // 🔥 Subtitle Filter
        if (checkedSubs.length > 0) {
            const mSubs = m.subtitles_languages_english || [];
            if (subLogic === 'OR') {
                if (!checkedSubs.some(l => mSubs.includes(l))) return false;
            } else if (subLogic === 'AND') {
                if (!checkedSubs.every(l => mSubs.includes(l))) return false;
            }
        }

        return true;
    });

    const sortRules = sortSelect.value.split('_');
    const sortField = sortRules[0];
    const sortDir = sortRules[1];

    filtered.sort((a, b) => {
        let valA, valB;
        if (sortField === 'title') { valA = a.title.toLowerCase(); valB = b.title.toLowerCase(); }
        else if (sortField === 'year') { valA = a.year; valB = b.year; }
        else if (sortField === 'rating') { valA = a.imdb_rating_val; valB = b.imdb_rating_val; }
        else if (sortField === 'duration') { valA = a.duration_min; valB = b.duration_min; }
        else if (sortField === 'director') { valA = a.director.toLowerCase(); valB = b.director.toLowerCase(); }

        if (valA < valB) return sortDir === 'asc' ? -1 : 1;
        if (valA > valB) return sortDir === 'asc' ? 1 : -1;
        return 0;
    });

    renderMovies(filtered);
}

function resetFilters() {
    searchInput.value = '';
    sortSelect.value = 'title_asc';
    ratingSlider.value = 0;
    ratingVal.textContent = '0.0';
    minDuration.value = 0;
    maxDuration.value = 300;
    directorFilter.value = '';
    starFilter.value = '';

    // Alle Checkboxen zurücksetzen
    document.querySelectorAll('.genre-checkbox, .audio-checkbox, .sub-checkbox').forEach(cb => cb.checked = false);

    // Logik Radios zurücksetzen
    document.querySelector('input[name="genreLogic"][value="OR"]').checked = true;
    document.querySelector('input[name="audioLogic"][value="OR"]').checked = true;
    document.querySelector('input[name="subLogic"][value="OR"]').checked = true;

    updateGallery();
}

searchInput.addEventListener('input', updateGallery);
sortSelect.addEventListener('change', updateGallery);
ratingSlider.addEventListener('input', (e) => {
    ratingVal.textContent = parseFloat(e.target.value).toFixed(1);
    updateGallery();
});
minDuration.addEventListener('input', updateGallery);
maxDuration.addEventListener('input', updateGallery);
logicRadios.forEach(radio => radio.addEventListener('change', updateGallery));

initFilters();
updateGallery();