function wordClass(line, idx) {
  const ws = line.words||[];
  for (let k=0;k<ws.length;k++) if (idx>=ws[k].s && idx<ws[k].e) return (k%2===0)?'wa':'wb';
  return '';
}
let LAST_RENDER = null;
function renderSignature() {
  const ancre = (typeof BULLE_ID !== 'undefined' && BULLE_ID != null)
    ? 'p' + BULLE_ID : 'n' + BULLE_IDX;
  return MODE + '|' + FS + '|' + (typeof BULLE !== 'undefined' && BULLE ? 'b' + ancre : '')
    + '|' + LINES.filter(l => l.jp)
    .map(l => l.text + '@' + Math.round(l.box[1] / 8)
             + (FR.get(l.text) || '')).join('');
}
let RENDU_ATTENDU = false;
let RENDU_DEPUIS = 0;
const RENDU_ATTENTE_MAX = 6000;

function ficheOuverte() {
  const p = $('popup');
  return !!p && getComputedStyle(p).display !== 'none';
}

function renderIfChanged() {
  const sig = renderSignature();
  if (sig === LAST_RENDER) return false;
  if (ficheOuverte()) {
    const t = Date.now();
    if (!RENDU_ATTENDU) { RENDU_ATTENDU = true; RENDU_DEPUIS = t; }
    if (t - RENDU_DEPUIS < RENDU_ATTENTE_MAX) return false;
    hidePopup();
  }
  RENDU_ATTENDU = false;
  LAST_RENDER = sig;
  renderText();
  return true;
}

function rattraperRendu() {
  if (!RENDU_ATTENDU) return;
  RENDU_ATTENDU = false;
  if (renderIfChanged() && typeof fitBulle === 'function') fitBulle();
}

function renderText() {
  LAST_RENDER = renderSignature();
  const box = $('text'); box.innerHTML = '';
  const jp = LINES.filter(l => l.jp);
  if (!jp.length) { box.innerHTML = '<div id="empty"><svg class="i" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>Aucun texte japonais détecté</div>'; return; }
  if (typeof BULLE !== 'undefined' && BULLE && typeof ancreBulle === 'function') {
    BULLE_IDX = ancreBulle(jp);
  }
  const aRendre = (typeof BULLE !== 'undefined' && BULLE)
    ? jp.slice(Math.min(BULLE_IDX, jp.length - 1), Math.min(BULLE_IDX, jp.length - 1) + 1)
    : jp;
  aRendre.forEach((line) => {
    const li = LINES.indexOf(line);
    const div = document.createElement('div'); div.className = 'tline';
    if (line.corrected) div.classList.add('corrected');
    const chars = [...line.text].map((ch, ci) => {
      const s = document.createElement('span'); s.textContent = ch;
      const wc = wordClass(line, ci); if (wc) s.classList.add(wc);
      s.dataset.line = li; s.dataset.idx = ci;
      s.addEventListener('mouseenter', onHover);
      return s;
    });

    const mots = (line.words || []).slice().sort((a, b) => a.s - b.s);
    let i = 0;
    for (const w of mots) {
      while (i < w.s && i < chars.length) div.appendChild(chars[i++]);
      const base = chars.slice(w.s, w.e);
      if (MODE === 'apprentissage' && w.ruby && base.length) {
        const ruby = document.createElement('ruby');
        base.forEach(s => ruby.appendChild(s));
        const rt = document.createElement('rt'); rt.textContent = w.ruby;
        ruby.appendChild(rt);
        div.appendChild(ruby);
      } else base.forEach(s => div.appendChild(s));
      i = Math.max(i, w.e);
    }
    while (i < chars.length) div.appendChild(chars[i++]);

    const fix = document.createElement('button');
    fix.className = 'fixbtn'; fix.textContent = '✎';
    fix.title = 'Corriger cette ligne. L\'app s\'en souviendra';
    fix.addEventListener('click', ev => { ev.stopPropagation(); startFix(div, line); });
    div.appendChild(fix);
    box.appendChild(div);

    if (MODE !== 'lecture') {
      const fr = document.createElement('div');
      fr.className = 'tfr';
      const t = FR.get(line.text);
      if (t) fr.textContent = t;
      else { fr.classList.add('attente'); fr.textContent = 'traduction…'; }
      box.appendChild(fr);
    }
  });
  box.dataset.rendu = aRendre.length ? clePiste(aRendre[0]) : '';
  if (MODE !== 'lecture') requestTranslations(jp);
}

function clePiste(l) {
  return l ? (l.id != null ? 'p' + l.id : 't' + l.text) : '';
}

let frPending = false;
async function requestTranslations(lignes) {
  if (frPending) return;
  const besoin = [...new Set(lignes.map(l => l.text).filter(t => !FR.has(t)))];
  if (!besoin.length) return;
  frPending = true;
  try {
    const r = await api('/api/translate', {texts: besoin});
    if (r && r.texts) besoin.forEach((t, i) => FR.set(t, r.texts[i] || ''));
    else {
      besoin.forEach(t => FR.set(t, ''));
      setStatus('Traduction : ' + ((r && r.error) || 'indisponible'));
    }
    renderText();
  } catch (e) {
    besoin.forEach(t => FR.set(t, ''));
  } finally { frPending = false; }
}

async function startFix(div, line) {
  const avant = line.text;
  hidePopup();
  const inp = document.createElement('input');
  inp.className = 'fixinput'; inp.value = avant;
  inp.title = 'Entrée pour retenir · Échap pour annuler';
  div.innerHTML = ''; div.appendChild(inp);
  inp.focus(); inp.select();
  let fini = false;
  const terminer = async garder => {
    if (fini) return; fini = true;
    const apres = inp.value.trim();
    if (garder && apres && apres !== avant) {
      const r = await api('/api/corrections',
                          {wrong: avant, right: apres, source: gameTitle || ''});
      if (r && r.ok) {
        line.text = apres;
        line.corrected = true;
        try {
          const seg = await api('/api/text', {text: apres});
          const l0 = seg && seg.lines && seg.lines[0];
          if (l0) {
            line.words = l0.words;
            const [bx, by, bw, bh] = line.box, n = Math.max(apres.length, 1);
            line.chars = Array.from({length: n}, (_, i) => [bx + i * bw / n, by, bw / n, bh]);
          }
        } catch (e) {}
        setStatus(`Correction retenue · ${r.count} au total`);
      } else setStatus('Correction refusée : ' + ((r && r.error) || '?'));
    }
    renderText();
  };
  inp.addEventListener('keydown', ev => {
    if (ev.key === 'Enter')  { ev.preventDefault(); terminer(true); }
    if (ev.key === 'Escape') { ev.preventDefault(); terminer(false); }
  });
  inp.addEventListener('blur', () => terminer(true));
}

let lookupTimer=null, lookupSeq=0;
let lastHover = {li:-1, ci:-1};

const LOOKUP_CACHE = new Map();
const LOOKUP_CACHE_MAX = 400;
function cacheCle(texte, ci) {
  return (typeof LANGUE === 'string' ? LANGUE : 'fr') + '|' + ci + '@' + texte;
}
function cacheMet(cle, r) {
  if (LOOKUP_CACHE.size >= LOOKUP_CACHE_MAX) {
    LOOKUP_CACHE.delete(LOOKUP_CACHE.keys().next().value);
  }
  LOOKUP_CACHE.set(cle, r);
}

function onHover(ev) {
  const li=+ev.target.dataset.line, ci=+ev.target.dataset.idx;
  clearTimeout(lookupTimer);
  const line = LINES[li];
  if (line) {
    const r = LOOKUP_CACHE.get(cacheCle(line.text, ci));
    if (r) {
      lastHover = {li, ci};
      lookupSeq++;
      highlight(li, ci, r.matchLen);
      showPopup(r, ev.clientX, ev.clientY);
      return;
    }
  }
  lookupTimer = setTimeout(() => doLookup(li, ci, ev.clientX, ev.clientY), 70);
}
async function doLookup(li, ci, mx, my) {
  const line = LINES[li]; if (!line) return;
  lastHover = {li, ci};
  const seq = ++lookupSeq;
  const cle = cacheCle(line.text, ci);
  let r = LOOKUP_CACHE.get(cle);
  if (!r) {
    r = await api('/api/lookup', {text: line.text, offset: ci,
                                  langue: (typeof LANGUE === 'string' ? LANGUE : 'fr')});
    if (seq !== lookupSeq) return;
    if (r && !r.error) cacheMet(cle, r);
  }
  highlight(li, ci, r.matchLen);
  showPopup(r, mx, my);
}
function highlight(li, ci, len) {
  document.querySelectorAll('.hl').forEach(e =>
    e.classList.remove('hl', 'hl-debut', 'hl-fin'));
  if (!len) { gameHighlight(null); return; }
  document.querySelectorAll(`[data-line="${li}"]`).forEach(e => {
    const i = +e.dataset.idx;
    if (i < ci || i >= ci + len) return;
    e.classList.add('hl');
    if (i === ci) e.classList.add('hl-debut');
    if (i === ci + len - 1) e.classList.add('hl-fin');
  });
  gameHighlight(li, ci, len);
}

let GAMEHL = localStorage.getItem('kgr_gamehl') !== '0';
function gameHighlight(li, ci, len) {
  const pv = window.pywebview && window.pywebview.api;
  if (!pv) return;
  if (!GAMEHL || li === null || histPos !== -1) { pv.clear_highlight(); return; }
  const line = LINES[li];
  if (!line || !line.chars || !line.chars.length) { pv.clear_highlight(); return; }
  const boxes = [];
  for (let i = ci; i < ci + len && i < line.chars.length; i++) {
    const b = line.chars[i];
    if (b) boxes.push([b[0], b[1], b[2], b[3], 'word']);
  }
  pv.highlight(boxes, gameTitle, currentRegion());
}
function showPopup(r, mx, my) {
  const p = $('popup');
  if (!r.matches || !r.matches.length) { hidePopup(); return; }
  p.innerHTML = r.matches.slice(0,12).map(m => {
    const head = m.reading && m.reading !== m.expression
      ? `<ruby>${esc(m.expression)}<rt>${esc(m.reading)}</rt></ruby>`
      : `<ruby>${esc(m.expression)}</ruby>`;
    const tags = m.tags.map(t=>`<span class="tag ${posTag(t)?'pos':''}" title="${esc(tagNote(t))}">${esc(t)}</span>`).join('');
    const defs = m.defs.map(d => {
      const badge = `<span class="langbadge ${d.lang}">${d.lang.toUpperCase()}</span>`;
      const lis = d.glosses.slice(0,8).map(g=>`<li>${esc(g)}</li>`).join('');
      return `<div>${badge}</div><ol class="gl">${lis}</ol>`;
    }).join('');
    const gloss = (m.defs[0] && m.defs[0].glosses.slice(0,3).join(', ')) || '';
    const save = `<button class="savew" title="Enregistrer dans mon vocabulaire"
        data-e="${esc(m.expression)}" data-r="${esc(m.reading||'')}"
        data-g="${esc(gloss)}">＋</button>`;
    return `<div class="entry"><div class="head">${head}${save}</div>` +
           `<div class="tagrow">${tags}</div>${defs}</div>`;
  }).join('');
  p.querySelectorAll('.savew').forEach(b => b.addEventListener('click', async ev => {
    ev.stopPropagation();
    const line = LINES[lastHover.li];
    const r = await api('/api/vocab', {
      expr: b.dataset.e, reading: b.dataset.r, gloss: b.dataset.g,
      sentence: line ? line.text : '', source: gameTitle || ''
    });
    if (r && r.ok) { b.textContent = '✓'; b.classList.add('saved');
      setStatus(`« ${b.dataset.e} » enregistré · ${r.count} mot(s)`); }
  }));
  p.style.display = 'block';
  const pw = Math.ceil(p.getBoundingClientRect().width) || 410;
  const ph = Math.min(p.scrollHeight, Math.max(260, window.innerHeight * 0.52));
  const ligne = document.elementFromPoint(mx, my);
  const lr = (ligne && ligne.closest('.tline') || {getBoundingClientRect: () => ({top: my, bottom: my})})
               .getBoundingClientRect();
  if (typeof BULLE !== 'undefined' && BULLE) {
    if (window.bulleFiche) window.bulleFiche();
    return;
  }
  const placeAuDessus = lr.top - 6 >= ph + 8;
  let x = mx - 20;
  let y = placeAuDessus ? lr.top - ph - 6 : lr.bottom + 6;
  if (x + pw > window.innerWidth - 8) x = window.innerWidth - pw - 8;
  if (y + ph > window.innerHeight - 8) y = Math.max(8, window.innerHeight - ph - 8);
  p.style.left = Math.max(8,x)+'px'; p.style.top = Math.max(8,y)+'px';
  if (window.bulleFiche) window.bulleFiche();
}
let hideTimer=null;
function scheduleHide(){
  clearTimeout(hideTimer);
  hideTimer = setTimeout(hidePopup, 420);
}
function hidePopup(){ clearTimeout(hideTimer);
  $('popup').style.display='none';
  document.querySelectorAll('.hl').forEach(e=>e.classList.remove('hl'));
  gameHighlight(null);
  if (window.bulleFiche) window.bulleFiche();
  rattraperRendu();
}
$('popup').addEventListener('mouseenter', ()=>clearTimeout(hideTimer));
$('popup').addEventListener('mouseleave', scheduleHide);
$('text').addEventListener('mouseleave', scheduleHide);
document.addEventListener('mousemove', ev => {
  const p = $('popup'); if (p.style.display==='none') return;
  const t = ev.target;
  if (t.closest && (t.closest('#popup') || (t.dataset && t.dataset.line!==undefined))) { clearTimeout(hideTimer); return; }
  scheduleHide();
});
document.addEventListener('keydown', ev => { if (ev.key === 'Escape') hidePopup(); });

document.addEventListener('mousedown', ev => {
  if (ev.target.closest && ev.target.closest('#popup')) return;
  hidePopup();
}, true);
document.addEventListener('mouseleave', scheduleHide);
