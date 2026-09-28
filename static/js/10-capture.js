async function refreshWindows() {
  if (typeof relisJeuxBulle === 'function') relisJeuxBulle();
}
const JEU_RETENU = 'dnareader_jeu';

function setGame(titre) {
  gameTitle = titre || '';
  try {
    if (gameTitle) localStorage.setItem(JEU_RETENU, gameTitle);
    else localStorage.removeItem(JEU_RETENU);
  } catch (e) {}
  lastSig = null;
  resetLive();
  loadZone();
  setStatus(gameTitle ? 'Jeu : ' + gameTitle : 'Choisis le jeu…');
  if (typeof majEtiquetteJeu === 'function') majEtiquetteJeu();
  if (gameTitle && typeof loadProfile === 'function') loadProfile();
  if (typeof annonceEtat === 'function') annonceEtat();
  tireLesCorrectionsPartagees();
  if (typeof fitBulle === 'function') fitBulle(true);
}

async function reprendLeJeuRetenu() {
  let voulu = '';
  try { voulu = localStorage.getItem(JEU_RETENU) || ''; } catch (e) { return; }
  if (!voulu || gameTitle) return;
  let ouvertes = [];
  try {
    ouvertes = await fetch('/api/windows').then(r => r.json())
                     .then(d => d.windows || d || []);
  } catch (e) { return; }
  const noms = ouvertes.map(w => (typeof w === 'string' ? w : w.title || ''));
  if (noms.includes(voulu)) setGame(voulu);
}

let ACCES = {ok: true, mode: 'libre'};
async function relisAcces() {
  try {
    ACCES = await fetch('/api/acces').then(r => r.json());
  } catch (e) { return; }
  document.body.classList.toggle('expire', ACCES.mode === 'expire'
                                        || (!ACCES.ok && ACCES.mode !== 'libre'));
  const cache = document.getElementById('accesbandeau');
  if (ACCES.mode === 'libre' || ACCES.mode === 'cle') {
    if (cache) cache.hidden = true;
    return;
  }
  const j = Math.ceil(ACCES.jours_restants || 0);
  const bandeau = document.getElementById('accesbandeau');
  const texte = document.getElementById('accestexte');
  if (!bandeau || !texte) return;

  bandeau.hidden = false;
  bandeau.classList.toggle('presse', ACCES.ok && j <= 3);
  bandeau.classList.toggle('fini', !ACCES.ok);
  texte.textContent = ACCES.ok
    ? (j <= 3
        ? t('acces.essai.bientot', 'Essai gratuit : plus que {0} jour(s)').replace('{0}', j)
        : t('acces.essai.reste', 'Version d\'essai : {0} jours restants').replace('{0}', j))
    : (ACCES.raison_cle || ACCES.raison
       || t('acces.essai.fini', 'Essai terminé : il faut une clé pour lire'));
}
let MAJ_ATTENTE = null;
let PAIEMENT_URL = '';
const ATTENTE_MAX_MIN = 15;
let ATTENTE_DEPUIS = 0;

function surveilleLePaiement() {
  if (MAJ_ATTENTE) return;
  ATTENTE_DEPUIS = Date.now();
  MAJ_ATTENTE = setInterval(async () => {
    let r;
    try {
      r = await fetch('/api/licence/attente').then(x => x.json());
    } catch (e) { return; }
    if (r.aucune_attente || r.expire
        || Date.now() - ATTENTE_DEPUIS > ATTENTE_MAX_MIN * 60000) {
      arreteLaSurveillance();
      return;
    }
    if (!r.pret) return;
    arreteLaSurveillance();
    if (r.active) {
      relisAcces();
      setStatus(t('acces.merci', 'Abonnement actif. Merci !'));
    } else if (r.cle) {
      const e = document.getElementById('accestexte');
      if (e) e.textContent = t('acces.cle.manuelle',
        'Payé. Ta clé : {0}. Colle-la dans Réglages.').replace('{0}', r.cle);
    }
  }, 3000);
}

function arreteLaSurveillance() {
  if (MAJ_ATTENTE) { clearInterval(MAJ_ATTENTE); MAJ_ATTENTE = null; }
  rendLeBouton();
}

function rendLeBouton() {
  const ab = document.getElementById('accesabonner');
  if (!ab) return;
  ab.disabled = false;
  ab.textContent = ab.dataset.libelle || ab.textContent;
}

{
  const pv = () => window.pywebview && window.pywebview.api;

  const cle = document.getElementById('accescle');
  if (cle) cle.addEventListener('click', () => {
    const a = pv();
    if (a && typeof a.ouvrir_reglages === 'function') a.ouvrir_reglages('cle');
  });

  const ab = document.getElementById('accesabonner');
  if (ab) ab.addEventListener('click', async () => {
    if (!ab.dataset.libelle) ab.dataset.libelle = ab.textContent;

    if (MAJ_ATTENTE && PAIEMENT_URL) {
      const a0 = pv();
      if (a0 && typeof a0.ouvrir_lien === 'function') a0.ouvrir_lien(PAIEMENT_URL);
      else window.open(PAIEMENT_URL, '_blank');
      return;
    }

    ab.disabled = true;
    ab.textContent = t('acces.ouverture', 'ouverture…');
    let r;
    try {
      r = await fetch('/api/licence/abonner', {method: 'POST'}).then(x => x.json());
    } catch (e) { r = {ok: false, raison: String(e)}; }
    if (!r.ok || !r.url) {
      setStatus(r.raison || 'impossible d\'ouvrir le paiement');
      rendLeBouton();
      return;
    }
    PAIEMENT_URL = r.url;
    const a = pv();
    if (a && typeof a.ouvrir_lien === 'function') a.ouvrir_lien(r.url);
    else window.open(r.url, '_blank');
    ab.disabled = false;
    ab.textContent = t('acces.attente', 'en attente, rouvrir le paiement');
    surveilleLePaiement();
  });

  if (ab) fetch('/api/licence/boutique').then(r => r.json())
    .then(r => { ab.hidden = !r.ouverte; })
    .catch(() => {});

  surveilleLePaiement();
}

relisAcces();
setInterval(relisAcces, 3600 * 1000);

let MAJ_DEMANDEE = false;
let MAJ_SUIVI_BULLE = null;

function majCache() {
  const c = $('majask');
  if (c) c.classList.remove('show');
  document.body.classList.remove('en-visite');
  if (typeof ajusteFenetreAuContenu === 'function') {
    requestAnimationFrame(() => requestAnimationFrame(ajusteFenetreAuContenu));
  }
}

function majDit(html) {
  const e = $('majasktexte');
  if (e) e.innerHTML = html;
}

async function majLanceDepuisLaBulle() {
  $('majoui').disabled = true;
  $('majplustard').textContent = t('maj.masquer', 'Masquer');
  majDit(t('maj.encours', 'Téléchargement en cours. Tu peux continuer à jouer, '
           + "l'installation se fera à la fin."));
  await api('/api/maj/telecharger', {});
  if (MAJ_SUIVI_BULLE) clearInterval(MAJ_SUIVI_BULLE);
  MAJ_SUIVI_BULLE = setInterval(async () => {
    let m;
    try { m = await fetch('/api/maj').then(r => r.json()); } catch (e) { return; }
    if (m.phase === 'telechargement' && m.octets) {
      const p = Math.round((m.recus || 0) * 100 / m.octets);
      majDit(t('maj.pourcent', 'Téléchargement : {0} %').replace('{0}', p));
      setStatus(t('maj.pourcent', 'Téléchargement : {0} %').replace('{0}', p));
    } else if (m.phase === 'prete') {
      clearInterval(MAJ_SUIVI_BULLE); MAJ_SUIVI_BULLE = null;
      majDit(t('maj.installe', "Installation : l'application va se fermer et "
               + 'revenir toute seule.'));
      await api('/api/maj/installer', {});
    } else if (m.phase === 'echec') {
      clearInterval(MAJ_SUIVI_BULLE); MAJ_SUIVI_BULLE = null;
      majDit(t('maj.rate', 'La mise à jour a échoué : {0}')
               .replace('{0}', m.erreur || '?'));
      $('majoui').disabled = false;
    }
  }, 900);
}

async function signaleMaj() {
  if (MAJ_DEMANDEE) return;
  let m;
  try {
    m = await fetch('/api/maj').then(r => r.json());
  } catch (e) { return; }
  if (!m.possible || !m.version_distante || m.ignoree) return;
  if (!ACCES.ok && ACCES.mode !== 'libre') return;
  if (document.body.classList.contains('en-visite')) {
    setTimeout(signaleMaj, 30000);
    return;
  }
  MAJ_DEMANDEE = true;
  const poids = m.octets ? ` (${Math.round(m.octets / 1e6)} Mo)` : '';
  majDit(t('maj.question',
           'La version <b>{0}</b> est disponible{1}.<br><br>'
           + "L'application se ferme et revient toute seule, en gardant ton "
           + 'vocabulaire et tes réglages.')
           .replace('{0}', m.version_distante).replace('{1}', poids));
  $('majask').classList.add('show');
  document.body.classList.add('en-visite');
  if (typeof applyOpacity === 'function') applyOpacity(false);
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (typeof ajusteFenetreAuContenu === 'function') ajusteFenetreAuContenu();
  }));
  setStatus(t('maj.dispo', 'Version {0} disponible dans Réglages > Mise à jour')
              .replace('{0}', m.version_distante));
}

if ($('majplustard')) {
  $('majplustard').addEventListener('click', () => majCache());
}
if ($('majoui')) {
  $('majoui').addEventListener('click', () => majLanceDepuisLaBulle());
}

setTimeout(signaleMaj, 12000);

const _dejaTire = new Set();
async function tireLesCorrectionsPartagees() {
  if (!gameTitle || _dejaTire.has(gameTitle)) return;
  _dejaTire.add(gameTitle);
  try {
    const etat = await fetch('/api/partage').then(r => r.json());
    if (!etat || !etat.actif) return;
    const r = await api('/api/partage/tirer', {jeu: gameTitle});
    if (r && r.ok && r.ajoutees) {
      setStatus(t('etat.partage.tire',
                  '{0} correction(s) de la communauté pour ce jeu')
                  .replace('{0}', r.ajoutees));
      lastSig = null;
      resetLive();
    }
  } catch (e) {  }
}

let ZONE = null;
const zoneKey = () => 'kgr_zone:' + (gameTitle || '*');
function loadZone() {
  try { ZONE = JSON.parse(localStorage.getItem(zoneKey()) || 'null'); }
  catch { ZONE = null; }
  zoneLabel();
}
const ZONE_SUSPECTE = 0.03;

function zoneLabel() {
  const part = ZONE ? ZONE[2] * ZONE[3] : 1;
  const texte = ZONE
    ? `${Math.round(ZONE[2] * 100)}% × ${Math.round(ZONE[3] * 100)}%`
    : "tout l'écran";
  si('zonelbl', e => { e.textContent = texte; });
  si('bzonelbl', e => {
    e.textContent = ZONE
      ? (part < ZONE_SUSPECTE
          ? t('zone.minuscule', '{0} — soit {1} % de l\'écran, tout le reste est ignoré')
              .replace('{0}', texte).replace('{1}', (part * 100).toFixed(1))
          : texte)
      : t('zone.tout', "tout l'écran est lu");
    e.classList.toggle('alerte', !!ZONE && part < ZONE_SUSPECTE);
  });
  si('bzonetout', e => { e.style.display = ZONE ? '' : 'none'; });
}
function currentRegion() { return ZONE; }

function zoneTout() {
  ZONE = null;
  try { localStorage.removeItem(zoneKey()); } catch (e) {}
  zoneLabel();
  lastSig = null;
  if (typeof resetLive === 'function') resetLive();
  if (typeof profileTouch === 'function') profileTouch();
  setStatus(t('etat.zone.tout', "Toute la fenêtre du jeu est lue."));
  if (typeof annonceEtat === 'function') annonceEtat();
}

async function startZonePick() {
  const pv = window.pywebview && window.pywebview.api;
  if (!pv || typeof pv.pick_region !== 'function') {
    setStatus('(mode navigateur : sélection indispo)'); return;
  }
  setStatus('Trace un rectangle autour du texte…');
  const r = await pv.pick_region(gameTitle || null);
  if (r && r.region) {
    ZONE = r.region;
    localStorage.setItem(zoneKey(), JSON.stringify(ZONE));
    const part = ZONE[2] * ZONE[3];
    if (part < ZONE_SUSPECTE) {
      setStatus(t('etat.zone.minuscule',
                  'Zone de {0} % de l\'écran : TOUT le reste sera ignoré. '
                  + '« Tout l\'écran » pour l\'enlever.')
                  .replace('{0}', (part * 100).toFixed(1)));
    } else {
      setStatus(gameTitle ? `Zone retenue pour « ${gameTitle} »`
                          : 'Zone définie : seule cette partie sera lue');
    }
    LINES = [];
    if (typeof renderText === 'function') renderText();
  } else { setStatus('Sélection annulée'); }
  zoneLabel(); lastSig = null; resetLive();
  profileTouch();
}
window.startZonePick = startZonePick;
loadZone();

let lastSig = null, changedAt = 0, lastMoveAt = 0, pending = false, ocring = false;
const SETTLE_MS = 190;
const MAX_WAIT_MS = 1200;
const POLL_FAST = 200, POLL_SLOW = 900;
const POLL_STREAM = 60;
let pollMs = POLL_FAST, stableCount = 0;

let overlayVisible = true;
window.setOverlayVisible = v => {
  overlayVisible = !!v;
  if (overlayVisible) { lastSig = null; pollMs = POLL_FAST; stableCount = 0; resetLive(); }
};

let MUET = localStorage.getItem('kgr_muet') === '1';
function litEnCeMoment() { return overlayVisible && !MUET; }

window.toggleMuet = (force) => {
  MUET = (force === undefined) ? !MUET : !!force;
  localStorage.setItem('kgr_muet', MUET ? '1' : '0');
  document.body.classList.toggle('muet', MUET);
  const touche = ((typeof HOTKEYS === 'object' && HOTKEYS.muet) || 'f6').toUpperCase();
  if (MUET) {
    LINES = []; LIVE = [];
    resetLive();
    if (typeof renderText === 'function') renderText([]);
    if (typeof gameHighlight === 'function') gameHighlight(null);
    const pv = window.pywebview && window.pywebview.api;
    if (pv && typeof pv.clear_highlight === 'function') pv.clear_highlight();
    setStatus(t('etat.enpause', 'Lecture en pause. {0} pour reprendre.')
                .replace('{0}', touche));
  } else {
    lastSig = null; pollMs = POLL_FAST; stableCount = 0;
    resetLive();
    setStatus(t('etat.reprise', 'Lecture reprise.'));
  }
  if (typeof majBset === 'function') majBset();
  if (typeof fitBulle === 'function') fitBulle();
  if (typeof annonceEtat === 'function') annonceEtat();
  return MUET;
};

function paceAfterStable() {
  stableCount++;
  if (stableCount > 6) pollMs = Math.min(POLL_SLOW, pollMs + 100);
}
async function loop() {
  try {
    if (!gameTitle) {
      if (typeof fitBulle === 'function') fitBulle();
    } else if (MUET) {
      if (typeof fitBulle === 'function') fitBulle();
    } else if (overlayVisible) {
      const r = await api('/api/probe', {window: gameTitle, region: currentRegion()});
      if (r.error) { setDot('err'); setStatus('Erreur : ' + r.error); }
      else if (r.sig) {
        const now = Date.now();
        if (r.sig !== lastSig) {
          lastSig = r.sig;
          if (!pending) { pending = true; changedAt = now; }
          lastMoveAt = now;
          pollMs = POLL_FAST; stableCount = 0;
          setDot('change');
        }
        if (pending && (now - lastMoveAt >= SETTLE_MS
                        || now - changedAt >= MAX_WAIT_MS)) {
          pending = false;
          const g = await api('/api/grab', {window: gameTitle, region: currentRegion()});
          COUVERT = (g && g.couvert) || '';
          PLEIN_ECRAN = (g && g.plein_ecran) || '';
          setDot('change');
          drainOnce();
        } else if (!pending) {
          if (!ocring) setDot('idle');
          paceAfterStable();
        }
        if (r.stream) { pollMs = POLL_STREAM; stableCount = 0; }
      }
    }
  } catch (e) {}
  setTimeout(loop, pollMs);
}

function applyGameHl() {
  localStorage.setItem('kgr_gamehl', GAMEHL ? '1' : '0');
  if (!GAMEHL) gameHighlight(null);
}

let FROZEN = false;
function paintFreeze() {
  document.body.classList.toggle('frozen', FROZEN);
}
async function toggleFreeze(veut) {
  const pv = window.pywebview && window.pywebview.api;
  if (!pv || typeof pv.toggle_freeze !== 'function') {
    setStatus('(mode navigateur : gel indispo)'); return false;
  }
  if (!gameTitle) { setStatus("Choisis d'abord le jeu"); return false; }
  if (veut !== undefined && veut === FROZEN) return FROZEN;
  const r = await pv.toggle_freeze(gameTitle);
  if (!r || !r.ok) { setStatus('Gel impossible : ' + ((r && r.error) || '?')); return FROZEN; }
  FROZEN = !!r.frozen;
  paintFreeze();
  setStatus(FROZEN ? `Jeu gelé. ${(HOTKEYS.freeze || 'f11').toUpperCase()} ou « Reprendre » pour relancer`
                   : 'Jeu relancé');
  return FROZEN;
}
window.hotFreeze = () => toggleFreeze();

let AUTOFREEZE = localStorage.getItem('kgr_autofreeze') === '1';
function applyAutoFreeze() {
  localStorage.setItem('kgr_autofreeze', AUTOFREEZE ? '1' : '0');
  document.body.classList.toggle('autofreeze', AUTOFREEZE);
  profileTouch();
}

function onNewText() {
  if (!AUTOFREEZE || FROZEN) return;
  if (!LINES.some(l => l.jp)) return;
  toggleFreeze(true);
}

const HIST = [];
const HIST_MAX = 40;
let histPos = -1;

function pushHistory(lines) {
  const txt = lines.map(l => l.text).join('\n');
  if (!txt.trim()) return;
  const last = HIST[HIST.length - 1];
  if (last && last.txt === txt) return;
  HIST.push({lines, txt, t: Date.now()});
  if (HIST.length > HIST_MAX) HIST.shift();
  if (histPos > 0) histPos--;
}

function showHistory(pos) {
  histPos = pos;
  const item = HIST[pos];
  if (!item) return;
  LINES = item.lines; renderText();
  const age = Math.round((Date.now() - item.t) / 1000);
  setStatus(`Réplique ${pos + 1}/${HIST.length} · il y a ${age} s`);
  updateHistUI();
}
function backToLive() {
  histPos = -1;
  if (HIST.length) { LINES = HIST[HIST.length - 1].lines; renderText(); }
  setStatus('En direct');
  updateHistUI();
}
function updateHistUI() {
  const live = histPos === -1;
}

const PISTE_ABSENCES = 5;
const PISTE_VUES = 2;
const PISTE_ASSIDUITE = 0.5;
const SEUIL_DIRECT = 0.75;

const SCENE_FIGE_APRES = 3;

let PISTES = [];
let PISTE_SEQ = 0;
let LECTURE_N = 0;
let DERNIERE_COMPO = '';
let SCENE_IDENTIQUE = 0;
let LIVE = [];

function proximite(a, b) {
  if (a === b) return 1;
  if (!a || !b) return 0;
  const reste = [...b];
  let communs = 0;
  for (const c of a) {
    const i = reste.indexOf(c);
    if (i >= 0) { reste.splice(i, 1); communs++; }
  }
  return (2 * communs) / (a.length + b.length);
}

function recouvrement(a, b) {
  if (!a || !b) return 0;
  const ix = Math.max(0, Math.min(a[0] + a[2], b[0] + b[2]) - Math.max(a[0], b[0]));
  const iy = Math.max(0, Math.min(a[1] + a[3], b[1] + b[3]) - Math.max(a[1], b[1]));
  const inter = ix * iy;
  const union = a[2] * a[3] + b[2] * b[3] - inter;
  return union > 0 ? inter / union : 0;
}

function lineQuality(l) {
  if (!l.jp) return 0;
  const junk = (l.text.match(/[\/\\|_^~`<>{}\[\]=+*#@$%]/g) || []).length;
  return Math.max(0, 0.3 - junk * 0.15);
}

const VOTE_DECAY = 0.6;
const VOTE_MARGIN = 0.8;

function voteDansPiste(piste, ligne) {
  const m = piste.cand;
  for (const e of m.values()) e.score *= VOTE_DECAY;
  const poids = 1 + lineQuality(ligne);
  const cur = m.get(ligne.text);
  if (cur) { cur.score += poids; cur.ligne = ligne; }
  else m.set(ligne.text, {score: poids, ligne});

  let best = null;
  for (const e of m.values()) if (!best || e.score > best.score) best = e;
  const tenant = piste.sortant && m.get(piste.sortant);
  if (tenant && best !== tenant && best.score <= tenant.score + VOTE_MARGIN) best = tenant;
  piste.sortant = best.ligne.text;
  for (const [k, e] of m) if (e.score < 0.05 && k !== piste.sortant) m.delete(k);
  return best.ligne;
}

function scoreAppariement(piste, ligne) {
  const iou = recouvrement(piste.box, ligne.box);
  if (iou < 0.15) return 0;
  return iou * (0.45 + 0.55 * proximite(piste.text, ligne.text));
}

function majBoite(piste, box) {
  const [ox, oy, ow, oh] = piste.box, [nx, ny, nw, nh] = box;
  if (Math.abs(nx - ox) > 6 || Math.abs(ny - oy) > 6
      || Math.abs(nw - ow) > 12 || Math.abs(nh - oh) > 8) {
    piste.box = box;
    return true;
  }
  return false;
}

function resetLive() {
  LIVE = []; PISTES = []; LECTURE_N = 0;
  DERNIERE_COMPO = ''; SCENE_IDENTIQUE = 0;
}

function dedoublonne(lignes) {
  const out = [];
  for (const l of lignes) {
    const jumelle = out.find(o => proximite(o.text, l.text) >= 0.6 &&
      Math.abs(o.box[1] - l.box[1]) < Math.max(12, l.box[3] * 0.6) &&
      Math.abs(o.box[0] - l.box[0]) < Math.max(24, l.box[2] * 0.4));
    if (!jumelle) { out.push(l); continue; }
    if ((l.conf || 0) > (jumelle.conf || 0)) out[out.indexOf(jumelle)] = l;
  }
  return out;
}

function memeTexte(a, b) {
  const cle = ls => ls.filter(l => l.jp)
    .map(l => l.id + '' + l.text).sort().join('');
  const ka = cle(a);
  return ka.length > 0 && ka === cle(b);
}

function ordonne(lignes) {
  const hauteurs = lignes.map(l => l.box[3]).filter(h => h > 0).sort((a, b) => a - b);
  const h = hauteurs.length ? hauteurs[Math.floor(hauteurs.length / 2)] : 20;
  const pas = Math.max(10, h * 0.6);
  return lignes.slice().sort((a, b) =>
    (Math.round(a.box[1] / pas) - Math.round(b.box[1] / pas)) || (a.box[0] - b.box[0]));
}

function sceneOverlap(prev, next) {
  const avant = prev.filter(l => l.jp).map(l => l.text);
  if (!avant.length) return 0;
  const apres = next.filter(l => l.jp).map(l => l.text);
  let hit = 0;
  for (const t of avant) if (apres.some(u => proximite(t, u) >= 0.6)) hit++;
  return hit / avant.length;
}

function confirme(lignes) { return lignes; }

function mergeReadings(prev, next, immediat) {
  LECTURE_N++;
  const lignes = dedoublonne((next || []).filter(l => l && l.text && l.text.trim()));

  const publiees = PISTES.filter(p => p.publiee).map(p => ({jp: true, text: p.text}));
  const rupture = publiees.length && lignes.length
                  && sceneOverlap(publiees, lignes) < 0.2;

  const prises = new Set();
  const nouvelles = [];
  for (const ligne of lignes) {
    let best = null, bestScore = 0;
    for (const p of PISTES) {
      if (prises.has(p)) continue;
      const s = scoreAppariement(p, ligne);
      if (s > bestScore) { bestScore = s; best = p; }
    }
    if (best) {
      prises.add(best);
      best.absent = 0;
      best.vues++;
      best.suite++;
      majBoite(best, ligne.box);
      const gagnante = voteDansPiste(best, ligne);
      best.ligne = (ligne.text === gagnante.text) ? ligne : gagnante;
      best.text = gagnante.text;
      best.conf = Math.max(best.conf, typeof ligne.conf === 'number' ? ligne.conf : 1);
    } else {
      const p = {id: ++PISTE_SEQ, box: ligne.box.slice(), text: ligne.text,
                 ligne, cand: new Map(), sortant: null, vues: 1, suite: 1, absent: 0,
                 naissance: LECTURE_N,
                 conf: typeof ligne.conf === 'number' ? ligne.conf : 1,
                 publiee: false};
      voteDansPiste(p, ligne);
      PISTES.push(p);
      nouvelles.push(p);
      prises.add(p);
    }
  }

  for (const neuve of nouvelles) {
    const jumelle = PISTES.find(v => v !== neuve && v.publiee && !prises.has(v)
                                     && proximite(v.text, neuve.text) >= 0.6);
    if (!jumelle) continue;
    neuve.id = jumelle.id;
    neuve.vues = Math.max(neuve.vues, jumelle.vues);
    neuve.suite = Math.max(neuve.suite, jumelle.suite);
    neuve.naissance = Math.min(neuve.naissance, jumelle.naissance);
    neuve.publiee = true;
    PISTES = PISTES.filter(x => x !== jumelle);
  }

  const attendues = PISTES.filter(p => p.publiee).length;
  const retrouvees = [...prises].filter(p => p.publiee).length;
  const lectureCredible = rupture || attendues === 0
                          || retrouvees / attendues >= 0.6;
  if (lectureCredible) {
    for (const p of PISTES) {
      if (prises.has(p)) continue;
      p.absent += rupture ? PISTE_ABSENCES : 1;
      p.suite = 0;
    }
    PISTES = PISTES.filter(p => p.absent < PISTE_ABSENCES);
  }

  const sortie = [];
  for (const p of PISTES) {
    if (!p.publiee) {
      const age = LECTURE_N - p.naissance + 1;
      const assidue = p.suite >= PISTE_VUES && p.vues / age >= PISTE_ASSIDUITE;
      if (immediat || p.conf >= SEUIL_DIRECT || assidue) p.publiee = true;
    }
    if (!p.publiee) continue;
    if (p.gel) { sortie.push(p.gel); continue; }
    sortie.push(Object.assign({}, p.ligne, {box: p.box, id: p.id}));
  }
  const rangee = ordonne(sortie);

  let deriveGel = 0;
  for (const p of PISTES) {
    if (p.gel && prises.has(p) && proximite(p.gel.text, p.text) < 0.6) deriveGel++;
  }
  const composition = rangee.map(l => l.id).join(',');
  if (composition === DERNIERE_COMPO && composition !== '' && deriveGel < 2) {
    SCENE_IDENTIQUE++;
  } else {
    SCENE_IDENTIQUE = 0;
    for (const p of PISTES) p.gel = null;
  }
  DERNIERE_COMPO = composition;
  if (SCENE_IDENTIQUE >= SCENE_FIGE_APRES) {
    for (const l of rangee) {
      const p = PISTES.find(q => q.id === l.id);
      if (p && !p.gel) p.gel = l;
    }
  }
  return rangee;
}

async function drainOnce() {
  try {
    if (!ocring && litEnCeMoment() && gameTitle) {
      ocring = true;
      try {
        const r = await api('/api/drain', {enhance: ENHANCE, engine: ENGINE});
        if (r && !r.empty && r.lines) {
          const fusion = mergeReadings(LIVE, confirme(r.lines));
          if (memeTexte(LIVE, fusion)) { setDot('idle'); return; }
          LIVE = fusion;
          pushHistory(LIVE);
          if (histPos === -1) {
            LINES = LIVE;
            if (renderIfChanged()) {
              const nj = LINES.filter(l => l.jp).length;
              const q = r.queued ? ` · ${r.queued} en attente` : '';
              setStatus((nj ? nj + ' ligne(s) JP' : 'Aucun texte JP') + q);
              onNewText();
            }
            fitBulle();
          }
          updateHistUI();
          setDot('idle');
        }
      } finally { ocring = false; }
    }
  } catch (e) {}
}

const REPOS_MIN = 120;
async function drainLoop() {
  const t0 = Date.now();
  await drainOnce();
  const duree = Date.now() - t0;
  setTimeout(drainLoop, Math.max(REPOS_MIN, duree));
}

async function doOCR() {
  if (!gameTitle) return;
  ocring = true; setDot('ocr');
  try {
    const r = await api('/api/ocr', {window: gameTitle, region: currentRegion(),
                                     auto: false, enhance: ENHANCE, engine: ENGINE, want_image: false});
    if (r.error) { setDot('err'); setStatus('Erreur : ' + r.error); }
    else { resetLive(); LINES = LIVE = mergeReadings([], r.lines || [], true);
      renderText(); pushHistory(LINES); updateHistUI();
      const nj = LINES.filter(l=>l.jp).length;
      setStatus(nj ? nj + ' ligne(s) JP' : 'Aucun texte JP'); setDot('idle');
      if (typeof fitBulle === 'function') fitBulle(true); }
  } catch (e) { setDot('err'); }
  ocring = false;
}

let ws = null;
function connectWS() {
  try {
    ws = new WebSocket(`ws://${location.host}/ws`);
    ws.onmessage = ev => {
      let m; try { m = JSON.parse(ev.data); } catch { return; }
      if (m.type === 'capture') doOCR();
      else if (m.type === 'reglage') appliqueReglage(m.cle, m.valeur);
      else if (m.type === 'acces') relisAcces();
    };
    ws.onclose = () => setTimeout(connectWS, 1500);
    ws.onerror = () => { try { ws.close(); } catch {} };
  } catch { setTimeout(connectWS, 1500); }
}
connectWS();

async function ocrImage(dataUrl) {
  if (!dataUrl) { setStatus('Presse-papiers : aucune image'); return; }
  ocring = true; setDot('ocr'); setStatus('Lecture de l\'image collée…');
  try {
    const r = await api('/api/ocr', {image: dataUrl, enhance: ENHANCE, engine: ENGINE, want_image: false});
    if (r.error) { setDot('err'); setStatus('Erreur : ' + r.error); }
    else {
      resetLive();
      LINES = LIVE = mergeReadings([], r.lines || [], true);
      renderText(); pushHistory(LINES); updateHistUI();
      const nj = LINES.filter(l => l.jp).length;
      setStatus((nj ? nj + ' ligne(s) JP' : 'Aucun texte JP') + ' · image collée');
      setDot('idle');
      if (typeof fitBulle === 'function') fitBulle(true);
    }
  } catch (e) { setDot('err'); setStatus('Erreur : ' + e); }
  ocring = false;
}

document.addEventListener('paste', ev => {
  const items = (ev.clipboardData && ev.clipboardData.items) || [];
  const txt = ev.clipboardData && ev.clipboardData.getData('text');
  if (txt && IS_JP.test(txt)) {
    ev.preventDefault(); readText(txt); return;
  }
  for (const item of items) {
    if (item.type && item.type.startsWith('image/')) {
      const rd = new FileReader();
      rd.onload = () => ocrImage(rd.result);
      rd.readAsDataURL(item.getAsFile());
      ev.preventDefault();
      return;
    }
  }
});

async function readText(text) {
  setDot('ocr');
  try {
    const r = await api('/api/text', {text});
    resetLive();
    LINES = LIVE = mergeReadings([], r.lines || [], true);
    renderText(); pushHistory(LINES); updateHistUI();
    setStatus(`${LINES.filter(l=>l.jp).length} ligne(s) · texte copié (sans OCR)`);
    setDot('idle');
    if (typeof fitBulle === 'function') fitBulle(true);
  } catch (e) { setDot('err'); setStatus('Erreur : ' + e); }
}
