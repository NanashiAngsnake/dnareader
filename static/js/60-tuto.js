const TUTO_VU = 'dnareader_tuto_vu_v3';
let tutoPas = 0;
let tutoHauteurAvant = 0;

const TUTO_ETAPES = [
  {
    cible: null, titre: 'Bienvenue dans DNAreader',
    texte: `DNAreader lit le japonais affiché à l'écran et donne le sens de chaque mot, `
         + `sans toucher au jeu.<br><br>Ce tour dure une minute. Il couvre les deux choses `
         + `qui ne se devinent pas : le mode bulle, et les jeux où le texte défile seul.`
  },
  {
    cible: 'bjeu', titre: '1 · Choisis ton jeu', panneau: false,
    texte: `Choisis ici la fenêtre du jeu. Seule celle-là est lue.<br><br>`
         + `<b>Dans les options du jeu, mets « fenêtré sans bordure »</b> `
         + `(<i>borderless</i>) plutôt que « plein écran ». En plein écran exclusif, `
         + `le jeu prend l'écran pour lui seul : DNAreader ne peut ni le lire ni poser `
         + `la bulle par-dessus, et c'est une limite de Windows, pas un réglage à `
         + `trouver. Sans bordure, l'image est identique et tout fonctionne.<br><br>`
         + `Le jeu doit être lancé pour apparaître dans la liste. Il doit aussi rester `
         + `VISIBLE : DNAreader lit la zone d'écran où il se trouve, donc une fenêtre posée `
         + `devant lui serait lue à sa place.`
  },
  {
    cible: 'bnext', titre: '2 · Le mode bulle', panneau: false,
    texte: `C'est le seul affichage de DNAreader : une petite bulle se pose à côté de la `
         + `phrase, dans le jeu, et ne montre qu'une ligne à la fois.<br><br>`
         + `Ces flèches, <kbd>←</kbd> et <kbd>→</kbd>, ou la molette, passent d'une ligne `
         + `à l'autre. Survole un mot : sa définition s'affiche, et le bouton + l'ajoute à `
         + `ton vocabulaire.`
  },
  {
    cible: 'bgear', titre: '3 · Les réglages rapides', panneau: true,
    texte: `L'engrenage ouvre ce panneau sans quitter la bulle : transparence quand l'app `
         + `attend du texte, taille du texte, gel automatique, et les touches.<br><br>`
         + `Quand il y a du texte à lire, la bulle reste opaque : le japonais posé sur `
         + `une image de jeu se déchiffre mal en transparence.`
  },
  {
    cible: 'bzone', titre: '4 · Délimite le texte (à faire en premier)', panneau: true,
    texte: `Trace un rectangle autour de la zone où le jeu affiche ses dialogues.<br><br>`
         + `<b>C'est le réglage qui change le plus la précision</b>, et c'est pour ça `
         + `qu'il est tout en haut du panneau. Les compteurs de vie, les icônes et les `
         + `noms de menus cessent d'être lus, la lecture devient plus rapide, et la bulle `
         + `arrête de se poser sur des bouts d'interface.<br><br>`
         + `<b>Et la bulle ne se posera plus jamais dessus.</b> Tant qu'aucune zone `
         + `n'est tracée, elle se colle à la ligne qu'elle vient de lire — donc `
         + `souvent en plein sur la réplique suivante. Une fois la zone connue, `
         + `elle s'écarte toute seule au-dessus ou à côté.<br><br>`
         + `La zone est retenue pour CE jeu : à faire une seule fois.`
  },
  {
    cible: 'bengine', titre: '5 · Le moteur de lecture', panneau: true,
    texte: `<b>Rapide (Windows)</b> lit avec le moteur du système : instantané, et `
         + `suffisant sur du texte net.<br><br>`
         + `<b>DNAreader (embarqué)</b> est notre propre modèle, entraîné pour les `
         + `polices de jeu. Il relit les lignes douteuses en quelques millisecondes et `
         + `se trompe moins souvent sur les kanji serrés.<br><br>`
         + `Dans les deux cas, un second lecteur japonais corrige déjà les lignes `
         + `douteuses au passage : tu n'as rien à activer pour en profiter.<br><br>`
         + `Change de moteur si tu vois des erreurs, pas avant.`
  },
  {
    cible: 'bafbtn', titre: '6 · Les deux types de jeu', panneau: true,
    texte: `Si tu fais défiler le texte toi-même (RPG au tour par tour, visual novels), `
         + `la phrase t'attend et il n'y a rien à faire.<br><br>`
         + `Si le texte défile seul (cinématiques, gros titres), la réplique disparaît avant `
         + `que tu aies fini de lire. Gèle alors le jeu entre chaque phrase avec la touche `
         + `<kbd id="tutofreeze">F11</kbd>, ou active ici le gel automatique, qui met en `
         + `pause à chaque nouvelle phrase.<br><br>`
         + `Cette touche se change juste en dessous.`
  },
  {
    cible: 'bfenetre', titre: '7 · Le mode fenêtre, et comment il marche', panneau: true,
    faire: {libelle: 'Ouvre-le pour voir',
            action: () => tutoOuvreLaFenetre()},
    texte: `<b>La bulle</b>, celle que tu vois, se pose SUR le jeu et montre une ligne à `
         + `la fois. Elle lit en continu, toute seule. C'est le mode normal.<br><br>`
         + `<b>Le mode fenêtre</b> est autre chose : une vraie fenêtre, à côté du jeu, qui `
         + `ne lit QUE quand tu le demandes. Elle demande donc beaucoup moins à la `
         + `machine : à choisir sur un PC modeste, où la lecture en continu peut faire `
         + `perdre des images au jeu.<br><br>`
         + `<b>Comment on s'en sert :</b><br>`
         + `• <b>Capturer</b>, ou <kbd id="tutocap">F8</kbd> sans quitter le jeu, prend une `
         + `image de la fenêtre choisie.<br>`
         + `• L'image s'affiche dans la fenêtre, et <b>tout</b> le texte trouvé est listé `
         + `dessous, pas une ligne à la fois.<br>`
         + `• Survole un mot, sur l'image ou dans la liste : la définition s'affiche comme `
         + `dans la bulle, et le bouton + l'ajoute à ton vocabulaire.<br>`
         + `• <kbd>Ctrl</kbd>+<kbd>V</kbd> lit une capture d'écran collée depuis le `
         + `presse-papiers, même si elle ne vient pas d'un jeu.<br>`
         + `• Coche <b>auto</b> pour qu'elle recapture toute seule toutes les N secondes.<br><br>`
         + `Pour revenir, le bouton <b>Bulle</b> en haut, ou la croix de la fenêtre, qui `
         + `ramène aussi à la bulle sans fermer l'application.`
  },
  {
    cible: 'bsetplus', titre: '8 · Plus d’options', panneau: true,
    texte: `Ouvre une fenêtre à part avec tout le reste : la traduction en français, `
         + `le détail des raccourcis, ton compte pour retrouver ton vocabulaire sur une `
         + `autre machine, et la langue de l'interface.<br><br>`
         + `Le bouton juste à côté rejoue cette visite quand tu veux.`
  },
  {
    cible: 'bquit', titre: '9 · C\'est tout', panneau: false,
    texte: `Cette croix ferme l'application ; celle du haut la met simplement de côté.<br><br>`
         + `Tu peux relancer cette visite à tout moment depuis les réglages.<br><br>`
         + `<b>Bonne lecture !</b>`
  },
];

function tutoCible(pas) {
  const e = TUTO_ETAPES[pas];
  return e && e.cible ? $(e.cible) : null;
}

async function tutoPlace() {
  if (typeof ajusteFenetreAuContenu === 'function') {
    await ajusteFenetreAuContenu();
  }
}

function tutoRedimensionne() {
  if (!document.body.classList.contains('en-visite')) return;
  tutoPoseCarte();
  const ask = $('tutoask').classList.contains('show');
  const carte = ask ? $('tutoaskcarte') : $('tutocarte');
  tutoPlace();
}

function tutoLargeurVoulue(carte) {
  const bar = $('bar').getBoundingClientRect();
  let bouts = 0;
  for (const e of $('bar').children) {
    const st = getComputedStyle(e);
    if (st.position === 'absolute' || st.position === 'fixed') continue;
    if (st.display === 'none') continue;
    const r = e.getBoundingClientRect();
    if (r.width) bouts = Math.max(bouts, r.right - bar.left);
  }
  return Math.ceil(Math.max(bouts, carte || 0) + 30);
}

function tutoPoseCarte() {
  const r = $('bar').getBoundingClientRect();
  const y = Math.max(0, Math.round(r.bottom)) + 6;
  $('tuto').style.top = y + 'px';
  $('tutoask').style.top = y + 'px';
  const r2 = $('recolteask');
  if (r2) r2.style.top = y + 'px';
}

function tutoAffiche() {
  const e = TUTO_ETAPES[tutoPas];
  if (!e) return tutoFin();

  const bset = $('bset');
  if (bset) {
    const ouvert = bset.classList.contains('show');
    if (e.panneau === true && !ouvert) toggleBset();
    if (e.panneau === false && ouvert) toggleBset();
  }

  $('tutotitre').innerHTML = e.titre;
  $('tutotexte').innerHTML = e.texte;

  const faire = $('tutofaire');
  if (faire) {
    faire.hidden = !e.faire;
    faire.textContent = e.faire ? e.faire.libelle : '';
  }
  $('tutopas').textContent = `${tutoPas + 1} / ${TUTO_ETAPES.length}`;
  $('tutoprev').style.visibility = tutoPas ? 'visible' : 'hidden';
  $('tutonext').textContent = tutoPas === TUTO_ETAPES.length - 1 ? 'Terminer' : 'Suivant';

  for (const [id, nom] of [['tutofreeze', 'freeze'], ['tutocap', 'capture']]) {
    const k = $(id);
    if (k && typeof HOTKEYS === 'object' && HOTKEYS[nom]) {
      k.textContent = HOTKEYS[nom].toUpperCase();
    }
  }

  requestAnimationFrame(() => {
    tutoPoseCarte();
    tutoPlace();
    const halo = $('tutohalo');
    const cible = tutoCible(tutoPas);
    if (!cible) { halo.style.display = 'none'; return; }
    const r = cible.getBoundingClientRect();
    if (!r.width) { halo.style.display = 'none'; return; }
    halo.style.display = 'block';
    halo.style.left = (r.left - 6) + 'px';
    halo.style.top = (r.top - 6) + 'px';
    halo.style.width = (r.width + 12) + 'px';
    halo.style.height = (r.height + 12) + 'px';
  });
}

const TUTO_REPRISE = 'dnareader_tuto_reprise';

function tutoOuvreLaFenetre() {
  try { localStorage.setItem(TUTO_REPRISE, String(tutoPas + 1)); } catch (e) {}
  const pv = window.pywebview && window.pywebview.api;
  if (pv && typeof pv.set_mode === 'function') {
    $('tuto').classList.remove('show');
    document.body.classList.remove('en-visite');
    pv.set_mode('window', (typeof gameTitle !== 'undefined' && gameTitle) || null);
  } else {
    setStatus('(mode navigateur : la vue fenêtre est la page /)');
  }
}

function tutoReprendPeutEtre() {
  let n;
  try { n = parseInt(localStorage.getItem(TUTO_REPRISE) || '', 10); } catch (e) { return false; }
  if (!Number.isFinite(n) || n < 0) return false;
  try { localStorage.removeItem(TUTO_REPRISE); } catch (e) {}
  if (n >= TUTO_ETAPES.length) return false;
  if (typeof GHOST !== 'undefined' && GHOST) { GHOST = false; applyGhost(true); }
  document.body.classList.add('en-visite');
  if (typeof applyOpacity === 'function') applyOpacity(false);
  tutoHauteurAvant = window.innerHeight;
  tutoPas = n;
  $('tutoask').classList.remove('show');
  $('tuto').classList.add('show');
  tutoAffiche();
  return true;
}

async function tutoDemarre() {
  if (typeof BULLE !== 'undefined' && !BULLE) { BULLE = true; applyBulle(); }
  if (typeof GHOST !== 'undefined' && GHOST) { GHOST = false; applyGhost(true); }
  $('tutoask').classList.remove('show');
  document.body.classList.add('en-visite');
  tutoHauteurAvant = window.innerHeight;
  tutoPas = 0;
  document.body.classList.add('en-visite');
  if (typeof applyOpacity === 'function') applyOpacity(false);
  $('tuto').classList.add('show');
  tutoAffiche();
}

async function tutoFin() {
  document.body.classList.remove('en-visite');
  $('tuto').classList.remove('show');
  $('tutoask').classList.remove('show');
  $('tutohalo').style.display = 'none';
  localStorage.setItem(TUTO_VU, '1');
  if (tutoHauteurAvant) await tutoPlace();
  if (typeof BULLE !== 'undefined') {
    BULLE = true;
    applyBulle();
    if (typeof ajusteFenetreAuContenu === 'function') {
      requestAnimationFrame(() => requestAnimationFrame(ajusteFenetreAuContenu));
    }
    recolteDemandePeutEtre();
    return;
  }
  setStatus('Visite terminée. Relançable depuis les réglages.');
  recolteDemandePeutEtre();
}

function tutoSuivant(pas) {
  const n = tutoPas + pas;
  if (n < 0) return;
  if (n >= TUTO_ETAPES.length) return tutoFin();
  tutoPas = n;
  tutoAffiche();
}

$('tutofaire').addEventListener('click', () => {
  const e = TUTO_ETAPES[tutoPas];
  if (e && e.faire) e.faire.action();
});
$('tutonext').addEventListener('click', () => tutoSuivant(+1));
$('tutoprev').addEventListener('click', () => tutoSuivant(-1));
$('tutoskip').addEventListener('click', tutoFin);
$('tutooui').addEventListener('click', tutoDemarre);
$('tutonon').addEventListener('click', () => {
  $('tutoask').classList.remove('show');
  document.body.classList.remove('en-visite');
  localStorage.setItem(TUTO_VU, '1');
  if (typeof BULLE !== 'undefined') { applyBulle(); recolteDemandePeutEtre(); return; }
  setStatus('Visite passée. Elle reste dans les réglages.');
  recolteDemandePeutEtre();
});

const RECOLTE_DEMANDEE = 'dnareader_recolte_demandee_v1';

const RECOLTE_ASK_FR =
  `DNAreader se trompe encore sur les polices de jeu. Il peut apprendre des `
  + `tiennes : quand ses deux moteurs lisent une ligne <b>exactement pareil</b>, `
  + `la lecture est sûre, et cette ligne entraîne le lecteur que tout le monde `
  + `reçoit à la mise à jour suivante.<br><br>`
  + `<b>Ce qui part :</b> la bande découpée autour de la ligne (quelques Ko), le `
  + `texte lu, et le nom du jeu.<br>`
  + `<b>Ce qui ne part pas :</b> aucune capture d'écran, aucun ordre des `
  + `répliques, rien de ta machine ni de ton compte de jeu.<br><br>`
  + `Réglable à tout moment dans les réglages, ligne <b>Aider le lecteur</b>.`;

function recolteDemandePeutEtre() {
  if (localStorage.getItem(RECOLTE_DEMANDEE) === '1') return false;
  const c = $('recolteask');
  if (!c) return false;
  $('recolteasktexte').innerHTML = t('recolteask.texte', RECOLTE_ASK_FR);
  document.body.classList.add('en-visite');
  if (typeof applyOpacity === 'function') applyOpacity(false);
  tutoPoseCarte();
  c.classList.add('show');
  tutoPoseCarte();
  requestAnimationFrame(() => requestAnimationFrame(() => {
    tutoPoseCarte();
    tutoPlace();
  }));
  return true;
}

async function recolteRepond(oui) {
  localStorage.setItem(RECOLTE_DEMANDEE, '1');
  $('recolteask').classList.remove('show');
  document.body.classList.remove('en-visite');
  try {
    await fetch('/api/recolte', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({actif: !!oui})
    });
  } catch (e) {  }
  if (typeof BULLE !== 'undefined') { applyBulle(); }
  if (typeof ajusteFenetreAuContenu === 'function') {
    requestAnimationFrame(() => requestAnimationFrame(ajusteFenetreAuContenu));
  }
  if (typeof setStatus === 'function') {
    setStatus(oui ? t('recolte.marche', 'Merci ! Joue normalement.')
                  : t('recolte.arret', 'Rien ne sera envoyé.'));
  }
}

$('recolteoui').addEventListener('click', () => recolteRepond(true));
$('recoltenon').addEventListener('click', () => recolteRepond(false));

document.addEventListener('keydown', ev => {
  if (!$('tuto').classList.contains('show')) return;
  if (ev.key === 'ArrowRight') { ev.preventDefault(); tutoSuivant(+1); }
  else if (ev.key === 'ArrowLeft') { ev.preventDefault(); tutoSuivant(-1); }
  else if (ev.key === 'Escape') { ev.preventDefault(); tutoFin(); }
});

const TUTO_H_MIN = 330;

function tutoProposePeutEtre() {
  if (tutoReprendPeutEtre()) return;
  if (localStorage.getItem(TUTO_VU) === '1') return;
  document.body.classList.add('en-visite');
  if (typeof applyOpacity === 'function') applyOpacity(false);
  tutoPoseCarte();
  $('tutoask').classList.add('show');
  tutoPoseCarte();
  requestAnimationFrame(() => requestAnimationFrame(() => {
    tutoPoseCarte();
    tutoPlace();
  }));
}
