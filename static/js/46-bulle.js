let BULLE = true;
let BULLE_IDX = 0;
let BULLE_ID = null;
let BULLE_TEXTE = '';
let bulleVide = false;
let bulleSurvolee = false;
let derniereCible = null;
let ficheEnHaut = false;
let fichePour = null;
const CONFORT_FICHE = 320;

function lignesBulle() { return LINES.filter(l => l.jp); }

function ancreBulle(jp) {
  if (!jp.length) return 0;
  if (BULLE_ID != null) {
    const i = jp.findIndex(l => l.id === BULLE_ID);
    if (i >= 0) return i;
  }
  if (BULLE_TEXTE) {
    let meilleur = -1, score = 0.6;
    for (let i = 0; i < jp.length; i++) {
      const s = (typeof proximite === 'function')
        ? proximite(BULLE_TEXTE, jp[i].text)
        : (BULLE_TEXTE === jp[i].text ? 1 : 0);
      if (s >= score) { score = s; meilleur = i; }
    }
    if (meilleur >= 0) return meilleur;
  }
  return Math.max(0, Math.min(BULLE_IDX, jp.length - 1));
}

function poseAncre(ligne) {
  BULLE_ID = ligne ? (ligne.id != null ? ligne.id : null) : null;
  BULLE_TEXTE = ligne ? ligne.text : '';
}

const ANNONCE_SECONDES = 6;
let jeuAnnonce = null;
let minuteurAnnonce = null;

function annonceLaVeille() {
  const oeil = document.getElementById('veilleoeil');
  if (!oeil || !gameTitle) return;
  if (jeuAnnonce === gameTitle) return;
  jeuAnnonce = gameTitle;

  const court = gameTitle.length > 28 ? gameTitle.slice(0, 27) + '…' : gameTitle;
  oeil.textContent = t('bulle.jecoute', 'DNAreader écoute {0}').replace('{0}', court);
  document.body.classList.add('annonce');
  if (typeof applyOpacity === 'function') applyOpacity(true);

  clearTimeout(minuteurAnnonce);
  minuteurAnnonce = setTimeout(() => {
    oeil.textContent = '···';
    document.body.classList.remove('annonce');
    if (document.body.classList.contains('veille')
        && typeof applyOpacity === 'function') applyOpacity(false);
    if (typeof ajusteFenetreAuContenu === 'function') ajusteFenetreAuContenu();
  }, ANNONCE_SECONDES * 1000);
}

let enAttente = false;
async function montreBulleEnAttente() {
  const dejaEnAttente = enAttente;
  enAttente = true;
  const pv = window.pywebview && window.pywebview.api;
  annonceLaVeille.attendu = true;
  if (bulleVide && pv && typeof pv.bubble_visible === 'function') {
    await pv.bubble_visible(true);
  }
  bulleVide = false;
  if (!dejaEnAttente) derniereCible = null;
  document.body.classList.add('attente');
  document.body.classList.toggle('veille', !!gameTitle);
  if (typeof applyOpacity === 'function') applyOpacity(false);
  annonceLaVeille();
  if (dejaEnAttente) { planifieAjustement(); rangeLaPastille(pv); return; }
  if (!gameTitle) {
    relisJeuxBulle();
    setStatus(t('etat.choisirjeu', 'Choisis le jeu à lire.'));
  } else if (PLEIN_ECRAN) {
    setStatus(t('etat.pleinecran',
                'Jeu en plein écran : passe en « fenêtré sans bordure »'));
  } else if (COUVERT) {
    setStatus(t('etat.couvert', 'Le jeu est derrière « {0} »')
                .replace('{0}', COUVERT));
  } else {
    setStatus(t('etat.enveille', 'En attente de texte…'));
  }
  requestAnimationFrame(() => requestAnimationFrame(async () => {
    await ajusteFenetreAuContenu();
    rangeLaPastille(pv);
  }));
}

async function rangeLaPastille(pv) {
  if (!enAttente || !gameTitle) return;
  if (!pv || typeof pv.garer_bulle !== 'function') return;
  if (document.body.classList.contains('en-visite')) return;
  const k = window.devicePixelRatio || 1;
  const [larg, haut] = mesureContenu();
  const r = reposChoisi();
  try {
    const g = await pv.garer_bulle(Math.ceil(larg * k), Math.ceil(haut * k),
                                   gameTitle, r ? r[0] : null, r ? r[1] : null,
                                   currentRegion());
    if (g && g.ok) _tailleDemandee = g.w + 'x' + g.h;
  } catch (e) {}
}

const reposKey = () => 'kgr_repos2:' + (gameTitle || '*');
function reposChoisi() {
  try {
    const v = JSON.parse(localStorage.getItem(reposKey()) || 'null');
    return (Array.isArray(v) && v.length === 2) ? v : null;
  } catch (e) { return null; }
}
async function memoriseRepos() {
  const pv = window.pywebview && window.pywebview.api;
  if (!pv || typeof pv.get_geometry !== 'function') return;
  try {
    const g = await pv.get_geometry();
    if (!g || typeof g.x !== 'number') return;
    localStorage.setItem(reposKey(), JSON.stringify([g.x, g.y]));
    setStatus(t('etat.repos', 'La bulle attendra ici.'));
  } catch (e) {}
}

let _tailleDemandee = '';
function oublieTailleDemandee() { _tailleDemandee = ''; }

const HORS_FLUX = [{id: 'tutoask', marge: 0}, {id: 'tuto', marge: 0},
                   {id: 'majask', marge: 0}, {id: 'popup', marge: 0}];

function estVisible(e) {
  if (!e) return false;
  const st = getComputedStyle(e);
  return st.display !== 'none' && st.visibility !== 'hidden';
}

function mesureContenu() {
  const bar = $('bar');
  const r = bar.getBoundingClientRect();
  let larg = r.right, haut = r.bottom;
  for (const {id, marge} of HORS_FLUX) {
    const c = $(id);
    if (!estVisible(c)) continue;
    const cr = c.getBoundingClientRect();
    if (!cr.width) continue;
    larg = Math.max(larg, cr.right + marge);
    haut = Math.max(haut, cr.bottom + marge);
  }
  for (const e of bar.children) {
    const st = getComputedStyle(e);
    if (st.position === 'absolute' || st.position === 'fixed') continue;
    if (st.display === 'none' || st.visibility === 'hidden') continue;
    const c = e.getBoundingClientRect();
    if (!c.width) continue;
    larg = Math.max(larg, c.right);
    haut = Math.max(haut, c.bottom);
  }
  return [larg, haut];
}

async function ajusteFenetreAuContenu() {
  const pv = window.pywebview && window.pywebview.api;
  if (!pv || typeof pv.taille_bulle !== 'function') return;
  if (estVisible($('popup'))) return;
  const [larg, haut] = mesureContenu();
  if (larg < 20 || haut < 12) return;
  const k = window.devicePixelRatio || 1;
  const w = Math.ceil(larg * k), h = Math.ceil(haut * k);
  const cle = w + 'x' + h;
  if (cle === _tailleDemandee) return;
  _tailleDemandee = cle;
  try {
    await pv.taille_bulle(w, h);
  } catch (e) { _tailleDemandee = ''; }
}

let _ajusteTimer = null;
function planifieAjustement() {
  clearTimeout(_ajusteTimer);
  _ajusteTimer = setTimeout(ajusteFenetreAuContenu, 24);
}
window.planifieAjustement = planifieAjustement;

try {
  const obs = new ResizeObserver(planifieAjustement);
  for (const id of ['bar', ...HORS_FLUX.map(h => h.id)]) {
    const e = $(id);
    if (e) obs.observe(e);
  }
} catch (e) {  }

function applyBulle() {
  BULLE = true;
  document.body.classList.add('bulle');
  profileTouch();
  if (docked && typeof detache === 'function') detache();
  BULLE_IDX = 0;
  poseAncre(null);
  derniereCible = null;
  applyOpacity(false);
  renderText();
  fitBulle();
  setStatus(t('etat.enbulle', 'Flèches ou molette pour changer de ligne.'));
}
window.toggleBulle = () => {
  applyBulle();
  if (typeof ajusteFenetreAuContenu === 'function') ajusteFenetreAuContenu();
};
$('bulleout').addEventListener('click', () => {
  const pv = window.pywebview && window.pywebview.api;
  if (pv && typeof pv.minimize_window === 'function') pv.minimize_window();
});
$('bquit').addEventListener('click', () => {
  const pv = window.pywebview && window.pywebview.api;
  if (pv && typeof pv.close_app === 'function') pv.close_app();
});

function bulleGo(pas) {
  const jp = lignesBulle();
  const n = jp.length;
  if (!n) return;
  BULLE_IDX = (ancreBulle(jp) + pas + n) % n;
  poseAncre(jp[BULLE_IDX]);
  verrouilleLecture();
  derniereCible = null;
  renderText();
  fitBulle(true);
}
$('bprev').addEventListener('click', () => bulleGo(-1));
$('bnext').addEventListener('click', () => bulleGo(+1));

document.addEventListener('keydown', ev => {
  if (!BULLE) return;
  if (typeof capturingHk !== 'undefined' && capturingHk) return;
  const t = ev.target;
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
  if (ev.key === 'ArrowRight' || ev.key === 'PageDown') { ev.preventDefault(); bulleGo(+1); }
  else if (ev.key === 'ArrowLeft' || ev.key === 'PageUp') { ev.preventDefault(); bulleGo(-1); }
});

function majBset() {
  const on = $('bset').classList.contains('show');
  $('bgear').classList.toggle('on', on);
  if ($('bopacity')) { $('bopacity').value = OPACITY; $('bopacitylbl').textContent = OPACITY + ' %'; }
  if ($('bopacitylec')) { $('bopacitylec').value = OPACITY_LECTURE;
                          $('bopacityleclbl').textContent = OPACITY_LECTURE + ' %'; }
  if ($('bfslbl')) $('bfslbl').textContent = FS + ' px';
  if ($('bafbtn')) $('bafbtn').classList.toggle('on', !!AUTOFREEZE);
  const bm = $('bmuet');
  if (bm && typeof MUET !== 'undefined') {
    bm.textContent = MUET ? t('bulle.reprendre', 'Reprendre la lecture')
                          : t('bulle.pause', 'Mettre en pause');
    const h = $('bmuethint');
    if (h) h.textContent = MUET ? t('etat.enpause.court', 'rien ne s\'affichera')
                                : '';
  }
}
function toggleBset() {
  const el = $('bset');
  el.classList.toggle('show');
  document.body.classList.toggle('panneau', el.classList.contains('show'));
  majBset();
  suitLaRecolte(el.classList.contains('show'));
  derniereCible = null;
  if (enAttente) {
    requestAnimationFrame(() => requestAnimationFrame(ajusteFenetreAuContenu));
    return;
  }
  fitBulle(true);
}
$('bgrip').addEventListener('mousedown', ev => {
  ev.preventDefault();
  if (typeof startDrag === 'function') startDrag(ev);
});
let JEUX = [];
async function relisJeuxBulle() {
  try {
    const r = await fetch('/api/windows').then(r => r.json());
    JEUX = (r.windows || [])
      .map(t => (typeof t === 'string' ? t : (t && t.title) || ''))
      .filter(t => t && !/DNAreader/i.test(t));
  } catch (e) { return; }

  peinsListeJeux();
}

function peinsListeJeux() {
  const el = $('bjeuliste');
  if (!el) return;
  if (!JEUX.length) {
    el.innerHTML = '<div class="vide">Aucune fenêtre trouvée. Lance le jeu.</div>';
    return;
  }
  el.innerHTML = '';
  for (const titre of JEUX) {
    const d = document.createElement('div');
    d.className = 'jeu' + (titre === gameTitle ? ' actif' : '');
    d.textContent = titre;
    d.title = titre;
    d.addEventListener('click', () => {
      if (typeof setGame === 'function') setGame(titre);
      fermeListeJeux();
    });
    el.appendChild(d);
  }
}

function majEtiquetteJeu() {
  const l = $('bjeulbl');
  if (l) l.textContent = gameTitle || t('jeu.choisir', 'Jeu à lire');
}

function ouvreListeJeux() {
  document.body.classList.add('liste-jeux');
  relisJeuxBulle();
  requestAnimationFrame(() => requestAnimationFrame(ajusteFenetreAuContenu));
}

function fermeListeJeux() {
  if (!document.body.classList.contains('liste-jeux')) return;
  document.body.classList.remove('liste-jeux');
  requestAnimationFrame(() => requestAnimationFrame(ajusteFenetreAuContenu));
}

function bascListeJeux() {
  if (document.body.classList.contains('liste-jeux')) fermeListeJeux();
  else ouvreListeJeux();
}

$('bjeu').addEventListener('click', bascListeJeux);
document.addEventListener('keydown', ev => {
  if (ev.key === 'Escape') fermeListeJeux();
});

setInterval(() => {
  if (!gameTitle && BULLE) relisJeuxBulle();
}, 5000);
$('bgear').addEventListener('click', toggleBset);
$('bgear').addEventListener('contextmenu', ev => {
  ev.preventDefault();
  ouvreReglages();
});
function ouvreReglages() {
  const pv = window.pywebview && window.pywebview.api;
  if (!pv || typeof pv.ouvrir_reglages !== 'function') {
    setStatus('Fenêtre de réglages indisponible'); return;
  }
  annonceEtat();
  pv.ouvrir_reglages();
  setStatus('Réglages ouverts.');
}
$('bsetplus').addEventListener('click', ouvreReglages);
$('bjeu2').addEventListener('click', () => {
  document.body.classList.remove('veille');
  if (typeof ouvreListeJeux === 'function') ouvreListeJeux();
});
let zoneApprise = null;
async function apprendUnEndroit() {
  const pv = window.pywebview && window.pywebview.api;
  if (!pv || typeof pv.pick_region !== 'function') {
    setStatus('(mode navigateur : sélection indispo)'); return;
  }
  if (!gameTitle) { setStatus("Choisis d'abord le jeu à lire."); return; }
  setStatus('Entoure le texte que l\'app ne voit pas…');
  let r = null;
  try { r = await pv.pick_region(gameTitle); } catch (e) {}
  if (!r || !r.region) { setStatus('Apprentissage annulé'); return; }
  zoneApprise = r.region;
  document.body.classList.add('apprend');
  const champ = $('bapprendtexte');
  champ.value = '';
  champ.placeholder = 'lecture en cours…';
  planifieAjustement();
  let propose = '';
  try {
    const rep = await api('/api/zone-lire', {jeu: gameTitle, rect: zoneApprise});
    propose = (rep && rep.texte) || '';
  } catch (e) {}
  champ.value = propose;
  champ.placeholder = 'ce que tu lis à l\'écran';
  setStatus(propose ? 'Corrige si besoin, puis « Retenir ».'
                    : 'Rien lu ici : écris ce qui est affiché.');
  champ.focus();
  champ.select();
  planifieAjustement();
}

async function retientLEndroit() {
  const texte = $('bapprendtexte').value.trim();
  if (!zoneApprise) { fermeApprentissage(); return; }
  try {
    const r = texte
      ? await api('/api/zone-apprise', {jeu: gameTitle, rect: zoneApprise, texte})
      : await api('/api/zone-apprise/remove', {jeu: gameTitle, rect: zoneApprise});
    if (!r || r.ok === false) {
      setStatus(`Apprentissage refusé : ${(r && r.error) || '?'}`);
    } else if (texte) {
      setStatus(`Endroit appris : « ${texte} ». Il sera relu à chaque image.`);
    } else {
      setStatus(r.retire ? 'Endroit oublié.' : 'Aucun endroit appris ici.');
    }
    if (r && r.ok !== false) { lastSig = null; resetLive(); }
  } catch (e) { setStatus('Apprentissage impossible : ' + e); }
  fermeApprentissage();
  majCompteurAppris();
}

function fermeApprentissage() {
  zoneApprise = null;
  document.body.classList.remove('apprend');
  $('bapprendtexte').value = '';
  planifieAjustement();
}

async function majCompteurAppris() {
  const el = $('bapprendnb');
  if (!el || !gameTitle) return;
  try {
    const r = await fetch('/api/zones-apprises?jeu=' + encodeURIComponent(gameTitle))
                    .then(x => x.json());
    const z = r.zones || [];
    el.textContent = z.length ? `${z.length} endroit(s) appris pour ce jeu` : '';
    el.title = z.length
      ? z.map(x => '« ' + x.texte + ' »').join('\n')
        + '\n\nPour en corriger un : réapprends le même endroit.'
        + '\nPour l\'oublier : réapprends-le en laissant le champ vide.'
      : '';
  } catch (e) {}
}

$('bapprend').addEventListener('click', apprendUnEndroit);
$('bapprendok').addEventListener('click', retientLEndroit);
$('bapprendnon').addEventListener('click', () => {
  fermeApprentissage();
  setStatus('Apprentissage annulé');
});
$('bapprendtexte').addEventListener('keydown', ev => {
  if (ev.key === 'Enter') { ev.preventDefault(); retientLEndroit(); }
  if (ev.key === 'Escape') { ev.preventDefault(); fermeApprentissage(); }
});

$('bzone').addEventListener('click', () => {
  if (typeof startZonePick === 'function') startZonePick();
});
$('bfenetre').addEventListener('click', () => {
  const pv = window.pywebview && window.pywebview.api;
  if (pv && typeof pv.set_mode === 'function') pv.set_mode('window', gameTitle || null);
  else setStatus('(mode navigateur : ouvre la page / pour la vue fenêtre)');
});
let RECOLTE_TIMER = null;

function peinsRecolteBulle(r) {
  const b = $('brecolte');
  if (!b || !r || !r.ok) return;
  b.classList.toggle('on', !!r.actif);
  b.textContent = r.actif ? t('etat.activee', 'Activée')
                          : t('etat.desactivee', 'Désactivée');
  const l = $('brecoltelbl');
  if (l) {
    const env = (r.envoi && r.envoi.envoyees) || 0;
    l.textContent = r.lignes
      ? t('recolte.compte', '{0} lignes gardées · {1} envoyées')
          .replace('{0}', r.lignes).replace('{1}', env)
      : (r.actif ? t('recolte.attente', 'en attente de texte…')
                 : t('recolte.aide',
                     'envoie les lignes sûres pour entraîner le lecteur commun'));
  }
}

async function relisRecolteBulle() {
  try {
    peinsRecolteBulle(await fetch('/api/recolte').then(x => x.json()));
  } catch (e) {  }
}

function suitLaRecolte(ouvert) {
  clearInterval(RECOLTE_TIMER);
  RECOLTE_TIMER = null;
  if (!ouvert || !$('brecolte')) return;
  relisRecolteBulle();
  RECOLTE_TIMER = setInterval(relisRecolteBulle, 5000);
}

if ($('brecolte')) {
  $('brecolte').addEventListener('click', async () => {
    const b = $('brecolte');
    const etait = b.classList.contains('on');
    try {
      peinsRecolteBulle(await api('/api/recolte', {actif: !etait}));
    } catch (e) { return; }
    setStatus(etait ? t('recolte.arret', 'Récolte arrêtée.')
                    : t('recolte.marche',
                        'Récolte en cours : joue normalement.'));
  });
}

if ($('bmodebulle')) {
  $('bmodebulle').addEventListener('click', () => {
    if (typeof BULLE !== 'undefined' && !BULLE) { BULLE = true; applyBulle(); }
    majModeAffichage();
  });
}

function majModeAffichage() {
  const enBulle = (typeof BULLE === 'undefined') || BULLE;
  if ($('bmodebulle')) $('bmodebulle').classList.toggle('on', enBulle);
  if ($('bfenetre')) $('bfenetre').classList.toggle('on', !enBulle);
}
majModeAffichage();
$('bopacity').addEventListener('input', () => {
  OPACITY = +$('bopacity').value; $('bopacitylbl').textContent = OPACITY + ' %';
  applyOpacity(true);
});
$('bopacitylec').addEventListener('input', () => {
  OPACITY_LECTURE = +$('bopacitylec').value;
  $('bopacityleclbl').textContent = OPACITY_LECTURE + ' %';
  applyOpacity(true);
});
$('bfsdown').addEventListener('click', () => { FS -= 2; applyFS(); majBset(); fitBulle(); });
$('bfsup').addEventListener('click',   () => { FS += 2; applyFS(); majBset(); fitBulle(); });
$('bafbtn').addEventListener('click',  () => { AUTOFREEZE = !AUTOFREEZE; applyAutoFreeze(); majBset(); });
$('text').addEventListener('wheel', ev => {
  if (!BULLE || ev.ctrlKey) return;
  ev.preventDefault();
  bulleGo(ev.deltaY > 0 ? +1 : -1);
}, {passive: false});

let degelTimer = null;
function geler()  { clearTimeout(degelTimer); bulleSurvolee = true; }
function degeler() {
  clearTimeout(degelTimer);
  degelTimer = setTimeout(() => { bulleSurvolee = false; fitBulle(); }, 260);
}
$('bar').addEventListener('mouseenter', geler);
$('bar').addEventListener('mouseleave', degeler);
$('popup').addEventListener('mouseenter', geler);
$('popup').addEventListener('mouseleave', degeler);

function majCompteur() {
  const n = lignesBulle().length;
  $('bidx').textContent = n ? `${BULLE_IDX + 1}/${n}` : '·';
  $('bprev').disabled = $('bnext').disabled = n < 2;
}

const VERROU_MS = 5000;
let verrouJusqua = 0;
function verrouilleLecture() { verrouJusqua = Date.now() + VERROU_MS; }
function lectureVerrouillee() { return Date.now() < verrouJusqua; }

async function fitBulle(force) {
  if (!BULLE || (bulleSurvolee && !force)) return;
  if (!force && lectureVerrouillee()) { majCompteur(); return; }
  const pv = window.pywebview && window.pywebview.api;
  if (!pv || typeof pv.place_bubble !== 'function') return;
  const jp = lignesBulle();
  majCompteur();

  if (!jp.length) {
    montreBulleEnAttente();
    return;
  }
  if (bulleVide && typeof pv.bubble_visible === 'function') await pv.bubble_visible(true);
  bulleVide = false;
  if (enAttente) {
    enAttente = false;
    document.body.classList.remove('attente');
    document.body.classList.remove('veille');
    if (typeof applyOpacity === 'function') applyOpacity(false);
  }

  BULLE_IDX = ancreBulle(jp);
  const ligne = jp[BULLE_IDX];

  if (($('text').dataset.rendu || '') !== clePiste(ligne)) {
    poseAncre(ligne);
    renderText();
  }
  poseAncre(ligne);

  const cible = [ligne.id != null ? 'p' + ligne.id : ligne.text,
                 Math.round(ligne.box[0] / 40),
                 Math.round(ligne.box[1] / 40),
                 getComputedStyle($('popup')).display !== 'none',
                 $('bset').classList.contains('show')].join('|');
  if (cible === derniereCible) return;
  derniereCible = cible;
  const r = window.devicePixelRatio || 1;
  const bar = $('bar');
  const pop = $('popup');
  const fiche = getComputedStyle(pop).display !== 'none';

  const rbAvant = bar.getBoundingClientRect();

  if (fiche) {
    let g = null;
    try { g = await pv.get_geometry(); } catch (e) {}
    const barreY = g ? g.y + rbAvant.top * r : 0;

    bar.style.top = '';
    pop.style.maxHeight = '';
    pop.style.top = '0px';
    pop.style.left = '0px';
    const rb = bar.getBoundingClientRect();
    const largeurCommune = Math.max(410, Math.ceil(rb.width));
    pop.style.width = largeurCommune + 'px';
    bar.style.minWidth = largeurCommune + 'px';
    const voulue = Math.min(pop.scrollHeight + 2, 520);
    let dispoBas = 1e9, dispoHaut = 0;
    if (g && g.ecran) {
      dispoBas = Math.floor((g.ecran.y1 - (barreY + rb.height * r)) / r) - 16;
      dispoHaut = Math.floor((barreY - g.ecran.y0) / r) - 16;
      const barreX = g.x + rb.left * r;
      const dispoDroite = Math.floor((g.ecran.x1 - barreX) / r) - 12;
      pop.style.maxWidth = dispoDroite > 240 ? dispoDroite + 'px' : '';
    }
    if (fichePour !== null && fichePour === ligne.id) {
    } else {
      ficheEnHaut = dispoBas < CONFORT_FICHE && dispoHaut > dispoBas + 80;
      fichePour = ligne.id != null ? ligne.id : null;
    }
    const place = ficheEnHaut ? dispoHaut - rb.height - 8 : dispoBas;
    const plafond = Math.min(voulue, Math.max(120, place));
    pop.style.maxHeight = plafond + 'px';
    if (ficheEnHaut) {
      pop.style.top = '0px';
      const hp = Math.ceil(pop.getBoundingClientRect().height);
      bar.style.top = (hp + 4) + 'px';
    } else {
      bar.style.top = '';
      pop.style.top = Math.ceil(rb.bottom + 4) + 'px';
    }
  } else {
    pop.style.maxHeight = '';
    pop.style.maxWidth = '';
    pop.style.width = '';
    bar.style.minWidth = '';
    bar.style.top = '';
  }
  const [larg, haut] = mesureContenu();
  const w = Math.ceil(larg), h = Math.ceil(haut);
  try {
    await pv.place_bubble(ligne.box, Math.ceil(w * r), Math.ceil(h * r),
                          gameTitle || null, currentRegion(), fiche, fiche,
                          ficheEnHaut, fiche);
    if (!fiche) { ficheEnHaut = false; fichePour = null; }
    _tailleDemandee = Math.ceil(w * r) + 'x' + Math.ceil(h * r);
  } catch (e) {}
}

window.bulleFiche = () => {
  if (!BULLE) return;
  derniereCible = null;
  fitBulle(true);
};
