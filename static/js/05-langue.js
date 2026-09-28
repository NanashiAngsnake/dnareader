const LANGUES = {fr: 'Français', en: 'English', es: 'Español',
                 de: 'Deutsch', pt: 'Português'};

const TEXTES = {
  en: {
    'jeu.choisir': 'Game to read',
    'bulle.jeu': 'Game window to read',
    'bulle.deplacer': 'Drag to move the bubble',
    'bulle.fenetre': 'Window',
    'bulle.fenetre.t': 'Switch to window mode, beside the game',
    'bulle.fermer': 'Close DNAreader',
    'bulle.precedent': 'Previous line',
    'bulle.suivant': 'Next line',
    'bulle.reglages': 'Quick settings. Right-click for all settings',
    'lbl.zone': 'Area read', 'lbl.affichage': 'Display',
    'lbl.recolte': 'Help the reader',
    'recolte.compte': '{0} lines kept · {1} sent',
    'recolte.attente': 'waiting for text...',
    'recolte.aide': 'sends the lines both engines agree on, to train the reader',
    'recolte.arret': 'Stopped. Nothing is sent any more.',
    'recolte.marche': 'Thanks! Just play normally.',
    'recolte.envoi': '{0} lines sent to train the shared reader',
    'recolteask.titre': 'Help improve reading?',
    'recolteask.texte': 'DNAreader still gets game fonts wrong. It can learn from '
      + 'yours: when its two engines read a line <b>exactly the same</b>, that '
      + 'reading is certain, and the line trains the reader everyone gets in the '
      + 'next update.<br><br><b>What is sent:</b> the strip cropped around the '
      + 'line (a few KB), the text read, and the game name.<br><b>What is not '
      + 'sent:</b> no screenshot, no ordering of the lines, nothing from your '
      + 'machine or your game account.<br><br>You can change this any time in '
      + 'the settings, on the <b>Help the reader</b> row.',
    'recolteask.oui': 'Yes, count me in',
    'recolteask.non': 'No thanks',
    'lbl.appris': 'Missed text',
    'lbl.moteur': 'Engine',
    'bulle.moteur.rapide': 'Fast (Windows)',
    'bulle.moteur.precis': 'High accuracy (AI)',
    'moteur.rapide.aide': 'instant',
    'moteur.precis.aide': 'more accurate, slower',
    'bulle.apprend': 'Draw around the text…',
    'bulle.tout': 'More options',
    'bulle.revoirvisite': 'Replay the tour',
    'lbl.cequiestecrit': 'It reads',
    'bulle.apprendok': 'Remember',
    'bulle.apprendok.t': 'Leave the field empty to forget this spot',
    'bulle.annuler': 'Cancel',
    'lbl.lecture': 'Reading', 'lbl.couleur': 'Colour',
    'bulle.pause': 'Pause reading',
    'bulle.reprendre': 'Resume reading',
    'etat.enpause': 'Reading paused. {0} to resume.',
    'etat.enpause.court': 'nothing will show',
    'etat.reprise': 'Reading resumed.',
    'etat.couleur': 'Colour: {0}',
    'etat.partage.tire': '{0} correction(s) from the community for this game',
    'etat.essai.reste': 'Free trial: {0} day(s) left',
    'etat.essai.fini': 'Trial over. Settings > Access key.',
    'bulle.zone.tout': 'Whole screen',
    'zone.tout': 'the whole screen is read',
    'zone.minuscule': '{0} — only {1} % of the screen, everything else is ignored',
    'etat.zone.tout': 'The whole game window is read.',
    'etat.zone.minuscule': 'Area covering {0} % of the screen: EVERYTHING else '
                         + 'is ignored. Use « Whole screen » to remove it.',
    'reg.sect.cle': 'Access key',
    'reg.cle': 'Key', 'reg.cle.serveur': 'Server',
    'reg.cle.activer': 'Activate',
    'reg.cle.oublier': 'Remove from this machine',
    'reg.cle.aide': 'The key is checked online at launch, then works without a '
                  + 'network for two weeks. It covers a limited number of machines.',
    'lbl.opacite': 'Transparency', 'lbl.opacitelec': '… while reading',
    'aide.opacitelec': 'The bubble while it shows text. 100 % by default: Japanese '
      + 'over a moving game background is hard to make out when see-through. '
      + 'Lower it if you want to keep an eye on what is happening behind.',
    'lbl.texte': 'Text', 'lbl.gelauto': 'Auto-pause',
    'aide.opacite': 'Applies while the app waits for text. As soon as there is a '
      + 'line to read it turns opaque again: transparent Japanese over a game '
      + 'background cannot be made out.',
    'lbl.touches': 'Keys', 'lbl.tout': 'Settings', 'lbl.jeu': 'Game',
    'gelauto.chaque': 'on every line',
    'touche.geler': 'pause game', 'touche.bulle': 'bubble mode',
    'touche.clics': 'clicks to game', 'touche.masquer': 'hide',
    'touche.lire': 'read', 'touche.zone': 'area', 'touche.quitter': 'quit',
    'hk.aide': 'click a key then press the one you want · ← → change line',
    'reg.titre': 'Settings',
    'reg.aucunjeu': 'no game selected',
    'reg.sect.jeu': 'Game',
    'reg.fenetrelue': 'Window read',
    'reg.actualiser': 'Refresh',
    'reg.jeu.aide': 'The game must be running to appear in the list.',
    'reg.zone': 'Text area', 'reg.zone.def': 'Set the area',
    'reg.zone.tout': 'whole screen',
    'reg.zone.aide': 'Optional. Limits reading to the dialogue band: faster, and '
                   + 'the rest of the interface is no longer read.',
    'reg.lire': 'Read now', 'reg.lire.btn': 'Read the screen',
    'reg.lire.aide': 'The shortcut does the same without leaving the game.',
    'reg.sect.mode': 'Display mode', 'reg.affichage': 'Display',
    'reg.mode.bulle': 'Bubble on the game', 'reg.mode.fen': 'Window beside',
    'reg.mode.aide': 'The bubble sits on the game and shows one line at a time. '
                   + 'The window shows everything beside the game and asks far less '
                   + 'of the machine: choose it on a low-end PC.',
    'reg.sect.lecture': 'Reading', 'reg.moteur': 'Engine',
    'reg.moteur.rapide': 'Fast', 'reg.moteur.precis': 'High precision',
    'reg.moteur.aide': 'High precision re-reads every line with a stronger model. '
                     + 'Turn it on if you see mistakes. Text appears slightly slower.',
    'reg.contraste': 'Contrast', 'reg.contraste.auto': 'Automatic',
    'reg.contraste.aucun': 'None', 'reg.contraste.clair': 'Light text on dark',
    'reg.contraste.sombre': 'Dark text on light',
    'reg.contraste.aide': 'Only touch this if reading fails on a game with an '
                        + 'unusual look.',
    'reg.flux': 'Continuous reading',
    'reg.flux.aide': 'Windows tells the app when the game image changes. On a '
                   + 'low-end machine, turning it off eases the game.',
    'reg.sect.affichage': 'Display', 'reg.opacite': 'Transparency — idle',
    'reg.opacitelec': 'Transparency — while reading',
    'reg.taille': 'Text size', 'reg.surlignage': 'Highlight in game',
    'reg.surlignage.aide': 'Puts a halo on the hovered word, inside the game image.',
    'reg.traduction': 'Translation',
    'reg.trad.aucune': 'Reading only (no translation)',
    'reg.trad.fr': 'Translate to French',
    'reg.trad.aide': 'Local translation downloads 2.5 GB on first use.',
    'reg.sect.auto': 'Games where text advances by itself',
    'reg.auto.aide': 'In cutscenes the line leaves before you have finished '
                   + 'reading. Pausing holds the game for the length of the line.',
    'reg.gelauto': 'Auto-pause',
    'reg.gelauto.aide': 'Pauses the game on every new line.',
    'reg.touchegel': 'Pause key', 'reg.changer': 'Pause game',
    'reg.touchegel.aide': 'Click, then press the key you want.',
    'reg.sect.raccourcis': 'Shortcuts',
    'reg.hk.aide': 'Click a shortcut then press the key you want (Esc to cancel).',
    'reg.sect.compte': 'Account',
    'reg.compte.aide': 'Find your work on another PC.',
    'reg.sync.aide': 'Synchronised: vocabulary, per-game profiles and corrections. '
                   + 'The file works without an account or a server. The account does '
                   + 'the same automatically.',
    'reg.fichier': 'File', 'reg.exporter': 'Export…', 'reg.importer': 'Import…',
    'reg.serveur': 'Server',
    'reg.serveur.aide': 'Address of a sync server. The bundled serveur_sync.py '
                      + 'runs wherever you want. Your password never arrives in clear.',
    'reg.identifiant': 'Username', 'reg.motdepasse': 'Password',
    'reg.connexion': 'Sign in', 'reg.inscription': 'Create account',
    'reg.synchroniser': 'Synchronise', 'reg.deconnexion': 'Sign out',
    'reg.sect.aide': 'Help', 'reg.visite': 'Guided tour',
    'reg.visite.btn': 'Replay the tour',
    'reg.visite.aide': 'The buttons, the two kinds of game, pausing, the bubble.',
    'reg.langue': 'Language',
    'reg.langue.aide': 'Applies to the whole interface, immediately.',
    'reg.pret': 'Ready.',
    'etat.actif': 'On', 'etat.inactif': 'Off',
    'etat.activee': 'On', 'etat.desactivee': 'Off',
    'etat.choisirjeu': 'Choose the game to read.',
    'etat.enveille': 'Waiting for text…',
    'etat.repos': 'The bubble will wait here.',
    'etat.enbulle': 'Arrows or wheel to change line.',
    'etat.couvert': 'The game is behind « {0} »',
    'etat.pleinecran': 'Game in fullscreen: switch to borderless windowed',
    'bulle.nom': 'Bubble', 'bulle.active': 'Bubble active',
    'reg.nonconnecte': 'Not signed in',
  },
  es: {
    'jeu.choisir': 'Juego a leer',
    'bulle.jeu': 'Ventana del juego a leer',
    'bulle.deplacer': 'Arrastra para mover la burbuja',
    'bulle.fenetre': 'Ventana',
    'bulle.fenetre.t': 'Cambiar al modo ventana, al lado del juego',
    'bulle.fermer': 'Cerrar DNAreader',
    'bulle.precedent': 'Línea anterior', 'bulle.suivant': 'Línea siguiente',
    'bulle.reglages': 'Ajustes rápidos. Clic derecho para todos los ajustes',
    'lbl.zone': 'Zona leida', 'lbl.affichage': 'Vista',
    'lbl.recolte': 'Ayudar al lector',
    'recolte.compte': '{0} lineas guardadas · {1} enviadas',
    'recolte.attente': 'esperando texto...',
    'recolte.aide': 'envia las lineas en que ambos motores coinciden',
    'recolte.arret': 'Detenido. Ya no se envia nada.',
    'recolte.marche': 'Gracias. Juega normalmente.',
    'recolte.envoi': '{0} lineas enviadas para entrenar el lector comun',
    'recolteask.titre': '¿Ayudar a mejorar la lectura?',
    'recolteask.texte': 'DNAreader todavia falla con las tipografias de los juegos. '
      + 'Puede aprender de las tuyas: cuando sus dos motores leen una linea '
      + '<b>exactamente igual</b>, la lectura es segura y esa linea entrena al '
      + 'lector que todos reciben en la siguiente actualizacion.<br><br>'
      + '<b>Lo que se envia:</b> la banda recortada alrededor de la linea (unos '
      + 'pocos KB), el texto leido y el nombre del juego.<br><b>Lo que no se '
      + 'envia:</b> ninguna captura de pantalla, ningun orden de las frases, nada '
      + 'de tu equipo ni de tu cuenta de juego.<br><br>Puedes cambiarlo cuando '
      + 'quieras en los ajustes, en la fila <b>Ayudar al lector</b>.',
    'recolteask.oui': 'Si, ayudo',
    'recolteask.non': 'No, gracias',
    'lbl.appris': 'Texto no visto',
    'lbl.moteur': 'Motor',
    'bulle.moteur.rapide': 'Rapido (Windows)',
    'bulle.moteur.precis': 'Alta precision (IA)',
    'moteur.rapide.aide': 'instantaneo',
    'moteur.precis.aide': 'mas exacto, mas lento',
    'bulle.apprend': 'Rodear el texto…',
    'bulle.tout': 'Mas opciones',
    'bulle.revoirvisite': 'Repetir la visita',
    'lbl.cequiestecrit': 'Pone',
    'bulle.apprendok': 'Recordar',
    'bulle.apprendok.t': 'Deja el campo vacio para olvidar este sitio',
    'bulle.annuler': 'Cancelar',
    'lbl.lecture': 'Lectura', 'lbl.couleur': 'Color',
    'bulle.pause': 'Pausar la lectura',
    'bulle.reprendre': 'Reanudar la lectura',
    'etat.enpause': 'Lectura en pausa. {0} para reanudar.',
    'etat.enpause.court': 'no se mostrara nada',
    'etat.reprise': 'Lectura reanudada.',
    'etat.couleur': 'Color: {0}',
    'etat.partage.tire': '{0} correccion(es) de la comunidad para este juego',
    'etat.essai.reste': 'Prueba gratuita: {0} dia(s) restante(s)',
    'etat.essai.fini': 'Prueba terminada. Ajustes > Clave de acceso.',
    'bulle.zone.tout': 'Toda la pantalla',
    'zone.tout': 'se lee toda la pantalla',
    'zone.minuscule': '{0} — solo {1} % de la pantalla, todo lo demas se ignora',
    'etat.zone.tout': 'Se lee toda la ventana del juego.',
    'etat.zone.minuscule': 'Zona de {0} % de la pantalla: TODO lo demas se '
                         + 'ignora. « Toda la pantalla » para quitarla.',
    'reg.sect.cle': 'Clave de acceso',
    'reg.cle': 'Clave', 'reg.cle.serveur': 'Servidor',
    'reg.cle.activer': 'Activar',
    'reg.cle.oublier': 'Quitar de esta maquina',
    'reg.cle.aide': 'La clave se verifica en linea al arrancar, luego funciona '
                  + 'sin red durante dos semanas. Vale para un numero limitado '
                  + 'de maquinas.',
    'lbl.opacite': 'Transparencia', 'lbl.opacitelec': '… al leer',
    'aide.opacitelec': 'La burbuja cuando muestra texto. 100 % por defecto: el '
      + 'japones sobre un fondo de juego en movimiento se descifra mal en '
      + 'transparencia. Bajalo si quieres ver lo que pasa detras.',
    'lbl.texte': 'Texto', 'lbl.gelauto': 'Pausa auto',
    'aide.opacite': 'Se aplica mientras la app espera texto. En cuanto hay una '
      + 'linea que leer vuelve a ser opaca: el japones transparente sobre un '
      + 'fondo de juego no se descifra.',
    'lbl.touches': 'Teclas', 'lbl.tout': 'Ajustes', 'lbl.jeu': 'Juego',
    'gelauto.chaque': 'en cada línea',
    'touche.geler': 'pausar el juego', 'touche.bulle': 'modo burbuja',
    'touche.clics': 'clics al juego', 'touche.masquer': 'ocultar',
    'touche.lire': 'leer', 'touche.zone': 'zona', 'touche.quitter': 'salir',
    'hk.aide': 'pulsa una tecla y luego la que quieras · ← → cambian de línea',
    'reg.titre': 'Ajustes', 'reg.aucunjeu': 'ningún juego seleccionado',
    'reg.sect.jeu': 'Juego', 'reg.fenetrelue': 'Ventana leída',
    'reg.actualiser': 'Actualizar',
    'reg.jeu.aide': 'El juego debe estar abierto para aparecer en la lista.',
    'reg.zone': 'Zona del texto', 'reg.zone.def': 'Definir la zona',
    'reg.zone.tout': 'toda la pantalla',
    'reg.zone.aide': 'Opcional. Limita la lectura a la banda de diálogo: más '
                   + 'rápido, y el resto de la interfaz ya no se lee.',
    'reg.lire': 'Leer ahora', 'reg.lire.btn': 'Leer la pantalla',
    'reg.lire.aide': 'El atajo hace lo mismo sin salir del juego.',
    'reg.sect.mode': 'Modo de visualización', 'reg.affichage': 'Visualización',
    'reg.mode.bulle': 'Burbuja sobre el juego', 'reg.mode.fen': 'Ventana al lado',
    'reg.mode.aide': 'La burbuja se posa sobre el juego y muestra una línea a la '
                   + 'vez. La ventana lo muestra todo al lado y exige mucho menos '
                   + 'a la máquina: elígela en un PC modesto.',
    'reg.sect.lecture': 'Lectura', 'reg.moteur': 'Motor',
    'reg.moteur.rapide': 'Rápido', 'reg.moteur.precis': 'Alta precisión',
    'reg.moteur.aide': 'La alta precisión relee cada línea con un modelo más '
                     + 'fuerte. Actívala si ves errores. El texto tarda algo más.',
    'reg.contraste': 'Contraste', 'reg.contraste.auto': 'Automático',
    'reg.contraste.aucun': 'Ninguno', 'reg.contraste.clair': 'Texto claro sobre oscuro',
    'reg.contraste.sombre': 'Texto oscuro sobre claro',
    'reg.contraste.aide': 'Tócalo solo si la lectura falla en un juego con un '
                        + 'aspecto inusual.',
    'reg.flux': 'Lectura continua',
    'reg.flux.aide': 'Windows avisa a la app cuando cambia la imagen del juego. '
                   + 'En una máquina modesta, desactivarla alivia el juego.',
    'reg.sect.affichage': 'Visualización', 'reg.opacite': 'Transparencia — en reposo',
    'reg.opacitelec': 'Transparencia — al leer',
    'reg.taille': 'Tamaño del texto', 'reg.surlignage': 'Resaltar en el juego',
    'reg.surlignage.aide': 'Pone un halo sobre la palabra señalada, en la imagen '
                         + 'del juego.',
    'reg.traduction': 'Traducción',
    'reg.trad.aucune': 'Solo lectura (sin traducción)',
    'reg.trad.fr': 'Traducir al francés',
    'reg.trad.aide': 'La traducción local descarga 2,5 GB el primer uso.',
    'reg.sect.auto': 'Juegos donde el texto avanza solo',
    'reg.auto.aide': 'En las cinemáticas la línea desaparece antes de acabar de '
                   + 'leer. La pausa detiene el juego el tiempo de la línea.',
    'reg.gelauto': 'Pausa automática',
    'reg.gelauto.aide': 'Pausa el juego en cada línea nueva.',
    'reg.touchegel': 'Tecla de pausa', 'reg.changer': 'Pausar el juego',
    'reg.touchegel.aide': 'Pulsa, y luego la tecla que quieras.',
    'reg.sect.raccourcis': 'Atajos',
    'reg.hk.aide': 'Pulsa un atajo y luego la tecla que quieras (Esc para anular).',
    'reg.sect.compte': 'Cuenta',
    'reg.compte.aide': 'Recupera tu trabajo en otro PC.',
    'reg.sync.aide': 'Se sincronizan: vocabulario, perfiles por juego y '
                   + 'correcciones. El archivo funciona sin cuenta ni servidor. La '
                   + 'cuenta hace lo mismo automáticamente.',
    'reg.fichier': 'Archivo', 'reg.exporter': 'Exportar…', 'reg.importer': 'Importar…',
    'reg.serveur': 'Servidor',
    'reg.serveur.aide': 'Dirección de un servidor de sincronización. El '
                      + 'serveur_sync.py incluido se aloja donde quieras. Tu '
                      + 'contraseña nunca llega en claro.',
    'reg.identifiant': 'Usuario', 'reg.motdepasse': 'Contraseña',
    'reg.connexion': 'Entrar', 'reg.inscription': 'Crear cuenta',
    'reg.synchroniser': 'Sincronizar', 'reg.deconnexion': 'Salir',
    'reg.sect.aide': 'Ayuda', 'reg.visite': 'Visita guiada',
    'reg.visite.btn': 'Repetir la visita',
    'reg.visite.aide': 'Los botones, los dos tipos de juego, la pausa, la burbuja.',
    'reg.langue': 'Idioma',
    'reg.langue.aide': 'Se aplica a toda la interfaz, de inmediato.',
    'reg.pret': 'Listo.', 'reg.nonconnecte': 'Sin conexión',
    'etat.actif': 'Activado', 'etat.inactif': 'Desactivado',
    'etat.activee': 'Activada', 'etat.desactivee': 'Desactivada',
    'etat.choisirjeu': 'Elige el juego a leer.',
    'etat.enveille': 'Esperando texto…',
    'etat.repos': 'La burbuja esperará aquí.',
    'etat.enbulle': 'Flechas o rueda para cambiar de línea.',
    'etat.couvert': 'El juego está detrás de « {0} »',
    'etat.pleinecran': 'Juego en pantalla completa: usa ventana sin bordes',
    'bulle.nom': 'Burbuja', 'bulle.active': 'Burbuja activa',
  },
};

TEXTES.de = Object.assign({}, TEXTES.en);
TEXTES.pt = Object.assign({}, TEXTES.en);

let LANGUE = localStorage.getItem('dnareader_langue') || '';
if (!LANGUE) {
  const n = (navigator.language || 'fr').slice(0, 2).toLowerCase();
  LANGUE = (n in LANGUES) ? n : 'fr';
}

function t(cle, defaut) {
  if (LANGUE === 'fr') return defaut !== undefined ? defaut : cle;
  const d = TEXTES[LANGUE];
  if (d && d[cle] !== undefined) return d[cle];
  return defaut !== undefined ? defaut : cle;
}

function traduisPage() {
  document.querySelectorAll('[data-t]').forEach(e => {
    const v = t(e.dataset.t, e.dataset.tFr || e.textContent);
    if (e.dataset.tFr === undefined) e.dataset.tFr = e.textContent;
    e.textContent = v;
  });
  document.querySelectorAll('[data-t-title]').forEach(e => {
    if (e.dataset.tTitleFr === undefined) e.dataset.tTitleFr = e.title || '';
    e.title = t(e.dataset.tTitle, e.dataset.tTitleFr);
  });
  document.documentElement.lang = LANGUE;
}

function changeLangue(l) {
  if (!(l in LANGUES)) return;
  LANGUE = l;
  localStorage.setItem('dnareader_langue', l);
  traduisPage();
  if (typeof hidePopup === 'function') hidePopup();
  if (typeof annonceEtat === 'function') annonceEtat();
}
