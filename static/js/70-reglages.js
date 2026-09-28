const $ = id => document.getElementById(id);
let ETAT = {};
let HOT = {};

function dit(msg, classe) {
  const e = $('etat');
  e.textContent = msg;
  e.className = classe || '';
}

async function poste(route, corps) {
  try {
    const r = await fetch(route, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(corps || {})
    });
    return await r.json();
  } catch (e) { return {ok: false, error: String(e)}; }
}

async function regle(cle, valeur) {
  ETAT[cle] = valeur;
  await poste('/api/reglage', {cle, valeur});
}

function peins() {
  const b = (id, on, oui, non) => {
    const e = $(id);
    e.classList.toggle('on', !!on);
    e.textContent = on ? oui : non;
  };
  const oui = t('etat.actif', 'Activé'), non = t('etat.inactif', 'Désactivé');
  peinsLeMoteur();
  b('flux', ETAT.stream !== false, t('etat.activee', 'Activée'),
    t('etat.desactivee', 'Désactivée'));
  b('surlignage', ETAT.gamehl !== false, oui, non);
  b('gelauto', !!ETAT.autofreeze, oui, non);
  if (ETAT.enhance) $('contraste').value = ETAT.enhance;
  if (ETAT.mode) $('traduction').value = ETAT.mode;
  const o = ETAT.opacity == null ? 100 : ETAT.opacity;
  $('opacite').value = o; $('opacitelbl').textContent = o + ' %';
  const ol = ETAT.opacitylec == null ? 100 : ETAT.opacitylec;
  $('opacitelec').value = ol; $('opaciteleclbl').textContent = ol + ' %';
  const f = ETAT.fontsize == null ? 26 : ETAT.fontsize;
  $('taille').value = f; $('taillelbl').textContent = f + ' px';
  $('jeu').textContent = ETAT.jeu ? t('lbl.jeu', 'Jeu') + ' : ' + ETAT.jeu
                                 : t('reg.aucunjeu', 'aucun jeu sélectionné');
  if (ETAT.jeu && $('jeusel').value !== ETAT.jeu) $('jeusel').value = ETAT.jeu;
  if (ETAT.zone !== undefined && $('zonelbl')) {
    $('zonelbl').textContent = ETAT.zone ? 'zone définie' : "tout l'écran";
  }
  $('modebulle').classList.toggle('on', !!ETAT.bulle);
  $('modefen').classList.toggle('on', false);
}

async function relis() {
  try {
    const r = await fetch('/api/reglage').then(r => r.json());
    ETAT = r.reglages || {};
    peins();
  } catch (e) {}
}

let MOTEURS_DISPO = ['windows'];
const MOTEUR_LIBELLE = {
  windows: () => t('reg.moteur.rapide', 'Rapide (Windows)'),
  maison: () => t('reg.moteur.maison', 'DNAreader (embarqué)'),
  precise: () => t('reg.moteur.precis', 'Haute précision (IA)'),
};

function moteurCourant() {
  const e = ETAT.engine === 'fast' ? 'windows' : ETAT.engine;
  return MOTEURS_DISPO.includes(e) ? e : 'windows';
}

function peinsLeMoteur() {
  const e = $('moteur');
  if (!e) return;
  const cour = moteurCourant();
  e.textContent = (MOTEUR_LIBELLE[cour] || MOTEUR_LIBELLE.windows)();
  e.classList.toggle('on', cour !== 'windows');
  const seul = MOTEURS_DISPO.length < 2;
  e.disabled = seul;
  e.style.opacity = seul ? .45 : '';
  e.title = seul
    ? t('reg.moteur.seul',
        "Un seul moteur est livré avec l'application. La haute précision "
        + "demande manga-ocr (2 Go), qui s'installe à côté.")
    : t('reg.moteur.tour', 'Clique pour passer au moteur suivant');
}

fetch('/api/engines').then(r => r.json()).then(d => {
  MOTEURS_DISPO = ['windows'];
  if (d.maison) MOTEURS_DISPO.push('maison');
  if (d.precise) MOTEURS_DISPO.push('precise');
  peinsLeMoteur();
}).catch(() => {});

$('moteur').addEventListener('click', () => {
  if ($('moteur').disabled) return;
  const cour = moteurCourant();
  const suivant = MOTEURS_DISPO[(MOTEURS_DISPO.indexOf(cour) + 1)
                                % MOTEURS_DISPO.length];
  regle('engine', suivant).then(peins);
  peins();
});
$('flux').addEventListener('click', () => {
  regle('stream', ETAT.stream === false); peins();
});
$('surlignage').addEventListener('click', () => {
  regle('gamehl', ETAT.gamehl === false); peins();
});
$('gelauto').addEventListener('click', () => {
  regle('autofreeze', !ETAT.autofreeze); peins();
});
$('contraste').addEventListener('change', () => regle('enhance', $('contraste').value));
$('traduction').addEventListener('change', () => regle('mode', $('traduction').value));
$('opacite').addEventListener('input', () => {
  const v = +$('opacite').value;
  $('opacitelbl').textContent = v + ' %';
  regle('opacity', v);
});
$('opacitelec').addEventListener('input', () => {
  const v = +$('opacitelec').value;
  $('opaciteleclbl').textContent = v + ' %';
  regle('opacitylec', v);
});
$('taille').addEventListener('input', () => {
  const v = +$('taille').value;
  $('taillelbl').textContent = v + ' px';
  regle('fontsize', v);
});
function peinsRecolte(r) {
  if (!r || !$('recolte')) return;
  $('recolte').textContent = r.actif ? t('etat.activee', 'Activée')
                                     : t('etat.desactivee', 'Désactivée');
  $('recolte').classList.toggle('on', !!r.actif);
  const env = (r.envoi && r.envoi.envoyees) || 0;
  $('recoltecompte').textContent = r.lignes
    ? `${r.lignes} gardée(s) · ${env} envoyée(s)`
    : (r.actif ? 'en attente de texte…' : '');
}
function relisRecolte() {
  fetch('/api/recolte').then(r => r.json()).then(peinsRecolte).catch(() => {});
}
if ($('recolte')) {
  $('recolte').addEventListener('click', async () => {
    const on = !$('recolte').classList.contains('on');
    peinsRecolte(await poste('/api/recolte', {actif: on}));
    dit(on ? 'Merci ! Joue normalement : les lignes sûres partent entraîner '
           + 'le lecteur commun.'
           : 'Arrêté. Plus rien ne sera envoyé.');
  });
  relisRecolte();
  setInterval(relisRecolte, 5000);
}

$('visite').addEventListener('click', () => {
  regle('tuto', true);
  dit('Visite lancée.');
});
$('modebulle').addEventListener('click', () => {
  regle('bulle', true);
  dit('Mode bulle.');
});
$('modefen').addEventListener('click', () => {
  regle('modefenetre', true);
  dit('Passage en mode fenêtre.');
});

async function relisJeux() {
  try {
    const r = await fetch('/api/windows').then(r => r.json());
    const sel = $('jeusel');
    const choisi = ETAT.jeu || sel.value;
    sel.innerHTML = '<option value="">' + t('jeu.choisir', 'Jeu à lire') + '</option>';
    for (const t of (r.windows || r.titles || [])) {
      const titre = typeof t === 'string' ? t : (t.title || '');
      if (!titre || /DNAreader/i.test(titre)) continue;
      const o = document.createElement('option');
      o.value = titre; o.textContent = titre;
      sel.appendChild(o);
    }
    if (choisi) sel.value = choisi;
  } catch (e) {}
}
$('relirejeux').addEventListener('click', () => { relisJeux(); dit('Liste actualisée.'); });
$('jeusel').addEventListener('mousedown', relisJeux);
$('jeusel').addEventListener('focus', relisJeux);
$('jeusel').addEventListener('change', () => {
  regle('jeu', $('jeusel').value);
  if (PARTAGE.actif && $('jeusel').value) {
    poste('/api/partage/tirer', {jeu: $('jeusel').value}).then(r => {
      if (r && r.ok && r.ajoutees) {
        dit(`${r.ajoutees} correction(s) partagée(s) récupérée(s) pour ce jeu.`, 'ok');
        relisPartage();
      }
    });
  }
  dit($('jeusel').value ? 'Jeu : ' + $('jeusel').value : 'Aucun jeu.');
});
$('lirebtn').addEventListener('click', () => { regle('lire', true); dit('Lecture…'); });
$('zonebtn').addEventListener('click', () => {
  regle('zone', true);
  dit('Trace le rectangle sur le jeu.');
});
relisJeux();
setInterval(relisJeux, 8000);

function peinsHot() {
  for (const [nom, val] of Object.entries(HOT)) {
    const e = $('k_' + nom);
    if (e) e.textContent = String(val).toUpperCase();
  }
}
let enCapture = null;
document.querySelectorAll('.rebind').forEach(b => {
  b.addEventListener('click', () => {
    enCapture = b.dataset.hk;
    b.classList.add('on');
    $('hkhint').textContent = 'Appuie sur la touche voulue… (Échap pour annuler)';
  });
});
document.addEventListener('keydown', async ev => {
  if (!enCapture) return;
  ev.preventDefault(); ev.stopPropagation();
  const bouton = document.querySelector(`.rebind[data-hk="${enCapture}"]`);
  const nom = enCapture; enCapture = null;
  if (bouton) bouton.classList.remove('on');
  if (ev.key === 'Escape') { $('hkhint').textContent = 'Inchangé.'; return; }
  const parts = [];
  if (ev.ctrlKey) parts.push('ctrl');
  if (ev.altKey) parts.push('alt');
  if (ev.shiftKey) parts.push('shift');
  const base = ev.key.toLowerCase();
  if (!['control', 'alt', 'shift'].includes(base)) parts.push(base);
  const r = await poste('/api/hotkey', {hotkey: parts.join('+'), name: nom});
  if (r && r.error) { $('hkhint').textContent = r.error; return; }
  HOT = Object.assign({}, HOT, r.hotkeys || {});
  peinsHot();
  $('hkhint').textContent = `« ${parts.join('+').toUpperCase()} » enregistré.`;
}, true);

function peinsCompte(c) {
  const e = $('compteetat');
  if (c && c.connecte) {
    const q = c.derniere_sync
      ? ' · dernière synchro ' + new Date(c.derniere_sync * 1000).toLocaleString()
      : ' · jamais synchronisé';
    e.textContent = 'Connecté : ' + c.identifiant + q;
    e.className = 'val ok';
    if (c.serveur) $('serveur').value = c.serveur;
    $('identifiant').value = c.identifiant || '';
  } else {
    e.textContent = 'Non connecté';
    e.className = 'val';
  }
}

async function relisCompte() {
  try { peinsCompte(await fetch('/api/compte').then(r => r.json())); } catch (e) {}
}

function champsCompte() {
  return {serveur: $('serveur').value.trim(),
          identifiant: $('identifiant').value.trim(),
          motdepasse: $('motdepasse').value};
}

$('inscription').addEventListener('click', async () => {
  dit('Création du compte…');
  const r = await poste('/api/compte/inscription', champsCompte());
  dit(r.ok ? 'Compte créé et connecté.' : 'Échec : ' + r.error, r.ok ? 'ok' : 'ko');
  relisCompte();
});
$('connexion').addEventListener('click', async () => {
  dit('Connexion…');
  const r = await poste('/api/compte/connexion', champsCompte());
  dit(r.ok ? 'Connecté.' : 'Échec : ' + r.error, r.ok ? 'ok' : 'ko');
  relisCompte();
});
$('deconnexion').addEventListener('click', async () => {
  await poste('/api/compte/deconnexion', {});
  dit('Déconnecté. Tes données restent sur cette machine.');
  relisCompte();
});
$('synchroniser').addEventListener('click', async () => {
  dit('Synchronisation…');
  const r = await poste('/api/compte/sync', {});
  if (!r.ok) { dit('Échec : ' + r.error, 'ko'); return; }
  const a = r.ajoutes || {};
  dit(`Synchronisé : ${a.mots || 0} mot(s), ${a.profils || 0} profil(s), `
    + `${a.corrections || 0} correction(s) récupéré(s).`, 'ok');
  relisCompte();
});

$('exporter').addEventListener('click', async () => {
  const r = await poste('/api/compte/export', {});
  $('fichieretat').textContent = r.ok ? '' : '';
  dit(r.ok ? 'Exporté dans ' + r.chemin : 'Échec : ' + r.error, r.ok ? 'ok' : 'ko');
});
$('importer').addEventListener('click', async () => {
  const pv = window.pywebview && window.pywebview.api;
  let chemin = '';
  if (pv && typeof pv.choisir_fichier === 'function') {
    try { chemin = await pv.choisir_fichier(); } catch (e) {}
  }
  if (!chemin) { dit('Import annulé.'); return; }
  const r = await poste('/api/compte/import', {chemin});
  if (!r.ok) { dit('Échec : ' + r.error, 'ko'); return; }
  const a = r.ajoutes || {};
  dit(`Importé : ${a.mots || 0} mot(s), ${a.profils || 0} profil(s), `
    + `${a.corrections || 0} correction(s) ajouté(s).`, 'ok');
});

let PARTAGE = {};

function peinsPartage() {
  const b = $('partagebtn');
  b.classList.toggle('on', !!PARTAGE.actif);
  b.textContent = PARTAGE.actif ? 'Activé' : 'Désactivé';
  if (PARTAGE.serveur && !$('partageserveur').value) {
    $('partageserveur').value = PARTAGE.serveur;
  }
  $('partageetat').textContent = PARTAGE.actif
    ? `${PARTAGE.envoyees || 0} envoyée(s) · ${PARTAGE.recues || 0} reçue(s)`
    : '';
}

async function relisPartage() {
  try { PARTAGE = await fetch('/api/partage').then(r => r.json()); } catch (e) { return; }
  peinsPartage();
}

$('partagebtn').addEventListener('click', async () => {
  const r = await poste('/api/partage', {actif: !PARTAGE.actif,
                                         serveur: $('partageserveur').value.trim()});
  PARTAGE = r; peinsPartage();
  dit(PARTAGE.actif ? 'Partage activé. Il faut être connecté pour contribuer.'
                    : 'Partage désactivé.');
});
$('partageserveur').addEventListener('change', async () => {
  PARTAGE = await poste('/api/partage', {serveur: $('partageserveur').value.trim()});
  peinsPartage();
});

$('partagetirer').addEventListener('click', async () => {
  if (!ETAT.jeu) { dit('Choisis d\'abord un jeu.', 'ko'); return; }
  dit('Récupération…');
  const r = await poste('/api/partage/tirer', {jeu: ETAT.jeu});
  if (!r.ok) { dit('Échec : ' + r.error, 'ko'); return; }
  dit(`${r.ajoutees} correction(s) ajoutée(s) sur ${r.disponibles} confirmée(s).`, 'ok');
  relisPartage();
});

$('partagevoir').addEventListener('click', async () => {
  if (!ETAT.jeu) { dit('Choisis d\'abord un jeu.', 'ko'); return; }
  const el = $('partageliste');
  el.innerHTML = '';
  let r;
  try {
    r = await fetch('/api/partage/propositions?jeu='
                    + encodeURIComponent(ETAT.jeu)).then(x => x.json());
  } catch (e) { dit('Serveur injoignable.', 'ko'); return; }
  if (!r.ok) { dit('Échec : ' + r.error, 'ko'); return; }
  const props = r.corrections || [];
  if (!props.length) { el.innerHTML = '<div class="aide">Aucune proposition en attente.</div>'; return; }
  for (const p of props) {
    const d = document.createElement('div');
    d.className = 'prop';
    d.innerHTML = `<span class="faux">${p.faux}</span>`
      + `<span class="juste">${p.juste}</span>`
      + `<span class="voix">${p.pour} pour · ${p.contre} contre</span>`;
    const c = document.createElement('button');
    c.textContent = 'Contester';
    c.addEventListener('click', async () => {
      const x = await poste('/api/partage/contester',
                            {jeu: ETAT.jeu, faux: p.faux, juste: p.juste});
      dit(x.ok ? 'Signalée.' : 'Échec : ' + x.error, x.ok ? 'ok' : 'ko');
    });
    d.appendChild(c);
    el.appendChild(d);
  }
  dit(`${props.length} proposition(s) en attente de confirmation.`);
});

relisPartage();

function monteLangues() {
  const sel = $('langue');
  if (!sel) return;
  sel.innerHTML = '';
  for (const [code, nom] of Object.entries(LANGUES)) {
    const o = document.createElement('option');
    o.value = code; o.textContent = nom;
    sel.appendChild(o);
  }
  sel.value = LANGUE;
}
if ($('langue')) {
  $('langue').addEventListener('change', () => {
    changeLangue($('langue').value);
    regle('langue', LANGUE);
    peins(); peinsHot(); relisCompte();
  });
}
monteLangues();
traduisPage();

async function relisContributions() {
  const ligne = $('contribligne');
  if (!ligne) return;
  let c;
  try {
    c = await fetch('/api/contributions').then(x => x.json());
  } catch (e) { ligne.style.display = 'none'; return; }

  const chiffres = $('contribchiffres');
  const texte = $('contribtexte');

  if (!c.ok) {
    chiffres.textContent = '';
    texte.textContent = c.inactif
      ? 'Active le partage ci-dessus pour que tes corrections comptent.'
      : (c.sans_compte
         ? 'Connecte-toi avec un compte : sans identité, on ne peut pas savoir '
           + 'qui a proposé quoi.'
         : (c.error || ''));
    return;
  }

  const gros = (n, l) =>
    `<span><b style="font-size:22px">${n}</b>`
    + `<span class="aide" style="margin-left:6px">${l}</span></span>`;

  chiffres.innerHTML =
      gros(c.confirmees, 'confirmée(s)')
    + gros(c.en_attente, 'en attente');

  texte.textContent =
    "Une correction compte quand d'autres comptes la confirment. "
    + 'Elle est alors appliquée chez tous les joueurs du même jeu.';
}

async function relisCle() {
  const el = $('cleetat');
  if (!el) return;
  try {
    const r = await fetch('/api/licence').then(x => x.json());
    if (r.serveur && $('cleserveur') && !$('cleserveur').value) {
      $('cleserveur').value = r.serveur;
    }
    if (r.serveur_impose && $('cleserveur')) {
      $('cleserveur').value = r.serveur;
      $('cleserveur').readOnly = true;
      $('cleserveur').title = "Fourni avec l'application, rien à saisir.";
      $('cleserveur').style.opacity = '.7';
    }
    if (r.serveur_impose) {
      for (const id of ['serveur', 'partageserveur']) {
        const e = $(id);
        if (e && !e.value) {
          e.value = r.serveur;
          e.title = "Fourni avec l'application. Modifiable si tu héberges le tien.";
        }
      }
    }
    if (r.ok) {
      let a = {};
      try { a = await fetch('/api/acces').then(x => x.json()); } catch (e) {}
      const quand = a.expire
        ? new Date(a.expire * 1000).toLocaleDateString('fr-FR',
            {day: 'numeric', month: 'long'})
        : '';
      const j = Math.floor(a.jours_avant_echeance ?? r.jours_restants ?? 0);
      if (a.abonnement === 'active' && quand) {
        el.textContent = `Abonnement actif, renouvelé le ${quand}`;
        el.style.color = 'var(--accent)';
      } else if (quand) {
        el.textContent = `Clé active jusqu'au ${quand}`;
        el.style.color = 'var(--accent)';
      } else {
        el.textContent = `Active : ${r.cle_masquee}`;
        el.style.color = 'var(--accent)';
      }
      if (r.hors_ligne) el.textContent += ` · hors ligne, ${j} j de marge`;
    } else if (r.aucune_cle) {
      let a = {};
      try { a = await fetch('/api/acces').then(x => x.json()); } catch (e) {}
      if (a.mode === 'essai' && a.ok) {
        const j = Math.ceil(a.jours_restants || 0);
        el.textContent = `Essai gratuit : ${j} jour(s) restant(s), puis une clé`
                       + ` sera nécessaire`;
        el.style.color = j <= 3 ? 'var(--danger)' : 'var(--dim)';
      } else if (a.mode === 'expire') {
        el.textContent = 'Essai terminé : colle une clé pour continuer à lire';
        el.style.color = 'var(--danger)';
      } else if (a.mode === 'libre') {
        el.textContent = 'Version libre, aucune clé requise';
        el.style.color = 'var(--dim)';
      } else {
        el.textContent = r.raison === 'aucune clé' ? 'Aucune clé sur cette machine'
                                                   : r.raison;
        el.style.color = 'var(--dim)';
      }
    } else {
      el.textContent = r.raison || 'clé refusée';
      el.style.color = 'var(--danger)';
    }
  } catch (e) { el.textContent = ''; }
}

if ($('cleactiver')) {
  $('cleactiver').addEventListener('click', async () => {
    const el = $('cleetat');
    el.textContent = 'vérification…'; el.style.color = 'var(--dim)';
    const r = await poste('/api/licence/activer',
                          {serveur: ($('cleserveur').value || '').trim(),
                           cle: ($('cle').value || '').trim()});
    if (r && r.ok) {
      $('cle').value = '';
      await relisCle();
    } else {
      el.textContent = (r && r.raison) || 'refusée';
      el.style.color = 'var(--danger)';
    }
  });
}
if ($('cleoublier')) {
  $('cleoublier').addEventListener('click', async () => {
    await poste('/api/licence/oublier', {});
    await relisCle();
  });
}

fetch('/api/hotkey').then(r => r.json()).then(d => {
  HOT = d.hotkeys || {}; peinsHot();
}).catch(() => {});
fetch('/api/version').then(r => r.json()).then(d => {
  const t = document.querySelector('h1');
  if (t && d.version) t.textContent = `${d.nom} ${d.version}`;
}).catch(() => {});
if (location.hash === '#cle') {
  requestAnimationFrame(() => {
    const champ = $('cle');
    if (!champ) return;
    champ.scrollIntoView({block: 'center'});
    champ.focus();
    champ.style.transition = 'box-shadow .4s';
    champ.style.boxShadow = '0 0 0 3px var(--accent)';
    setTimeout(() => { champ.style.boxShadow = ''; }, 1800);
  });
}

relis();
relisCompte();
relisCle();
relisContributions();
setInterval(relis, 2000);

function bugDit(txt, bon) {
  const e = $('bugetat');
  if (!e) return;
  e.textContent = txt || '';
  e.style.color = bon === undefined ? '' : (bon ? 'var(--ok, #4ade80)' : 'var(--err, #f87171)');
}

async function bugApercu() {
  const av = $('bugjournal') && $('bugjournal').checked;
  const r = await fetch('/api/signalement/apercu?journal=' + (av ? '1' : '0'))
    .then(x => x.json()).catch(() => ({ok: false, raison: 'app injoignable'}));
  if (!r.ok) return "impossible de préparer l'aperçu : " + (r.raison || '?');
  const lignes = ['ce qui accompagne ton message :'];
  for (const [k, v] of Object.entries(r.contexte || {})) lignes.push(k + ' : ' + v);
  if (r.journal) lignes.push('', 'journal technique :', r.journal);
  else lignes.push('', '(journal non joint)');
  return lignes.join('\n');
}

if ($('bugvoir')) {
  $('bugvoir').addEventListener('click', async () => {
    const p = $('bugapercu');
    if (!p.hidden) { p.hidden = true; $('bugvoir').textContent = 'Voir ce qui sera envoyé'; return; }
    p.textContent = 'un instant…';
    p.hidden = false;
    $('bugvoir').textContent = 'Masquer';
    p.textContent = await bugApercu();
  });
}
if ($('bugjournal')) {
  $('bugjournal').addEventListener('change', async () => {
    const p = $('bugapercu');
    if (p && !p.hidden) p.textContent = await bugApercu();
  });
}
if ($('bugenvoi')) {
  $('bugenvoi').addEventListener('click', async () => {
    const t = $('bugtexte');
    const msg = (t.value || '').trim();
    if (msg.length < 3) {
      bugDit('écris ce qui se passe, même en une ligne', false);
      t.focus();
      return;
    }
    const b = $('bugenvoi');
    b.disabled = true;
    bugDit('envoi…');
    const r = await poste('/api/signalement', {
      message: msg,
      journal: !!($('bugjournal') && $('bugjournal').checked),
    }).catch(() => ({ok: false, raison: 'app injoignable'}));
    b.disabled = false;
    if (r && r.ok) {
      bugDit('reçu, merci', true);
      t.value = '';
      if ($('bugapercu')) $('bugapercu').hidden = true;
      if ($('bugvoir')) $('bugvoir').textContent = 'Voir ce qui sera envoyé';
    } else {
      bugDit((r && r.raison) || "l'envoi n'est pas passé", false);
    }
  });
}
