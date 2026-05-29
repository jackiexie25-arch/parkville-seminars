/**
 * Parkville Biomedical Seminars — Frontend App
 * Loads seminars.json, renders cards with Apple design classes,
 * and handles pill-based institution filtering.
 */

// ── State ────────────────────────────────────────────────
let allSeminars = [];
let scraperStatus = {};
let activeInstitutions = new Set();
let searchQuery = '';
let dateFrom = '';
let dateTo = '';

// Institution metadata (colors must match scrapers)
const INSTITUTIONS = {
  'WEHI':                          { color: '#003087', short: 'WEHI' },
  'Doherty Institute':             { color: '#00539B', short: 'Doherty' },
  'Peter MacCallum Cancer Centre': { color: '#6D2077', short: 'Peter Mac' },
  'MCRI':                          { color: '#009FDA', short: 'MCRI' },
  'Florey Institute':              { color: '#FF6B00', short: 'Florey' },
  'Bio21 Institute':               { color: '#0F4C81', short: 'Bio21' },
  'Orygen':                        { color: '#E4022D', short: 'Orygen' },
  'Melbourne Bioinformatics':      { color: '#005A8E', short: 'Melb. Bioinformatics' },
  'Melbourne Brain Centre':        { color: '#9B2335', short: 'Brain Centre' },
  'Royal Melbourne Hospital':      { color: '#0066CC', short: 'RMH' },
  'CERA':                          { color: '#00A9CE', short: 'CERA' },
  'Bionics Institute':             { color: '#E31B23', short: 'Bionics' },
};

// ── Initialise ───────────────────────────────────────────
async function init() {
  try {
    const res = await fetch('seminars.json?t=' + Date.now());
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    allSeminars = data.seminars || [];

    if (data.generated_at) {
      document.getElementById('update-time').textContent =
        'Updated ' + formatRelativeTime(new Date(data.generated_at));
    }

    // Load scraper status (optional)
    try {
      const sr = await fetch('scraper_status.json?t=' + Date.now());
      if (sr.ok) {
        const sd = await sr.json();
        scraperStatus = sd.scrapers || {};
        renderScraperStatus();
      }
    } catch (_) { /* optional */ }

    // Activate all institutions by default
    const institutions = allKnownInstitutions();
    institutions.forEach(i => activeInstitutions.add(i));
    renderInstitutionFilter(institutions);

    render();

  } catch (err) {
    document.getElementById('seminars-container').innerHTML = `
      <div class="error-state">
        <span class="state-icon">⚠️</span>
        <div class="state-title">Could not load seminars</div>
        <div class="state-sub">${err.message}<br>
          Run <code>python3 run_scrapers.py</code> to generate <code>seminars.json</code>.
        </div>
      </div>`;
  }
}

// ── Helpers ──────────────────────────────────────────────
function allKnownInstitutions() {
  return [...new Set(allSeminars.map(s => s.institution))].sort();
}

// ── Filter & Sort ────────────────────────────────────────
function getFiltered() {
  let seminars = [...allSeminars];

  seminars = seminars.filter(s => activeInstitutions.has(s.institution));

  if (dateFrom) seminars = seminars.filter(s => s.date && s.date >= dateFrom);
  if (dateTo)   seminars = seminars.filter(s => s.date && s.date <= dateTo);

  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    seminars = seminars.filter(s =>
      (s.title       || '').toLowerCase().includes(q) ||
      (s.speaker     || '').toLowerCase().includes(q) ||
      (s.abstract    || '').toLowerCase().includes(q) ||
      (s.affiliation || '').toLowerCase().includes(q) ||
      (s.institution || '').toLowerCase().includes(q) ||
      (s.location    || '').toLowerCase().includes(q)
    );
  }

  const sort = document.getElementById('sort-select').value;
  if (sort === 'date-asc') {
    seminars.sort((a, b) => (a.date || '').localeCompare(b.date || ''));
  } else if (sort === 'date-desc') {
    seminars.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  } else if (sort === 'institution') {
    seminars.sort((a, b) =>
      a.institution.localeCompare(b.institution) ||
      (a.date || '').localeCompare(b.date || '')
    );
  }

  return seminars;
}

// ── Render ───────────────────────────────────────────────
function render() {
  const filtered = getFiltered();
  const container = document.getElementById('seminars-container');

  document.getElementById('count-display').textContent = filtered.length;
  document.getElementById('count-label').textContent =
    filtered.length === 1 ? ' seminar' : ' upcoming seminars';

  updateInstitutionCounts();
  updateClearBtn();

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <span class="state-icon">🔍</span>
        <div class="state-title">No seminars match your filters</div>
        <div class="state-sub">Try adjusting your search or date range,
          or check back once new events are posted.</div>
      </div>`;
    return;
  }

  const sort = document.getElementById('sort-select').value;
  const today   = todayISO();
  const weekEnd = addDays(today, 7);

  let html = '';

  if (sort === 'institution') {
    // Group by institution name
    const grouped = {};
    filtered.forEach(s => {
      if (!grouped[s.institution]) grouped[s.institution] = [];
      grouped[s.institution].push(s);
    });
    html = Object.entries(grouped).map(([inst, items]) => `
      <div class="seminar-group">
        <div class="section-label">${escHtml(inst)}</div>
        <div class="seminars-list">${items.map(buildCard).join('')}</div>
      </div>`).join('');
  } else {
    // Group by time window
    const groups = { today: [], 'this-week': [], upcoming: [] };
    filtered.forEach(s => {
      if (!s.date || s.date < today) {
        groups.upcoming.push(s); // no date → put at end
      } else if (s.date === today) {
        groups.today.push(s);
      } else if (s.date <= weekEnd) {
        groups['this-week'].push(s);
      } else {
        groups.upcoming.push(s);
      }
    });

    const LABELS = { today: 'Today', 'this-week': 'This Week', upcoming: 'Upcoming' };

    html = Object.entries(groups)
      .filter(([, items]) => items.length > 0)
      .map(([key, items]) => `
        <div class="seminar-group">
          <div class="section-label ${key === 'today' ? 'today' : ''}">${LABELS[key]}</div>
          <div class="seminars-list">${items.map(buildCard).join('')}</div>
        </div>`).join('');
  }

  container.innerHTML = html;
}

function updateClearBtn() {
  const hasFilters =
    searchQuery || dateFrom || dateTo ||
    activeInstitutions.size < allKnownInstitutions().length;
  document.getElementById('clear-btn').classList.toggle('visible', !!hasFilters);
}

// ── Card builder ─────────────────────────────────────────
function buildCard(s) {
  const meta  = INSTITUTIONS[s.institution] || { color: '#38bdf8', short: s.institution };
  const color = s.institution_color || meta.color;
  const short = meta.short || s.institution;

  const dateBlock = buildDateBlock(s.date);
  const timeTxt   = s.time ? formatTime(s.time) : '';
  const loc       = s.location || '';
  const speaker   = s.speaker || '';
  const hasBody   = !!(s.abstract || speaker || s.url);

  const title = highlight(escHtml(s.title || 'Untitled'), searchQuery);

  const onlineTag = s.online
    ? `<span class="card-online-tag">Online</span>` : '';

  const metaItems = [
    timeTxt ? `<span class="card-meta-item">${iconClock()}${escHtml(timeTxt)}</span>` : '',
    loc     ? `<span class="card-meta-item">${iconLocation()}${escHtml(loc)}</span>` : '',
    speaker ? `<span class="card-meta-item">${iconPerson()}${escHtml(speaker)}</span>` : '',
  ].filter(Boolean).join('');

  const chevron = hasBody
    ? `<div class="card-chevron">${iconChevronRight()}</div>`
    : `<div></div>`;

  const speakerBlock = speaker ? `
    <div class="card-speaker">
      <div class="speaker-avatar">${getInitials(speaker)}</div>
      <div class="speaker-details">
        <div class="speaker-name">${escHtml(speaker)}</div>
        ${s.affiliation ? `<div class="speaker-affil">${escHtml(s.affiliation)}</div>` : ''}
      </div>
    </div>` : '';

  const abstractHtml = s.abstract
    ? `<div class="card-abstract">${highlight(escHtml(s.abstract), searchQuery)}</div>` : '';

  const cardBody = hasBody ? `
    <div class="card-body">
      <div class="card-body-inner">
        ${speakerBlock}
        ${abstractHtml}
        ${s.url ? `
        <div class="card-actions">
          <a class="btn btn-primary" href="${escAttr(s.url)}" target="_blank" rel="noopener">
            ${iconExternal()} View details
          </a>
          <button class="btn btn-ghost" onclick="copyLink(event,'${escAttr(s.url)}')">
            ${iconCopy()} Copy link
          </button>
        </div>` : ''}
      </div>
    </div>` : '';

  const expandable = hasBody ? '' : ' no-expand';

  return `
    <div class="seminar-card${expandable}" style="--inst-color:${color}"
         onclick="handleCardClick(event,this)">
      <div class="card-row">
        ${dateBlock}
        <div class="card-content">
          <div class="card-inst-row">
            <div class="card-inst-dot" style="background:${color}"></div>
            <span class="card-inst-name">${escHtml(short)}</span>
            ${onlineTag}
          </div>
          <div class="card-title">${title}</div>
          ${metaItems ? `<div class="card-meta-row">${metaItems}</div>` : ''}
        </div>
        ${chevron}
      </div>
      ${cardBody}
    </div>`;
}

function buildDateBlock(dateISO) {
  if (!dateISO) return `
    <div class="card-date">
      <div class="card-date-day">?</div>
      <div class="card-date-mon">TBD</div>
    </div>`;
  const d     = new Date(dateISO + 'T12:00:00');
  const day   = d.getDate();
  const month = d.toLocaleString('en-AU', { month: 'short' }).toUpperCase();
  const year  = d.getFullYear();
  const now   = new Date().getFullYear();
  return `
    <div class="card-date">
      <div class="card-date-day">${day}</div>
      <div class="card-date-mon">${month}</div>
      ${year !== now ? `<div class="card-date-mon">${year}</div>` : ''}
    </div>`;
}

// ── Institution pills ────────────────────────────────────
function renderInstitutionFilter(institutions) {
  const container = document.getElementById('institution-pills');
  container.innerHTML = institutions.map(inst => {
    const meta  = INSTITUTIONS[inst] || { color: '#38bdf8', short: inst };
    const color = meta.color;
    const count = allSeminars.filter(s => s.institution === inst).length;
    return `
      <button class="pill active" data-pill="${escAttr(inst)}"
        onclick="togglePill(this,'${escAttr(inst)}')">
        <span class="pill-dot" style="background:${color}"></span>
        ${escHtml(meta.short || inst)}
        <span class="pill-count">${count}</span>
      </button>`;
  }).join('');
}

function updateInstitutionCounts() {
  // Count per institution given current search+date (ignoring institution filter)
  let seminars = [...allSeminars];
  if (dateFrom) seminars = seminars.filter(s => s.date && s.date >= dateFrom);
  if (dateTo)   seminars = seminars.filter(s => s.date && s.date <= dateTo);
  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    seminars = seminars.filter(s =>
      (s.title || '').toLowerCase().includes(q) ||
      (s.speaker || '').toLowerCase().includes(q) ||
      (s.abstract || '').toLowerCase().includes(q) ||
      (s.institution || '').toLowerCase().includes(q)
    );
  }
  const counts = {};
  seminars.forEach(s => counts[s.institution] = (counts[s.institution] || 0) + 1);

  document.querySelectorAll('[data-pill]').forEach(pill => {
    const el = pill.querySelector('.pill-count');
    if (el) el.textContent = counts[pill.dataset.pill] || 0;
  });
}

function togglePill(btn, institution) {
  if (activeInstitutions.has(institution)) {
    activeInstitutions.delete(institution);
    btn.classList.remove('active');
  } else {
    activeInstitutions.add(institution);
    btn.classList.add('active');
  }
  render();
}

// ── Scraper status ───────────────────────────────────────
function renderScraperStatus() {
  const section = document.getElementById('status-section');
  const grid    = document.getElementById('scraper-grid');
  if (!Object.keys(scraperStatus).length) return;

  section.style.display = 'block';
  grid.innerHTML = Object.entries(scraperStatus).map(([, s]) => {
    const cls  = s.status === 'ok'    ? 'scraper-ok'
               : s.status === 'empty' ? 'scraper-empty'
               :                        'scraper-error';
    const badge = s.status === 'ok'    ? `✓ ${s.count}`
                : s.status === 'empty' ? `○ 0`
                :                        '✗';
    return `
      <div class="scraper-item">
        <span class="scraper-name">${escHtml(s.name)}</span>
        <span class="${cls}">${badge}</span>
      </div>`;
  }).join('');
}

// ── Event handlers ───────────────────────────────────────
function handleCardClick(e, card) {
  if (e.target.closest('a') || e.target.closest('button')) return;
  if (card.classList.contains('no-expand')) return;
  card.classList.toggle('expanded');
}

function clearFilters() {
  searchQuery = '';
  dateFrom    = '';
  dateTo      = '';
  document.getElementById('search').value    = '';
  document.getElementById('date-from').value = '';
  document.getElementById('date-to').value   = '';

  allKnownInstitutions().forEach(i => activeInstitutions.add(i));
  document.querySelectorAll('[data-pill]').forEach(p => p.classList.add('active'));

  render();
}

function copyLink(e, url) {
  e.stopPropagation();
  navigator.clipboard.writeText(url).then(() => {
    const btn  = e.currentTarget;
    const orig = btn.innerHTML;
    btn.innerHTML = '✓ Copied!';
    setTimeout(() => btn.innerHTML = orig, 1500);
  });
}

// ── Input listeners ──────────────────────────────────────
document.getElementById('search').addEventListener('input', e => {
  searchQuery = e.target.value.trim();
  render();
});
document.getElementById('date-from').addEventListener('change', e => {
  dateFrom = e.target.value;
  render();
});
document.getElementById('date-to').addEventListener('change', e => {
  dateTo = e.target.value;
  render();
});

// ── Helpers ──────────────────────────────────────────────
function escHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function escAttr(str) {
  if (!str) return '';
  return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function highlight(html, query) {
  if (!query) return html;
  const esc = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return html.replace(new RegExp(`(${esc})`, 'gi'),
    '<mark class="highlight">$1</mark>');
}

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function addDays(iso, n) {
  const d = new Date(iso + 'T12:00:00');
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

function formatTime(t) {
  const [h, m] = t.split(':').map(Number);
  const ampm   = h >= 12 ? 'PM' : 'AM';
  const h12    = h % 12 || 12;
  return `${h12}:${String(m).padStart(2, '0')} ${ampm}`;
}

function formatRelativeTime(d) {
  const diff = Date.now() - d.getTime();
  const mins = Math.floor(diff / 60000);
  const hrs  = Math.floor(mins / 60);
  if (mins < 2)  return 'just now';
  if (mins < 60) return `${mins}m ago`;
  if (hrs  < 24) return `${hrs}h ago`;
  return d.toLocaleDateString('en-AU', { day: 'numeric', month: 'short' });
}

function getInitials(name) {
  return name.trim().split(/\s+/)
    .map(w => w[0]).filter(Boolean)
    .slice(0, 2).join('').toUpperCase();
}

// ── SVG icons ─────────────────────────────────────────────
const SVG = 'width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';

function iconClock()        { return `<svg ${SVG}><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`; }
function iconLocation()     { return `<svg ${SVG}><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>`; }
function iconPerson()       { return `<svg ${SVG}><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`; }
function iconChevronRight() { return `<svg ${SVG}><polyline points="9 18 15 12 9 6"/></svg>`; }
function iconExternal()     { return `<svg ${SVG}><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>`; }
function iconCopy()         { return `<svg ${SVG}><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`; }

// ── Auto-refresh ─────────────────────────────────────────
let lastGeneratedAt = null;

async function checkForUpdates() {
  try {
    const res  = await fetch('seminars.json?t=' + Date.now());
    if (!res.ok) return;
    const data = await res.json();
    if (data.generated_at && data.generated_at !== lastGeneratedAt) {
      lastGeneratedAt = data.generated_at;
      allSeminars     = data.seminars || [];

      const institutions = allKnownInstitutions();
      institutions.forEach(i => { if (!activeInstitutions.has(i)) activeInstitutions.add(i); });
      renderInstitutionFilter(institutions);
      render();

      document.getElementById('update-time').textContent =
        'Updated ' + formatRelativeTime(new Date(data.generated_at));

      console.log('[Parkville Seminars] Refreshed:', data.total, 'seminars');
    }
  } catch (_) { /* silent */ }
}

// Poll every 30 minutes
setInterval(checkForUpdates, 30 * 60 * 1000);

// Also refresh when tab becomes visible
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') checkForUpdates();
});

// ── Boot ─────────────────────────────────────────────────
init().then(() => {
  fetch('seminars.json?t=' + Date.now())
    .then(r => r.json())
    .then(d => { lastGeneratedAt = d.generated_at || null; })
    .catch(() => {});
});
