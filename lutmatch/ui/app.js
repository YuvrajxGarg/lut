// Lut UI. Talks to Python through window.pywebview.api; Python pushes
// updates back by calling App.on(event, payload).
(function () {
  const ICONS = {
    upload: '<path d="M12 15V4"/><path d="m7 9 5-5 5 5"/><path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>',
    file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
    folder: '<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9L9.6 3.6A2 2 0 0 0 8.2 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2z"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
    sparkle: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 17v4M17 19h4"/>',
    layers: '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>',
    film: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 8h4M3 16h4M17 8h4M17 16h4"/>',
    image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    trash: '<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>',
    eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    reveal: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    alert: '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    download: '<path d="M12 4v11"/><path d="m7 10 5 5 5-5"/><path d="M4 20h16"/>',
    refresh: '<path d="M21 12a9 9 0 1 1-2.6-6.4L21 8"/><path d="M21 3v5h-5"/>',
    lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    bolt: '<path d="M13 2 3 14h9l-1 8 10-12h-9z"/>',
    eraser: '<path d="m7 21-4.3-4.3a1 1 0 0 1 0-1.4l10-10a1 1 0 0 1 1.4 0l5.6 5.6a1 1 0 0 1 0 1.4L11 21"/><path d="M22 21H7M5 11l9 9"/>',
    target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    cube: '<path d="m21 16-9 5-9-5V8l9-5 9 5z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
    wand: '<path d="m15 4 5 5L9 20H4v-5z"/><path d="M13 6l5 5"/>',
    swap: '<path d="M7 4 3 8l4 4"/><path d="M3 8h13"/><path d="m17 20 4-4-4-4"/><path d="M21 16H8"/>',  };
  const icon = (n) => `<svg class="i" viewBox="0 0 24 24">${ICONS[n] || ''}</svg>`;
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  document.querySelectorAll('[data-icon]').forEach((el) => {
    const svg = icon(el.dataset.icon);
    if (el.tagName === 'I') el.outerHTML = svg; else el.insertAdjacentHTML('afterbegin', svg);
  });

  const items = new Map(); // id -> clip
  let ref = null;
  let mode = 'beside', customDir = null, busy = false, lastDir = null;
  let api = null;
  let settings = {}, upd = null, modal = null, home = '';
  let claude = { has_key: false, hint: '' }, sources = [];
  const SHORT = { auto: 'Auto', rec709: 'Rec.709', slog3: 'S-Log3', vlog: 'V-Log', logc3: 'LogC3', logc4: 'LogC4', clog3: 'C-Log3',
    nlog: 'N-Log', flog: 'F-Log', flog2: 'F-Log2', applelog: 'Apple Log', hlg: 'HLG', pq: 'PQ' };
  const short = (k) => SHORT[k] || k || 'Auto';
  const tilde = (p) => (home && p && p.startsWith(home) ? '~' + p.slice(home.length) : p);
  const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;

  // ---------- reference ----------
  function renderRef() {
    const has = !!ref;
    $('#ref-slot').classList.toggle('filled', has);
    $('#ref-slot .ref-empty').classList.toggle('hidden', has);
    $('#ref-slot .ref-full').classList.toggle('hidden', !has);
    if (has) {
      $('#ref-name').textContent = ref.status === 'failed' ? (ref.error || 'Couldn’t read it') : ref.name;
      $('#ref-slot').classList.toggle('bad', ref.status === 'failed');
      $('#ref-slot').classList.toggle('loading', ref.status === 'loading');
      const img = $('#ref-img');
      if (ref.thumb) { img.src = ref.thumb; img.classList.remove('hidden'); } else img.classList.add('hidden');
    }
    refresh();
  }

  // ---------- clip cards ----------
  const STATUS = {
    loading: ['', 'Reading', true], ready: ['', 'Ready'], matching: ['', 'Matching', true], refining: ['', 'Claude', true],
    done: ['done', 'Done', false, 'check'], failed: ['failed', 'Failed', false, 'alert'], unsupported: ['failed', 'Can’t read'],
  };
  function statusPill(it) {
    let [cls, text, spin, ic] = STATUS[it.status] || ['', it.status];
    if (it.status === 'matching' && it.kind === 'video' && it.progress > 0.02) text = `Grading ${Math.round(it.progress * 100)}%`;
    return `<span class="status ${cls} ${spin ? 'busy' : ''}">${ic ? icon(ic) : ''}${text}</span>`;
  }

  function compareHTML(it) {
    if (!it.before) return `<div class="cmp placeholder">${it.status === 'unsupported' ? icon('alert') : '<span class="spinner"></span>'}</div>`;
    const after = it.after && ref && ref.status === 'ready';
    const pos = cmpPos.get(it.id) ?? 50;
    return `<div class="cmp" style="--pos:${pos}%">
      <img class="before" src="${it.before}" draggable="false">
      ${after ? `<img class="after" src="${it.after}" draggable="false"><div class="handle"><i></i></div>
        <span class="cap l">Before</span><span class="cap r">Matched</span>` : `<span class="cap l solo">${ref ? 'Measuring…' : 'Add a reference to preview'}</span>`}
    </div>`;
  }

  function cardHTML(it) {
    const sub = it.status === 'unsupported' || (it.status === 'failed' && it.error)
      ? `<span class="err">${esc(it.error)}</span>`
      : it.status === 'done'
        ? `<span class="sub">${it.graded ? 'LUT and graded copy saved' : 'LUT saved'}</span>`
        : `<span class="sub">${esc(it.ext)} · ${esc(it.size)}${it.source && it.source !== 'rec709' ? ` <span class="src-chip">${esc(short(it.source))}</span>` : ''}</span>`;
    const note = it.warn ? `<div class="claude-note warn">${icon('alert')}<span title="${esc(it.warn)}">Claude skipped: ${esc(it.warn)}</span></div>`
      : it.note ? `<div class="claude-note">${icon('sparkle')}<span title="${esc(it.note)}">${esc(it.note)}</span></div>` : '';
    return `${compareHTML(it)}
      ${it.status === 'matching' ? `<div class="bar"><div style="width:${Math.round((it.progress || 0) * 100)}%"></div></div>` : ''}
      <div class="card-foot">
        <div class="meta"><div class="title">${esc(it.name)}</div>${sub}${note}</div>
        ${statusPill(it)}
      </div>
      <div class="acts">
        ${it.cube ? `<button class="btn-icon dark" data-act="cube" title="Show the LUT">${icon('cube')}</button>` : ''}
        ${it.graded ? `<button class="btn-icon dark" data-act="graded" title="Show the graded copy">${icon('reveal')}</button>` : ''}
        ${it.before && it.status !== 'matching' ? `<button class="btn-icon dark" data-act="ref" title="Use as reference">${icon('target')}</button>` : ''}
        <button class="btn-icon dark" data-act="remove" title="Remove">${icon('x')}</button>
      </div>`;
  }

  const cmpPos = new Map();
  function upsert(it) {
    items.set(it.id, it);
    let el = document.getElementById('clip-' + it.id);
    if (!el) {
      el = document.createElement('div');
      el.className = 'clip';
      el.id = 'clip-' + it.id;
      el.dataset.id = it.id;
      $('#list').appendChild(el);
    }
    el.innerHTML = cardHTML(it);
    refresh();
  }
  function removeCard(id) {
    items.delete(id);
    const el = document.getElementById('clip-' + id);
    if (el) el.remove();
    refresh();
  }

  function refresh() {
    const all = [...items.values()];
    const done = all.filter((i) => i.status === 'done').length;
    const todo = all.filter((i) => ['ready', 'failed', 'done'].includes(i.status)).length;
    const pending = all.filter((i) => ['ready', 'failed'].includes(i.status)).length;
    const refReady = ref && ref.status === 'ready';
    $('#empty').classList.toggle('hidden', all.length > 0);
    $('#clear').classList.toggle('hidden', !all.length || busy);
    $('#open-out').classList.toggle('hidden', !lastDir);
    $('#stats').innerHTML = all.length ? `
      <span class="stat"><b>${all.length}</b>clip${all.length === 1 ? '' : 's'}</span>
      ${done ? `<span class="stat lime"><b>${done}</b>matched</span>` : ''}` : '';
    const btn = $('#match-btn');
    btn.disabled = busy || !todo || !refReady || (mode === 'custom' && !customDir);
    const n = pending || todo;
    btn.querySelector('span').textContent = busy ? 'Matching…' : !ref ? 'Add a reference' : !refReady ? 'Reading reference…' :
      !todo ? 'Add clips' : (pending ? `Match ${plural(n, 'clip')}` : `Match ${plural(n, 'clip')} again`);
  }

  function toast(text, err, action) {
    const t = document.createElement('div');
    t.className = 'toast' + (err ? ' err' : '');
    t.innerHTML = icon(err ? 'alert' : 'check') + `<span>${esc(text)}</span>`;
    if (action) {
      const b = document.createElement('button');
      b.textContent = action.label;
      b.onclick = action.run;
      t.appendChild(b);
    }
    $('#toasts').appendChild(t);
    setTimeout(() => { t.style.transition = 'opacity .3s'; t.style.opacity = 0; setTimeout(() => t.remove(), 300); }, 4200);
  }

  // ---------- modals ----------
  function closeModal() {
    const panel = document.querySelector('#modal-root #output-panel');
    if (panel) $('#output-holder').appendChild(panel);
    $('#modal-root').innerHTML = ''; modal = null;
  }
  function showModal(name, html, onClick, cls) {
    const box = modal === name && $('#modal-root .modal');
    modal = name;
    if (box) {
      // Same dialog again: swap what's inside so the dark backdrop doesn't fade in again (that read as the window blinking).
      const panel = document.querySelector('#modal-root #output-panel');
      if (panel) $('#output-holder').appendChild(panel);
      box.className = `modal ${cls || ''}`;
      box.innerHTML = html;
    } else {
      $('#modal-root').innerHTML = `<div class="modal-back"><div class="modal ${cls || ''}">${html}</div></div>`;
    }
    $('#modal-root .modal-back').onclick = (e) => {
      if (e.target.classList.contains('modal-back')) return closeModal();
      const el = e.target.closest('[data-m]');
      if (el) onClick(el.dataset.m, el);
    };
  }
  const sw = (on) => `<span class="switch ${on ? 'on' : ''}"></span>`;
  const opt = (key, title, detail) => `<button class="opt" data-m="toggle" data-key="${key}"><div class="t"><b>${title}</b><span>${detail}</span></div>${sw(settings[key])}</button>`;
  const ago = (iso) => {
    if (!iso) return 'Never checked';
    const s = (Date.now() - new Date(iso).getTime()) / 1000;
    if (s < 60) return 'Checked just now';
    if (s < 3600) return `Checked ${Math.round(s / 60)} min ago`;
    if (s < 86400) return `Checked ${Math.round(s / 3600)} h ago`;
    return 'Checked ' + new Date(iso).toLocaleDateString();
  };
  function updateLine() {
    if (!upd) return ['', ''];
    switch (upd.phase) {
      case 'checking': return ['Checking for updates…', ''];
      case 'uptodate': return ["You're up to date", 'ok'];
      case 'available': return [`Version ${upd.latest} is available`, 'ok'];
      case 'downloading': return [upd.progress >= 1 ? `Preparing ${upd.latest}…` : `Downloading ${upd.latest}… ${Math.round(upd.progress * 100)}%`, ''];
      case 'ready': return [`Version ${upd.latest} is ready to install`, 'ok'];
      case 'installing': return ['Installing…', ''];
      case 'failed': return [upd.error || 'Update failed', 'bad'];
      default: return [ago(upd.last_checked), ''];
    }
  }
  function renderUpdateRow() {
    const el = $('#upd-row');
    if (!el) return;
    const [line, cls] = updateLine();
    const has = upd && ['available', 'downloading', 'ready'].includes(upd.phase);
    el.innerHTML = `<div class="t"><b>Lut ${esc(upd ? upd.current : '')}</b><span class="${cls}">${esc(line)}</span></div>
      ${has ? `<button class="btn-quiet" data-m="see-update">${icon('download')}See update</button>` : `<button class="btn-quiet" data-m="check" ${upd && upd.phase === 'checking' ? 'disabled' : ''}>${icon('refresh')}Check now</button>`}`;
  }
  function openSettings() {
    showModal('settings', `
      <div class="modal-title"><h2>Settings</h2><button class="btn-icon" data-m="close">${icon('x')}</button></div>
      <div class="label">Updates</div>
      <div class="group">
        <div class="ver-row" id="upd-row"></div>
        ${opt('auto_check', 'Check for updates automatically', 'Looks for a new version at launch and every few hours')}
        ${opt('auto_install', 'Download and install updates automatically', 'Downloads in the background and installs when you quit')}
      </div>
      <div class="label">Claude</div>
      <div class="group" id="claude-group"></div>
      <div class="label">About</div>
      <div class="about">Lut measures the colour of the reference and the clip in OKLab, matches white balance, saturation and contrast, and bakes the result into a 33-point .cube LUT. Graded videos are re-encoded with that LUT through ffmpeg; audio is copied as is. Everything runs on this computer, unless you turn on Refine with Claude: then small preview frames (never the clips) go to Claude for a check.</div>
      <div class="foot"><button class="link" data-m="page">Release notes on GitHub</button><button class="link" data-m="welcome" style="margin-right:0">Show welcome screen</button></div>`,
      async (m, el) => {
        if (m === 'close') closeModal();
        else if (m === 'toggle') {
          const k = el.dataset.key;
          settings = await api.set_setting(k, !settings[k]);
          el.querySelector('.switch').classList.toggle('on', !!settings[k]);
        } else if (m === 'check') { upd = await api.check_updates(); renderUpdateRow(); renderPill(); }
        else if (m === 'see-update') openUpdate();
        else if (m === 'page') api.open_url(upd ? upd.page : '');
        else if (m === 'welcome') { closeModal(); showWelcome(); }
        else if (m === 'key-save' || m === 'key-remove') await saveKey(m === 'key-remove');
        else if (m === 'console') api.open_url('https://console.anthropic.com/settings/keys');
      }, 'settings');
    renderUpdateRow();
    renderClaudeGroup();
  }

  function renderClaudeGroup() {
    const g = $('#claude-group');
    if (!g) return;
    g.innerHTML = `<div class="ver-row"><div class="t"><b>API key</b><span class="${claude.has_key ? 'ok' : ''}">${claude.has_key
      ? (claude.env ? 'Using ANTHROPIC_API_KEY from the environment' : `Saved in your ${document.body.classList.contains('win') ? 'Windows Credential Manager' : 'Keychain'} ${esc(claude.hint)}`)
      : 'Not set. Refine with Claude stays off until you add one.'}</span></div>
      ${claude.has_key && !claude.env ? `<button class="btn-quiet" data-m="key-remove">${icon('trash')}Remove</button>` : ''}</div>
      <div><div class="key-row" style="flex:1"><input id="key-input" type="password" placeholder="${claude.has_key ? 'Paste a new key to replace it' : 'sk-ant-…'}" autocomplete="off" spellcheck="false">
      <button class="btn-quiet" data-m="key-save">Save</button></div></div>
      <div><span class="hint">Your key stays on this computer. Each refined clip sends a few small preview frames to Claude and costs a few cents. <button class="link" data-m="console">Get a key</button></span></div>`;
    const inp = $('#key-input');
    if (inp) inp.onkeydown = (e) => { if (e.key === 'Enter') saveKey(false); };
  }
  async function saveKey(remove) {
    const inp = $('#key-input');
    const v = remove ? '' : (inp ? inp.value.trim() : '');
    if (!remove && !v) return;
    claude = await api.set_claude_key(v);
    if (claude.error) toast(claude.error, true);
    else toast(remove ? 'API key removed' : 'API key saved');
    if (!remove && claude.has_key && !settings.refine) settings = await api.set_setting('refine', true);
    if (remove) settings = await api.info().then((i) => i.settings);
    renderClaudeGroup();
    renderRefine();
  }
  function renderRefine() {
    $('#refine-row .switch').classList.toggle('on', !!(settings.refine && claude.has_key));
    $('#refine-sub').textContent = claude.has_key ? 'Claude checks each match and fine-tunes it' : 'Add your Claude API key to turn this on';
  }
  function renderSource() {
    $('#source-sum').textContent = `Clips ${short(settings.source)} · Reference ${short(settings.ref_source)}`;
  }
  function openSources() {
    const grid = (key) => `<div class="src-grid" data-key="${key}">${[['auto', 'Auto']].concat(sources).map(([k, label]) =>
      `<button data-m="src" data-key="${key}" data-v="${k}" class="${(settings[key] || 'auto') === k ? 'on' : ''}" title="${esc(label)}">${esc(short(k))}</button>`).join('')}</div>`;
    showModal('sources', `<div class="modal-title"><h2>Shot in</h2><button class="btn-icon" data-m="close">${icon('x')}</button></div>
      <div class="src-hint">Pick the camera profile so log footage is turned into normal Rec.709 before it’s matched. The conversion is built into the .cube, so it goes straight onto your log clips in Resolve, Premiere or Final Cut. Auto picks HLG or PQ when the file is tagged that way, otherwise Rec.709.</div>
      <div class="label">Clips</div>${grid('source')}
      <div class="label">Reference</div>${grid('ref_source')}`,
      async (m, el) => {
        if (m === 'close') closeModal();
        else if (m === 'src') {
          settings = await api.set_setting(el.dataset.key, el.dataset.v);
          el.parentNode.querySelectorAll('button').forEach((b) => b.classList.toggle('on', b === el));
          renderSource();
        }
      }, 'sources');
  }

  function renderPill() {
    const p = $('#update-pill');
    if (!upd || !['available', 'downloading', 'ready', 'installing'].includes(upd.phase)) { p.classList.add('hidden'); return; }
    p.classList.remove('hidden');
    p.innerHTML = upd.phase === 'ready' ? `${icon('refresh')}Restart to update` :
      upd.phase === 'downloading' ? (upd.progress >= 1 ? `${icon('refresh')}Preparing update…` : `${icon('download')}Updating ${Math.round(upd.progress * 100)}%`) :
      upd.phase === 'installing' ? `${icon('refresh')}Installing…` : `${icon('download')}Update to ${esc(upd.latest)}`;
  }

  // Progress ticks arrive several times a second: only the bar and its line change.
  function patchUpdateProgress() {
    const bar = $('#modal-root .progress > div');
    const line = $('#modal-root .update-hero p');
    if (!bar || !line) return false;
    const pct = Math.round((upd.progress || 0) * 100);
    bar.style.width = pct + '%';
    line.textContent = pct >= 100 ? 'Checking and unpacking the update…' : `Downloading… ${pct}%`;
    return true;
  }

  function openUpdate() {
    if (!upd) return;
    const ph = upd.phase;
    const pct = Math.round((upd.progress || 0) * 100);
    const sub = ph === 'ready' ? 'Downloaded and ready. Restart now, or it installs the next time you quit.' :
      ph === 'downloading' ? (pct >= 100 ? 'Checking and unpacking the update…' : `Downloading… ${pct}%`) : ph === 'installing' ? 'Installing and restarting…' :
      ph === 'failed' ? (upd.error || 'Something went wrong.') : ph === 'uptodate' ? "You're on the newest version." :
      `You have ${esc(upd.current)}.` + (upd.can_install ? '' : ' This copy runs from source, so the download page opens instead.');
    const primary = ph === 'ready' ? `<button class="btn-primary inline" data-m="install">${icon('refresh')}Restart to update</button>` :
      ph === 'available' || ph === 'failed' ? `<button class="btn-primary inline" data-m="${upd.can_install ? 'download' : 'page'}">${icon('download')}${upd.can_install ? 'Download update' : 'Open download page'}</button>` : '';
    showModal('update', `
      <div class="update-hero">
        <div class="logomark lg"><span class="mark lut" style="--size:30px">lut<span class="graded" aria-hidden="true">lut</span><i class="wipe"></i></span></div>
        <div><h2>${upd.latest ? 'Lut ' + esc(upd.latest) : 'Updates'}</h2><p class="${ph === 'failed' ? 'err' : ''}">${sub}</p></div>
      </div>
      ${ph === 'downloading' ? `<div class="progress"><div style="width:${pct}%"></div></div>` : ''}
      ${upd.notes ? `<div class="label">What's new</div><div class="notes">${esc(upd.notes)}</div>` : ''}
      <div class="foot"><button class="link" data-m="page">View on GitHub</button><button class="btn-quiet" data-m="close">Later</button>${primary}</div>`,
      (m) => {
        if (m === 'close') closeModal();
        else if (m === 'install') api.install_update();
        else if (m === 'download') api.download_update();
        else if (m === 'page') api.open_url(upd.page);
      });
  }

  // ---------- welcome (first launch) ----------
  function showWelcome() {
    const w = $('#welcome');
    let page = 0;
    const pages = [
      () => `<div class="logomark lg" style="width:96px;height:96px;border-radius:26px"><span class="mark lut" style="--size:38px">lut<span class="graded" aria-hidden="true">lut</span><i class="wipe"></i></span></div>
        <h1>Welcome to Lut</h1>
        <p class="lead">Drop a frame with the look you want and the clip you shot.<br>Lut matches the colour and hands you a LUT and a graded copy.</p>
        <div class="facts">
          <div class="card fact">${icon('cube')}<b>A real LUT</b><span>A 33-point .cube that loads in Resolve, Premiere, Final Cut and OBS.</span></div>
          <div class="card fact">${icon('lock')}<b>Originals untouched</b><span>Graded copies are saved separately. Your files never change.</span></div>
          <div class="card fact">${icon('shield')}<b>Private</b><span>Matching happens on this computer. Nothing is uploaded.</span></div>
        </div>`,
      () => `<h1>Stay up to date</h1>
        <p class="lead">New versions arrive from GitHub with support for more apps and formats.</p>
        <div class="group">
          ${opt('auto_check', 'Check for updates automatically', 'Looks for a new version at launch and every few hours')}
          ${opt('auto_install', 'Download and install updates automatically', 'Downloads in the background and installs when you quit')}
        </div>`,
    ];
    const render = () => {
      w.innerHTML = `<div class="glow"></div><div class="dots">${pages.map((_, i) => `<i class="${i <= page ? 'on' : ''} ${i === page ? 'cur' : ''}"></i>`).join('')}</div>
        <div class="page">${pages[page]()}</div>
        <div class="foot">${page ? '<button class="btn-quiet" data-w="back">Back</button>' : ''}
          <button class="btn-primary" data-w="next">${page === pages.length - 1 ? 'Get started' : 'Continue'}</button></div>`;
    };
    w.onclick = async (e) => {
      const t = e.target.closest('[data-w],[data-m]');
      if (!t) return;
      if (t.dataset.m === 'toggle') {
        const k = t.dataset.key;
        settings = await api.set_setting(k, !settings[k]);
        t.querySelector('.switch').classList.toggle('on', !!settings[k]);
      } else if (t.dataset.w === 'back') { page--; render(); }
      else if (t.dataset.w === 'next') {
        if (page < pages.length - 1) { page++; render(); }
        else { w.classList.add('hidden'); settings = await api.set_setting('welcomed', true); }
      }
    };
    render();
    w.classList.remove('hidden');
  }


  // ---------- events from Python ----------
  window.App = {
    on(event, p) {
      if (event === 'upsert') upsert(p);
      else if (event === 'removed') removeCard(p.id);
      else if (event === 'ref') { ref = p; renderRef(); }
      else if (event === 'busy') {
        busy = p.busy;
        $('#progress').classList.toggle('hidden', !busy);
        if (busy) $('#progress > div').style.width = '0%';
        refresh();
      } else if (event === 'progress') {
        $('#progress > div').style.width = (100 * p.done / p.total) + '%';
        if (p.id != null) {
          const it = items.get(p.id);
          if (it) {
            it.progress = p.p;
            const el = document.getElementById('clip-' + p.id);
            const bar = el && el.querySelector('.bar > div');
            if (bar) bar.style.width = Math.round(p.p * 100) + '%';
            const pill = el && el.querySelector('.status');
            if (pill && it.kind === 'video' && p.p > 0.02) pill.lastChild.textContent = `Grading ${Math.round(p.p * 100)}%`;
          }
        }
      } else if (event === 'finished') {
        if (p.dir) { lastDir = p.dir; if (mode !== 'custom') $('#save-path').textContent = tilde(p.dir); }
        refresh();
        const failed = p.total - p.ok;
        toast(failed ? `Matched ${p.ok} of ${p.total} clips` : `Matched ${plural(p.ok, 'clip')}`, !!failed,
          p.dir ? { label: 'Show', run: () => api.reveal(p.dir) } : null);
      } else if (event === 'toast') toast(p.text, p.err);
      else if (event === 'update') {
        const prev = upd && upd.phase;
        upd = p;
        renderPill();
        if (modal === 'update' && !(prev === 'downloading' && p.phase === 'downloading' && patchUpdateProgress())) openUpdate();
        else if (modal === 'settings') renderUpdateRow();
        if (prev !== 'ready' && p.phase === 'ready' && modal !== 'update')
          toast(`Version ${p.latest} is ready`, false, { label: 'Restart', run: () => api.install_update() });
      }
    },
  };

  // ---------- user actions ----------
  $('#ref-slot').onclick = () => !busy && api.pick_reference();
  $('#dropzone').onclick = () => api.pick_clips();
  $('#add-folder').onclick = () => api.pick_folder();
  $('#match-btn').onclick = () => api.match(mode, customDir);
  $('#open-out').onclick = () => lastDir && api.reveal(lastDir);
  $('#clear').onclick = () => { api.clear(); items.clear(); $('#list').innerHTML = ''; lastDir = null; refresh(); };

  // strength: preview follows the slider (debounced), the value is saved on release
  let sTimer = null;
  const strength = $('#strength');
  const paintStrength = () => {
    $('#strength-val').textContent = strength.value + '%';
    strength.style.setProperty('--fill', strength.value + '%');
  };
  strength.oninput = () => {
    paintStrength();
    clearTimeout(sTimer);
    sTimer = setTimeout(() => api.set_setting('strength', +strength.value).then((s) => { settings = s; }), 140);
  };
  $('#keep-luma').onclick = async () => {
    settings = await api.set_setting('keep_luma', !settings.keep_luma);
    $('#keep-luma .switch').classList.toggle('on', !!settings.keep_luma);
  };
  function setTabs(sel, v) { document.querySelectorAll(sel + ' button').forEach((b) => b.classList.toggle('on', b.dataset.v === v)); }
  $('#export-mode').onclick = async (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    settings = await api.set_setting('lut_only', b.dataset.v === 'lut');
    setTabs('#export-mode', b.dataset.v);
    renderOutput();
  };
  $('#codec').onclick = async (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    settings = await api.set_setting('codec', b.dataset.v);
    setTabs('#codec', b.dataset.v);
    renderOutput();
  };
  const CODEC = { h264: ['H.264', 'Plays everywhere. Small files, high quality (CRF 16).'],
    hevc: ['HEVC', 'About half the size of H.264 at the same quality.'],
    prores: ['ProRes', '10-bit ProRes 422 HQ in a .mov, for grading further.'] };
  function renderOutput() {
    const c = CODEC[settings.codec] || CODEC.h264;
    $('#codec-wrap').classList.toggle('hidden', !!settings.lut_only);
    $('#codec-hint').textContent = c[1];
    $('#open-after .switch').classList.toggle('on', !!settings.open_after);
    const where = mode === 'custom' && customDir ? (customDir.split(/[\\/]/).filter(Boolean).pop() || customDir) : 'beside originals';
    $('#output-sum').textContent = (settings.lut_only ? 'LUT only' : 'LUT + ' + c[0]) + ' · ' + where;
  }
  $('#output-row').onclick = () => {
    showModal('output', `<div class="modal-title"><h2>Output</h2><button class="btn-icon" data-m="close">${icon('x')}</button></div><div id="output-slot"></div>`,
      (m) => { if (m === 'close') closeModal(); }, 'output');
    $('#output-slot').replaceWith($('#output-panel'));
  };
  $('#source-row').onclick = () => openSources();
  $('#refine-row').onclick = async () => {
    if (!claude.has_key) { openSettings(); setTimeout(() => { const i = $('#key-input'); if (i) i.focus(); }, 50); return; }
    settings = await api.set_setting('refine', !settings.refine);
    renderRefine();
  };
  $('#open-after').onclick = async () => { settings = await api.set_setting('open_after', !settings.open_after); renderOutput(); };

  async function pickCustom() {
    const d = await api.choose_output();
    if (d) { customDir = d; api.set_setting('custom_dir', d); }
    return !!customDir;
  }
  function setMode(m) {
    mode = m;
    document.querySelectorAll('#out-mode button').forEach((x) => x.classList.toggle('on', x.dataset.mode === m));
    $('#custom-row').classList.toggle('hidden', m !== 'custom');
    $('#custom-path').textContent = tilde(customDir) || '';
    $('#save-path').textContent = m === 'custom' && customDir ? tilde(customDir) : 'a “graded” folder beside each clip';
    renderOutput();
    refresh();
  }
  $('#out-mode').onclick = async (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.mode === 'custom' && !customDir && !(await pickCustom())) return;
    setMode(b.dataset.mode);
    api.set_setting('out_mode', mode);
  };
  $('#custom-row').onclick = async () => { if (await pickCustom()) setMode('custom'); };
  $('#save-row').onclick = () => {
    const target = mode === 'custom' && customDir ? customDir : lastDir;
    if (target) api.reveal(target);
  };

  // card actions + the before/after wipe (follows the pointer)
  $('#list').onclick = (e) => {
    const card = e.target.closest('.clip');
    if (!card) return;
    const it = items.get(+card.dataset.id);
    const act = e.target.closest('[data-act]');
    if (!act || !it) return;
    const a = act.dataset.act;
    if (a === 'cube') api.reveal(it.cube);
    else if (a === 'graded') api.reveal(it.graded);
    else if (a === 'ref' && !busy) api.make_reference(it.id);
    else if (a === 'remove' && !busy) { api.remove(it.id); removeCard(it.id); }
  };
  $('#list').addEventListener('pointermove', (e) => {
    const cmp = e.target.closest('.cmp');
    if (!cmp || !cmp.querySelector('.after')) return;
    const r = cmp.getBoundingClientRect();
    const pos = Math.max(0, Math.min(100, ((e.clientX - r.left) / r.width) * 100));
    cmp.style.setProperty('--pos', pos + '%');
    cmpPos.set(+cmp.closest('.clip').dataset.id, pos);
  });

  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });
  $('#open-settings').onclick = () => openSettings();
  $('#update-pill').onclick = () => openUpdate();

  // Drag overlay. Python receives the drop itself (with full paths) and asks which
  // half it landed on: left = reference, right = clips.
  let depth = 0;
  window.__lutZone = '';
  const showDrop = (on) => { $('#drop').classList.toggle('hidden', !on); document.body.classList.toggle('dragging', on); };
  const zoneAt = (x) => (x < window.innerWidth / 2 ? 'ref' : 'clips');
  const markZone = (z) => document.querySelectorAll('.drop-half').forEach((h) => h.classList.toggle('on', h.dataset.zone === z));
  document.addEventListener('dragenter', (e) => { e.preventDefault(); depth++; showDrop(true); });
  document.addEventListener('dragover', (e) => { e.preventDefault(); window.__lutZone = zoneAt(e.clientX); markZone(window.__lutZone); });
  document.addEventListener('dragleave', () => { if (--depth <= 0) { depth = 0; showDrop(false); } });
  document.addEventListener('drop', (e) => { e.preventDefault(); window.__lutZone = zoneAt(e.clientX); depth = 0; showDrop(false); });

  // ---------- start ----------
  async function start(a) {
    api = a;
    const info = await api.info();
    document.body.classList.add(info.platform === 'darwin' ? 'mac' : info.platform.startsWith('win') ? 'win' : 'other');
    $('#version').textContent = 'v' + info.version;
    settings = info.settings || {};
    home = info.home || '';
    upd = info.update;
    ref = info.ref || null;
    claude = info.claude || claude;
    sources = info.sources || [];
    if (settings.custom_dir) customDir = settings.custom_dir;
    strength.value = settings.strength == null ? 100 : settings.strength;
    paintStrength();
    $('#keep-luma .switch').classList.toggle('on', !!settings.keep_luma);
    setTabs('#export-mode', settings.lut_only ? 'lut' : 'graded');
    setTabs('#codec', settings.codec || 'h264');
    setMode(settings.out_mode === 'custom' && customDir ? 'custom' : 'beside');
    renderRef();
    renderSource();
    renderRefine();
    renderPill();
    if (!settings.welcomed) setTimeout(showWelcome, 1500);
    $('#ffmpeg-note').innerHTML = info.ffmpeg ? '<i class="dot"></i>Photos and videos supported' : '<i class="dot bad"></i>Videos need ffmpeg (see README)';
    refresh();
    setTimeout(() => { $('#splash').classList.add('out'); $('#app').classList.add('in'); }, 1500);
    setTimeout(() => $('#splash').remove(), 2150);
  }

  // Demo data for previewing the UI in a plain browser (open index.html?demo).
  function demoApi() {
    const scene = (hue, sat, light, w = 640, h = 360) => {
      const c = document.createElement('canvas'); c.width = w; c.height = h;
      const g = c.getContext('2d');
      const sky = g.createLinearGradient(0, 0, 0, h);
      sky.addColorStop(0, `hsl(${hue},${sat}%,${light + 25}%)`); sky.addColorStop(0.6, `hsl(${hue + 20},${sat}%,${light + 5}%)`); sky.addColorStop(1, `hsl(${hue + 40},${sat - 10}%,${light - 20}%)`);
      g.fillStyle = sky; g.fillRect(0, 0, w, h);
      g.fillStyle = `hsl(${hue + 180},${sat}%,${light + 20}%)`; g.beginPath(); g.arc(w * 0.7, h * 0.35, h * 0.12, 0, 7); g.fill();
      g.fillStyle = `hsl(${hue + 60},${sat - 15}%,${Math.max(5, light - 25)}%)`;
      g.beginPath(); g.moveTo(0, h); g.lineTo(0, h * .7); g.lineTo(w * .3, h * .5); g.lineTo(w * .55, h * .72); g.lineTo(w * .8, h * .55); g.lineTo(w, h * .68); g.lineTo(w, h); g.fill();
      g.fillStyle = `hsl(25,45%,${light + 10}%)`; g.beginPath(); g.ellipse(w * .3, h * .82, 30, 52, 0, 0, 7); g.fill();
      return c.toDataURL('image/jpeg', 0.85);
    };
    const sample = [
      { name: 'A001_C004_drone.mov', ext: 'MOV', kind: 'video', size: '1.8 GB', hue: 200, sat: 20, l: 45 },
      { name: 'higgsfield_shot_03.mp4', ext: 'MP4', kind: 'video', size: '64.2 MB', hue: 260, sat: 55, l: 40 },
      { name: 'interview_cam_b.mp4', ext: 'MP4', kind: 'video', size: '912.4 MB', hue: 120, sat: 15, l: 50 },
      { name: 'still_0042.jpg', ext: 'JPG', kind: 'image', size: '6.1 MB', hue: 180, sat: 30, l: 35 },
    ];
    let n = 0;
    const add = () => sample.forEach((s, i) => {
      const it = { id: ++n, name: s.name, ext: s.ext, kind: s.kind, size: s.size, path: '/Users/demo/Footage/' + s.name, folder: '/Users/demo/Footage', status: 'loading' };
      upsert(it);
      setTimeout(() => upsert(Object.assign({}, it, { status: 'ready', before: scene(s.hue, s.sat, s.l), after: scene(28, 62, 38) })), 300 + i * 150);
    });
    const setRef = () => {
      App.on('ref', { name: 'golden_hour_reference.jpg', kind: 'image', status: 'loading' });
      setTimeout(() => App.on('ref', { name: 'golden_hour_reference.jpg', kind: 'image', status: 'ready', thumb: scene(28, 62, 38) }), 250);
    };
    return {
      info: async () => ({ version: '1.0.0', ffmpeg: true, platform: 'darwin', home: '/Users/demo',
        settings: { out_mode: 'beside', open_after: false, strength: 85, keep_luma: false, lut_only: false, codec: 'h264', source: 'auto', ref_source: 'auto', refine: location.search.includes('key'), auto_check: true, auto_install: true, welcomed: !location.search.includes('welcome') },
        update: { phase: location.search.includes('update') ? 'ready' : 'uptodate', current: '1.0.0', latest: '1.1.0', progress: 0, can_install: true,
          notes: '- Match to a whole reference clip\n- Faster previews', page: 'https://github.com', last_checked: new Date().toISOString() }, ref: null,
        claude: { has_key: location.search.includes('key'), hint: '…3f9a' },
        sources: [['rec709', 'Rec.709 / normal'], ['slog3', 'Sony S-Log3'], ['vlog', 'Panasonic V-Log'], ['logc3', 'ARRI LogC3'], ['logc4', 'ARRI LogC4'], ['clog3', 'Canon Log 3'], ['nlog', 'Nikon N-Log'], ['flog', 'Fujifilm F-Log'], ['flog2', 'Fujifilm F-Log2'], ['applelog', 'Apple Log'], ['hlg', 'HLG'], ['pq', 'PQ']] }),
      set_claude_key: async (k) => ({ has_key: !!k, hint: k ? '…' + k.slice(-4) : '' }),
      set_setting: async (k, v) => { settings[k] = v; return Object.assign({}, settings); },
      check_updates: async () => upd, download_update() {}, install_update() {}, open_url() {},
      pick_reference: setRef, pick_clips: add, pick_folder: add, choose_output: async () => '/Users/demo/Desktop/Graded',
      match: () => {
        App.on('busy', { busy: true });
        const todo = [...items.values()].filter((i) => ['ready', 'failed', 'done'].includes(i.status));
        todo.forEach((it, k) => {
          setTimeout(() => upsert(Object.assign({}, it, { status: 'matching', progress: 0 })), k * 900);
          for (let j = 1; j <= 4; j++) setTimeout(() => App.on('progress', { id: it.id, p: j / 5, done: k + j / 5, total: todo.length }), k * 900 + j * 160);
          setTimeout(() => { upsert(Object.assign({}, it, { status: 'done', progress: 1, note: settings.refine ? 'Warmed the highlights and lifted the blacks a touch to match the reference’s faded film look.' : null, cube: '/Users/demo/Footage/graded/x.cube', graded: '/Users/demo/Footage/graded/x_graded.mp4' })); App.on('progress', { done: k + 1, total: todo.length }); }, k * 900 + 860);
        });
        setTimeout(() => { App.on('busy', { busy: false }); App.on('finished', { ok: todo.length, total: todo.length, dir: '/Users/demo/Footage/graded' }); }, todo.length * 900 + 500);
      },
      make_reference() {}, remove() {}, clear() {}, reveal() {},
      _add: add, _ref: setRef,
    };
  }

  // Never leave the window stuck on the splash. If startup throws, or the Python side never
  // answers, show the app anyway and say what went wrong.
  if (!location.search.includes('demo')) {
    let started = false;
    const reveal = (msg) => {
      const s = $('#splash');
      if (!s || s.classList.contains('out')) return;
      s.classList.add('out'); $('#app').classList.add('in');
      if (msg) toast(msg, true);
    };
    const boot = () => {
      const a = window.pywebview && window.pywebview.api;
      if (started || !a || typeof a.info !== 'function') return;
      started = true;
      start(a).catch((e) => reveal("Lut couldn't start: " + ((e && e.message) || e)));
    };
    window.addEventListener('pywebviewready', boot);
    boot();
    setTimeout(() => reveal(started ? '' : "Lut's engine didn't answer. Quit Lut and open it again."), 15000);
  }
  if (location.search.includes('demo')) {
    const d = demoApi();
    start(d).then(() => {
      if (location.search.includes('filled')) { d._ref(); d._add(); }
      if (location.search.includes('done')) setTimeout(() => d.match(), 1200);
    });
  }
})();
