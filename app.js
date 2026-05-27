/**
 * Parkville Biomedical Seminars — Frontend App
 * Loads seminars.json, renders cards, handles filtering.
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
  'WEHI':                     { color: '#003087', short: 'WEHI' },
  'Doherty Institute':        { color: '#00539B', short: 'Doherty' },
  'Peter MacCallum Cancer Centre': { color: '#6D2077', short: 'Peter Mac' },
  'MCRI':                     { color: '#009FDA', short: 'MCRI' },
  'Florey Institute':         { color: '#FF6B00', short: 'Florey' },
  'Bio21 Institute':          { color: '#0F4C81', short: 'Bio21' },
  'Orygen':                   { color: '#E4022D', short: 'Orygen' },
  'Melbourne Bioinformatics': { color: '#005A8E', short: 'Melb. Bioinformatics' },
  'Melbourne Brain Centre':   { color: '#9B2335', short: 'Brain Centre' },
  'Royal Melbourne Hospital': { color: '#0066CC', short: 'RMH' },
  'CERA':                     { color: '#00A9CE', short: 'CERA' },
  'Bionics Institute':        { color: '#E31B23', short: 'Bionics' },
};

// ── Initialise ───────────────────────────────────────────
async function init() {
  try {
    // Load seminars
    const res = await fetch('seminars.json?t=' + Date.now());
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    allSeminars = data.seminars || [];

    // Show update time
    if (data.generated_at) {
      const d = new Date(data.generated_at);
      document.getElementById('update-time').textContent =
        'Updated ' + formatRelativeTime(d);
    }

    // Load scraper status (optional)
    try {
      const sr = await fetch('scraper_status.json?t=' + Date.now());
      if (sr.ok) {
        const sd = await sr.json();
        scraperStatus = sd.scrapers || {};
        renderScraperStatus();
      }
    } catch (_) { /* status file is optional */ }

    // Initialise institution filter (all checked by default)
    const institutions = [...new Set(allSeminars.map(s => s.institution))].sort();
    institutions.forEach(i => activeInstitutions.add(i));
    renderInstitutionFilter(institutions);

    render();

  } catch (err) {
    document.getElementById('seminars-container').innerHTML = `
      <div class="error-state">
        <span class="state-icon">⚠️</span>
        <div class="state-title">Could not load seminars</div>
        <div class="state-sub">${err.message}<br>Make sure <code>seminars.json</code> exists and run <code>python run_scrapers.py</code> to generate it.</div>
      </div>`;
  }
}

// ── Filter & Sort ────────────────────────────────────────
function getFiltered() {
  let seminars = [...allSeminars];

  // Institution filter
  seminars = seminars.filter(s => activeInstitutions.has(s.institution));

  // Date range
  if (dateFrom) seminars = seminars.filter(s => s.date && s.date >= dateFrom);
  if (dateTo)   seminars = seminars.filter(s => s.date && s.date <= dateTo);

  // Search
  if (searchQuery) {
    const q = searchQuery.toLowerCase();
    seminars = seminars.filter(s =>
      (s.title        || '').toLowerCase().includes(q) ||
      (s.speaker      || '').toLowerCase().includes(q) ||
      (s.abstract     || '').toLowerCase().includes(q) ||
      (s.affiliation  || '').toLowerCase().includes(q) ||
      (s.institution  || '').toLowerCase().includes(q) ||
      (s.location     || '').toLowerCase().includes(q)
    );
  }

  // Sort
  const sort = document.getElementById('sort-select').value;
  if (sort === 'date-asc') {
    seminars.sort((a, b) => (a.date || '').localeCompare(b.date || ''));
  } else if (sort === 'date-desc') {
    seminars.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  } else if (sort === 'institution') {
    seminars.sort((a, b) => a.institution.localeCompare(b.institution) || (a.date || '').localeCompare(b.date || ''));
  }

  return seminars;
}

// ── Render ───────────────────────────────────────────────
function render() {
  const filtered = getFiltered();
  const container = document.getElementById('seminars-container');
  const countEl = document.getElementById('count-display');
  const labelEl = document.getElementById('count-label');

  countEl.textContent = filtered.length;
  labelEl.textContent = filtered.length === 1 ? ' seminar' : ' upcoming seminars';

  // Update institution counts
  updateInstitutionCounts();

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <span class="state-icon">🔍</span>
        <div class="state-title">No seminars match your filters</div>
        <div class="state-sub">Try adjusting your search or date range, or check back later for new events.</div>
      </div>`;
    return;
  }

  // Group by date sections
  const today = todayISO();
  const weekEnd = addDays(today, 7);

  let html = '';
  let lastSection = null;

  const sort = document.getElementById('sort-select').value;

  filtered.forEach((s, idx) => {
    // Date section header
    if (sort !== 'institution') {
      let section = null;
      if (s.date === today) section = 'today';
      else if (s.date > today && s.date <= weekEnd) section = 'this-week';
      else if (s.date > weekEnd) section = 'upcoming';
      else section = 'other';

      if (section !== lastSection) {
        lastSection = section;
        if (section === 'today') {
          html += `<div class="date-section-header today"><span class="today-dot"></span>Today</div>`;
        } else if (section === 'this-week') {
          html += `<div class="date-section-header this-week">This Week</div>`;
        } else if (section === 'upcoming') {
          html += `<div class="date-section-header">Upcoming</div>`;
        }
      }
    }

    html += buildCard(s);
  });

  container.innerHTML = `<div class="seminars-grid">${html}</div>`;

  // Show/hide clear button
  const hasFilters = searchQuery || dateFrom || dateTo ||
    activeInstitutions.size < Object.keys(INSTITUTIONS).length;
  document.getElementById('clear-btn').classList.toggle('visible', hasFilters);
}

// ── Card Builder ─────────────────────────────────────────
function buildCard(s) {
  const meta = INSTITUTIONS[s.institution] || { color: '#38bdf8', short: s.institution };
  const color = s.institution_color || meta.color;

  const dateBlock = buildDateBlock(s.date);
  const timeTxt   = s.time ? formatTime(s.time) : '';
  const loc       = s.location || '';
  const speaker   = s.speaker || '';
  const hasBody   = s.abstract || speaker;

  // Highlight search terms
  const title = highlight(escHtml(s.title || 'Untitled'), searchQuery);

  const instPill = `<span class="inst-pill" style="color:${color};background:${color}18;border-color:${color}33">${escHtml(meta.short || s.institution)}</span>`;
  const onlineBadge = s.online ? `<span class="online-badge">🌐 Online</span>` : '';

  const metaItems = [
    timeTxt   ? `<span class="card-meta-item">${iconClock()}${escHtml(timeTxt)}</span>` : '',
    loc       ? `<span class="card-meta-item">${iconLocation()}${escHtml(loc)}</span>` : '',
    speaker   ? `<span class="card-meta-item">${iconPerson()}${escHtml(speaker)}</span>` : '',
  ].filter(Boolean).join('');

  const expandBtn = hasBody ? `
    <button class="expand-btn" onclick="toggleCard(this)" aria-label="Toggle details">
      ${iconChevron()}
    </button>` : '';

  const speakerBlock = speaker ? `
    <div class="card-speaker-block">
      <div class="speaker-avatar">${getInitials(speaker)}</div>
      <div class="speaker-info">
        <div class="speaker-name">${escHtml(speaker)}</div>
        ${s.affiliation ? `<div class="speaker-affil">${escHtml(s.affiliation)}</div>` : ''}
      </div>
    </div>` : '';

  const abstractHtml = s.abstract
    ? `<div class="card-abstract">${highlight(escHtml(s.abstract), searchQuery)}</div>`
    : '';

  const cardBody = hasBody ? `
    <div class="card-body">
      ${speakerBlock}
      ${abstractHtml}
      <div class="card-actions">
        ${s.url ? `<a class="btn-link btn-primary" href="${escAttr(s.url)}" target="_blank" rel="noopener">
          ${iconExternal()} View details
        </a>` : ''}
        ${s.url ? `<button class="btn-link btn-secondary" onclick="copyLink(event,'${escAttr(s.url)}')">
          ${iconCopy()} Copy link
        </button>` : ''}
      </div>
    </div>` : '';

  return `
    <div class="seminar-card" style="--inst-color:${color}" onclick="handleCardClick(event, this)">
      <div class="card-top">
        ${dateBlock}
        <div class="card-main">
          <div class="card-institution">${instPill}${onlineBadge}</div>
          <div class="card-title">${title}</div>
          <div class="card-meta">${metaItems}</div>
        </div>
        ${expandBtn}
      </div>
      ${cardBody}
    </div>`;
}

function buildDateBlock(dateISO) {
  if (!dateISO) return `<div class="card-date-block"><div class="date-day">?</div><div class="date-month">TBD</div></div>`;
  const d = new Date(dateISO + 'T12:00:00');
  const day   = d.getDate();
  const month = d.toLocaleString('en-AU', { month: 'short' }).toUpperCase();
  const year  = d.getFullYear();
  const today = new Date().getFullYear();
  return `
    <div class="card-date-block">
      <div class="date-day">${day}</div>
      <div class="date-month">${month}</div>
      ${year !== today ? `<div class="date-year">${year}</div>` : ''}
    </div>`;
}

// ── Institution filter ───────────────────────────────────
function renderInstitutionFilter(institutions) {
  const list = document.getElementById('institution-list');
  list.innerHTML = institutions.map(inst => {
    const meta = INSTITUTIONS[inst] || { color: '#38bdf8' };
    const color = meta.color;
    const count = allSeminars.filter(s => s.institution === inst).length;
    return `
      <label class="inst-checkbox">
        <input type="checkbox" checked
          style="--inst-color:${color}"
          onchange="toggleInstitution('${escAttr(inst)}', this.checked)"
          data-institution="${escAttr(inst)}" />
        <span class="inst-dot" style="background:${color}"></span>
        <span class="inst-name">${escHtml(inst)}</span>
        <span class="inst-count" data-count="${escAttr(inst)}">${count}</span>
      </label>`;
  }).join('');
}

function updateInstitutionCounts() {
  const filtered = getFiltered();
  const counts = {};
  filtered.forEach(s => counts[s.institution] = (counts[s.institution] || 0) + 1);

  document.querySelectorAll('[data-count]').forEach(el => {
    const inst = el.dataset.count;
    el.textContent = counts[inst] || 0;
  });
}

function toggleInstitution(institution, checked) {
  if (checked) activeInstitutions.add(institution);
  else activeInstitutions.delete(institution);
  render();
}

// ── Scraper Status ───────────────────────────────────────
function renderScraperStatus() {
  const panel = document.getElementById('status-panel');
  const grid  = document.getElementById('status-grid');
  if (!Object.keys(scraperStatus).length) return;

  panel.style.display = 'block';
  grid.innerHTML = Object.entries(scraperStatus).map(([key, s]) => {
    const cls = s.status === 'ok' ? 'status-ok' : s.status === 'empty' ? 'status-empty' : 'status-error';
    const icon = s.status === 'ok' ? '✓' : s.status === 'empty' ? '○' : '✗';
    return `
      <div class="status-row">
        <span class="status-name">${escHtml(s.name)}</span>
        <span class="${cls}">${icon} ${s.count}</span>
      </div>`;
  }).join('');
}

// ── Event handlers ───────────────────────────────────────
function handleCardClick(e, card) {
  // Don't toggle when clicking a link or button inside the card
  if (e.target.closest('a') || e.target.closest('button')) return;
  card.classList.toggle('expanded');
}

function toggleCard(btn) {
  btn.closest('.seminar-card').classList.toggle('expanded');
}

function clearFilters() {
  searchQuery = '';
  dateFrom = '';
  dateTo = '';
  document.getElementById('search').value = '';
  document.getElementById('date-from').value = '';
  document.getElementById('date-to').value = '';
  // Re-check all institutions
  document.querySelectorAll('[data-institution]').forEach(cb => {
    cb.checked = true;
    activeInstitutions.add(cb.dataset.institution);
  });
  render();
}

function copyLink(e, url) {
  e.stopPropagation();
  navigator.clipboard.writeText(url).then(() => {
    const btn = e.currentTarget;
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
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function escAttr(str) {
  if (!str) return '';
  return str.replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function highlight(html, query) {
  if (!query) return html;
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return html.replace(new RegExp(`(${escaped})`, 'gi'), '<mark class="highlight">$1</mark>');
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
  // Convert "13:00" → "1:00 PM"
  const [h, m] = t.split(':').map(Number);
  const ampm = h >= 12 ? 'PM' : 'AM';
  const h12 = h % 12 || 12;
  return `${h12}:${String(m).padStart(2,'0')} ${ampm}`;
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
    .map(w => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

// ── SVG Icons ────────────────────────────────────────────
const svgProps = 'width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"';

function iconClock()     { return `<svg ${svgProps}><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`; }
function iconLocation()  { return `<svg ${svgProps}><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>`; }
function iconPerson()    { return `<svg ${svgProps}><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`; }
function iconChevron()   { return `<svg ${svgProps}><polyline points="6 9 12 15 18 9"/></svg>`; }
function iconExternal()  { return `<svg ${svgProps}><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>`; }
function iconCopy()      { return `<svg ${svgProps}><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`; }

// ── Auto-refresh ─────────────────────────────────────────
// Re-fetch seminars.json every 30 minutes while the tab is open.
// Only re-renders if the data actually changed (compares generated_at timestamp).
let lastGeneratedAt = null;

async function checkForUpdates() {
  try {
    const res = await fetch('seminars.json?t=' + Date.now());
    if (!res.ok) return;
    const data = await res.json();
    if (data.generated_at && data.generated_at !== lastGeneratedAt) {
      lastGeneratedAt = data.generated_at;
      allSeminars = data.seminars || [];

      // Refresh institution filter for any new institutions
      const institutions = [...new Set(allSeminars.map(s => s.institution))].sort();
      institutions.forEach(i => { if (!activeInstitutions.has(i)) activeInstitutions.add(i); });
      renderInstitutionFilter(institutions);

      render();

      if (data.generated_at) {
        document.getElementById('update-time').textContent =
          'Updated ' + formatRelativeTime(new Date(data.generated_at));
      }
      console.log('[Parkville Seminars] Data refreshed:', data.total, 'seminars');
    }
  } catch (_) { /* silent — no network disrupts the UI */ }
}

// Poll every 30 minutes
setInterval(checkForUpdates, 30 * 60 * 1000);

// Also refresh when the tab becomes visible again (e.g. switching back from another app)
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') checkForUpdates();
});

// ── Boot ─────────────────────────────────────────────────
init().then(() => {
  // Store initial timestamp after first load
  fetch('seminars.json?t=' + Date.now())
    .then(r => r.json())
    .then(d => { lastGeneratedAt = d.generated_at || null; })
    .catch(() => {});
});
