let ENGINE = localStorage.getItem('kgr_engine') || 'windows';
let PRECISE_DISPO = null;
let MOTEURS = ['windows'];
const MOTEUR_NOM = {
  windows: () => t('bulle.moteur.rapide', 'Rapide (Windows)'),
  maison: () => t('bulle.moteur.maison', 'DNAreader (embarqué)'),
  precise: () => t('bulle.moteur.precis', 'Haute précision (IA)'),
};
const MOTEUR_AIDE = {
  windows: () => t('moteur.rapide.aide', 'instantané'),
  maison: () => t('moteur.maison.aide', 'notre modèle, livré avec l\'app'),
  precise: () => t('moteur.precis.aide', 'plus juste, plus lent'),
};

function applyEngine() {
  if (!MOTEURS.includes(ENGINE)) ENGINE = 'windows';
  localStorage.setItem('kgr_engine', ENGINE);
  profileTouch();
  const on = ENGINE !== 'windows';
  si('enginebtn', e => e.classList.toggle('on', on));
  si('enginelbl', e => e.textContent = on ? 'Haute précision : active' : 'Haute précision');
  si('bengine', e => {
    e.classList.toggle('on', on);
    e.textContent = (MOTEUR_NOM[ENGINE] || MOTEUR_NOM.windows)();
  });
  si('benginehint', e => e.textContent =
      MOTEURS.length < 2
        ? t('moteur.absent.aide', 'seul moteur livré, voir Plus d\'options')
        : (MOTEUR_AIDE[ENGINE] || MOTEUR_AIDE.windows)());
}
fetch('/api/engines').then(r => r.json()).then(d => {
  PRECISE_DISPO = !!d.precise;
  MOTEURS = ['windows'];
  if (d.maison) MOTEURS.push('maison');
  if (d.precise) MOTEURS.push('precise');
  if (MOTEURS.length < 2) {
    for (const id of ['enginebtn', 'bengine']) si(id, e => {
      e.disabled = true;
      e.style.opacity = .45;
      e.title = t('moteur.absent.titre',
                  'La haute précision demande manga-ocr (2 Go), qui n\'est pas '
                  + 'livré avec l\'application. Détails dans Plus d\'options.');
    });
    ENGINE = 'windows';
  }
  applyEngine();
}).catch(() => applyEngine());

let ENHANCE = localStorage.getItem('kgr_enhance') || 'auto';
function applyEnhance() {
  localStorage.setItem('kgr_enhance', ENHANCE);
  profileTouch();
  si('boost', e => {
    e.classList.toggle('on', ENHANCE === 'boost');
    e.title = ENHANCE === 'boost'
      ? 'Renforcement MAX actif. Reclique pour revenir au mode normal'
      : 'Texte rebelle : renforce encore le contraste et la netteté';
  });
}
applyEnhance();

let FS = +(localStorage.getItem('kgr_fs') || 26);
function applyFS() {
  FS = Math.max(11, Math.min(60, FS));
  document.documentElement.style.setProperty('--fs', FS + 'px');
  localStorage.setItem('kgr_fs', FS);
  si('fslabel', e => e.textContent = FS + ' px');
  profileTouch();
}
$('text').addEventListener('wheel', ev => {
  if (!ev.ctrlKey) return;
  ev.preventDefault();
  FS += (ev.deltaY < 0 ? 2 : -2);
  applyFS();
}, {passive:false});
applyFS();

async function refreshVocabCount() {
  try { const r = await fetch('/api/vocab').then(r => r.json());
    si('vocabcount', e => e.textContent = r.count || 0); } catch {}
}
function fmtAge(t) {
  const s = Math.max(0, Date.now()/1000 - t);
  if (s < 3600) return Math.round(s/60) + ' min';
  if (s < 86400) return Math.round(s/3600) + ' h';
  return Math.round(s/86400) + ' j';
}
async function showVocab() {
  const p = $('vocabpanel');
  const r = await fetch('/api/vocab').then(r => r.json());
  const rows = (r.words || []).map(w => `
    <div class="vrow">
      <span class="vw">${esc(w.expr)}</span>
      <span class="vr">${esc(w.reading || '')}</span>
      <span class="vg">${esc(w.gloss || '')}
        ${w.sentence ? `<div class="vs">${esc(w.sentence)}</div>` : ''}</span>
      <span class="vs">${fmtAge(w.added)}</span>
      <button class="vdel" data-e="${esc(w.expr)}" data-r="${esc(w.reading||'')}"
              title="Retirer">✕</button>
    </div>`).join('');
  p.innerHTML = `<div id="vocabhead">
      <b>${r.count} mot(s) enregistré(s)</b>
      <a href="/api/vocab/export.apkg" download class="expbtn"
         title="Paquet Anki : double-clic et c'est importé, mise en forme et phrase de contexte comprises">
        Exporter pour Anki (.apkg)</a>
      <a href="/api/vocab/export" download class="explink"
         title="Colonnes séparées par des tabulations, à mapper soi-même dans Anki">
        .tsv</a>
      <span class="spacer"></span>
      <button id="vocabclose">Fermer</button></div>` +
    (rows || '<div style="color:var(--dim);padding:20px 0">Aucun mot pour l\'instant. Survole un mot et clique ＋</div>');
  p.classList.add('show'); $('text').style.display = 'none';
  $('vocabclose').addEventListener('click', hideVocab);
  p.querySelectorAll('.vdel').forEach(b => b.addEventListener('click', async () => {
    await api('/api/vocab/remove', {expr: b.dataset.e, reading: b.dataset.r});
    showVocab(); refreshVocabCount();
  }));
}
function hideVocab() {
  $('vocabpanel').classList.remove('show');
  $('text').style.display = '';
}
refreshVocabCount();

async function applyMode(quiet) {
  si('modesel', e => e.value = MODE);
  localStorage.setItem('kgr_mode', MODE);
  profileTouch();
  renderText();
  if (MODE === 'lecture' || quiet) return;
  const st = await fetch('/api/translate').then(r => r.json()).catch(() => null);
  if (st && !st.installed) { setStatus('Traduction indisponible : transformers absent'); return; }
  if (st && !st.loaded) {
    setStatus('Chargement du traducteur (téléchargement ~2,5 Go la 1re fois)…');
    setDot('ocr');
    const r = await api('/api/translate/warmup', {});
    setDot('idle');
    if (r && r.error) { setStatus('Traduction : ' + r.error); return; }
    setStatus('Traducteur prêt : français hors ligne');
  }
}

function appliqueReglage(cle, v) {
  switch (cle) {
    case 'opacity':    OPACITY = v; applyOpacity(true); break;
    case 'opacitylec': OPACITY_LECTURE = v; applyOpacity(true); break;
    case 'fontsize':   FS = v; applyFS(); break;
    case 'engine':     ENGINE = v; applyEngine(); break;
    case 'enhance':    ENHANCE = v; applyEnhance(); break;
    case 'stream':     STREAM = v; applyStream(); break;
    case 'gamehl':     GAMEHL = v; applyGameHl(); break;
    case 'autofreeze': AUTOFREEZE = v; applyAutoFreeze(); break;
    case 'mode':       MODE = v; applyMode(); break;
    case 'bulle':      applyBulle(); break;
    case 'tuto':       tutoDemarre(); break;
    case 'langue':     changeLangue(v); break;
    case 'jeu':        setGame(v); break;
    case 'lire':       doOCR(); break;
    case 'zone':       startZonePick(); break;
    case 'muet':       window.toggleMuet(!!v); return;
    case 'couleur':    setCouleur(v); return;
    case 'modefenetre': {
      const pv = window.pywebview && window.pywebview.api;
      if (pv && pv.set_mode) pv.set_mode('window', gameTitle || null);
      break;
    }
    default: return;
  }
  annonceEtat();
}

let etatTimer = null;
function annonceEtat() {
  clearTimeout(etatTimer);
  etatTimer = setTimeout(() => {
    fetch('/api/reglage/etat', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        opacity: OPACITY, opacitylec: OPACITY_LECTURE,
        fontsize: FS, engine: ENGINE, enhance: ENHANCE,
        stream: STREAM, gamehl: GAMEHL, autofreeze: AUTOFREEZE,
        mode: MODE, bulle: BULLE, jeu: gameTitle || null,
        muet: (typeof MUET !== 'undefined') && MUET, couleur: COULEUR,
        langue: (typeof LANGUE === 'string' ? LANGUE : 'fr'),
        zone: (typeof ZONE !== 'undefined' && ZONE) ? true : false
      })
    }).catch(() => {});
  }, 250);
}

let perfTimer = null;
async function majPerf() {
  try {
    const p = await fetch('/api/perf').then(r => r.json());
    const f = p.flux || {}, l = p.lecture || {};
    const fps = f.actif ? (f.images_par_seconde != null ? f.images_par_seconde + ' img/s' : '…') : 'flux inactif';
    const det = l.total_ms != null
      ? `${l.total_ms} ms (ocr ${l.ocr_ms} · detecteur ${l.detecteur_ms}`
        + (l.ppocr_ms ? ` · pp-ocr ${l.ppocr_ms}` : '')
        + (l.relecture_ms ? ` · IA ${l.relecture_ms}` : '') + ')'
      : 'aucune lecture';
    const m = (p.moteurs || {}).lignes_memorisees;
    si('perflbl', e => e.textContent = `${fps} · ${det}`
      + (m ? ` · ${m} ligne(s) memorisee(s)` : ''));
  } catch (e) { si('perflbl', e => e.textContent = 'indisponible'); }
}

const DOCK_OPACITY_MAX = 82;
let OPACITY = +(localStorage.getItem('kgr_opacity') || 45);
let OPACITY_LECTURE = +(localStorage.getItem('kgr_opacity_lecture') || 100);
function applyOpacity(save) {
  OPACITY = Math.max(10, Math.min(100, OPACITY));
  OPACITY_LECTURE = Math.max(40, Math.min(100, OPACITY_LECTURE));
  si('opacity', e => e.value = OPACITY);
  si('opacitylbl', e => e.textContent = OPACITY + ' %');
  si('opacitylec', e => e.value = OPACITY_LECTURE);
  si('opacityleclbl', e => e.textContent = OPACITY_LECTURE + ' %');
  if (save) {
    localStorage.setItem('kgr_opacity', OPACITY);
    localStorage.setItem('kgr_opacity_lecture', OPACITY_LECTURE);
    profileTouch();
  }
  const pv = window.pywebview && window.pywebview.api;
  const enVeille = document.body.classList.contains('veille')
                && !document.body.classList.contains('survolee')
                && !document.body.classList.contains('en-visite');
  const effective = (typeof BULLE !== 'undefined' && BULLE)
    ? (enVeille ? OPACITY : OPACITY_LECTURE)
    : (docked ? Math.min(OPACITY, DOCK_OPACITY_MAX) : OPACITY);
  if (pv && typeof pv.set_opacity === 'function' && effective !== _opaciteAppliquee) {
    _opaciteAppliquee = effective;
    pv.set_opacity(effective);
  }
}
let _opaciteAppliquee = -1;

const COULEURS = {
  cyan:    {nom: 'Cyan',    base: '#5ecfd4', clair: '#91e1e2'},
  vert:    {nom: 'Vert',    base: '#6bd48a', clair: '#9ce6b1'},
  ambre:   {nom: 'Ambre',   base: '#e0a95e', clair: '#f0c78f'},
  rose:    {nom: 'Rose',    base: '#e07a9e', clair: '#f0a7c0'},
  violet:  {nom: 'Violet',  base: '#a98ae0', clair: '#c7b3ee'},
  blanc:   {nom: 'Neutre',  base: '#c3d0d4', clair: '#e6eef0'},
};
let COULEUR = localStorage.getItem('kgr_couleur') || 'cyan';

function _rgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function applyCouleur(save) {
  const c = COULEURS[COULEUR] || COULEURS.cyan;
  const [r, v, b] = _rgb(c.base);
  const st = document.documentElement.style;
  st.setProperty('--accent', c.base);
  st.setProperty('--accent-hi', c.clair);
  st.setProperty('--accent-dim', `rgba(${r},${v},${b},.16)`);
  st.setProperty('--hl', `rgba(${r},${v},${b},.28)`);
  st.setProperty('--line', `rgba(${r},${v},${b},.16)`);
  st.setProperty('--line-soft', `rgba(${r},${v},${b},.08)`);
  document.querySelectorAll('.pastille-couleur').forEach(e =>
    e.classList.toggle('on', e.dataset.couleur === COULEUR));
  if (save) { localStorage.setItem('kgr_couleur', COULEUR); }
}
function setCouleur(nom) {
  if (!COULEURS[nom]) return;
  COULEUR = nom;
  applyCouleur(true);
  setStatus(t('etat.couleur', 'Couleur : {0}').replace('{0}', COULEURS[nom].nom));
  annonceEtat();
}
window.applyCouleur = applyCouleur;

function peinsCouleurs() {
  const hote = $('bcouleurs');
  if (!hote || hote.childElementCount) return;
  for (const [cle, c] of Object.entries(COULEURS)) {
    const b = document.createElement('button');
    b.className = 'pastille-couleur';
    b.dataset.couleur = cle;
    b.style.background = c.base;
    b.title = c.nom;
    b.addEventListener('click', () => setCouleur(cle));
    hote.appendChild(b);
  }
  applyCouleur(false);
}

si('bmuet', e => e.addEventListener('click', () => window.toggleMuet()));

si('bzonetout', e => e.addEventListener('click', () => zoneTout()));

si('bengine', e => e.addEventListener('click', () => {
  if (e.disabled) return;
  const i = MOTEURS.indexOf(ENGINE);
  ENGINE = MOTEURS[(i + 1) % MOTEURS.length];
  applyEngine();
  lastSig = null;
  if (typeof resetLive === 'function') resetLive();
  annonceEtat();
}));

si('btuto', e => e.addEventListener('click', () => {
  if (typeof toggleBset === 'function') toggleBset(false);
  if (typeof tutoDemarre === 'function') tutoDemarre();
}));
['mouseenter', 'mouseleave'].forEach(ev =>
  $('bar').addEventListener(ev, () => {
    document.body.classList.toggle('survolee', ev === 'mouseenter');
    applyOpacity(false);
  }));

let GHOST = false;
function applyGhost(quiet) {
  si('ghostbtn', e => e.classList.toggle('on', GHOST));
  si('ghostlbl', e => e.textContent = GHOST ? 'Traversant : actif' : 'Traversant');
  document.body.classList.toggle('ghost', GHOST);
  const kb = $('ghostkey');
  if (kb) kb.textContent = ((typeof HOTKEYS === 'object' && HOTKEYS.ghost) || '0').toUpperCase();
  const pv = window.pywebview && window.pywebview.api;
  if (pv && typeof pv.set_click_through === 'function') pv.set_click_through(GHOST);
  if (quiet) return;
  profileTouch();
  setStatus(GHOST ? `Clics envoyés au jeu. ${(HOTKEYS.ghost || '0').toUpperCase()} pour reprendre la main.`
                  : 'La barre reçoit de nouveau les clics.');
}
window.setGhost = on => { GHOST = !!on; applyGhost(); };

window.addEventListener('pywebviewready', () => {
  applyOpacity(false);
  applyGhost(true);
  if (typeof applyBulle === 'function') applyBulle();
  if (typeof planifieAjustement === 'function') planifieAjustement();
});

let STREAM = localStorage.getItem('kgr_stream') !== '0';
async function applyStream() {
  const on = STREAM && !!gameTitle;
  const r = await api('/api/stream', {on, window: gameTitle || null});
  STREAM = !!(r && r.on) || (STREAM && !gameTitle);
  localStorage.setItem('kgr_stream', STREAM ? '1' : '0');
  const live = !!(r && r.on);
  si('streambtn', e => e.classList.toggle('on', live));
  si('streamlbl', e => e.textContent = live ? 'Flux continu : actif' : 'Flux continu');
  $('statuspill').classList.toggle('live', live);
  if (r && r.error) setStatus('Flux : ' + r.error);
  else if (gameTitle) setStatus(live ? 'Détection instantanée activée'
                                     : 'Détection par sondage');
}
