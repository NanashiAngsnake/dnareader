function selfCheck() {
  const needed = ['bar','dot','status','statuspill','text','popup',
                  'bgrip','battente','bjeu','bjeulbl','bjeuliste','veilleoeil',
                  'bulleout','bnav','bprev','bnext','bidx','bgear','bquit',
                  'bset','bopacity','bopacitylec','bfsdown','bfsup','bafbtn','bsetplus',
                  'bapprend','bapprendok','bapprendnon','bapprendtexte',
                  'bmuet','bcouleurs','kmuet','ksouris','bengine','btuto',
                  'bzonetout','bzonelbl'];
  const missing = needed.filter(i => !document.getElementById(i));
  const fns = ['loop','drainLoop','doOCR','startDrag','applyGameHl',
               'updateHistUI','renderText','gameHighlight','readText',
               'applyStream','mergeReadings','loadProfile','saveProfile',
               'profileTouch','startZonePick','applyMode','requestTranslations',
               'toggleFreeze','onNewText','applyAutoFreeze','renderIfChanged','rattraperRendu','onHover',
               'paintHotkeys','applyBulle','fitBulle','bulleGo','majCompteur','confirme','majPerf','toggleBset','majBset','hkHint',
               'tutoProposePeutEtre','tutoDemarre','tutoAffiche','tutoFin','tutoPoseCarte',
               'tutoRedimensionne','tutoLargeurVoulue',
               'recolteDemandePeutEtre','recolteRepond',
               'apprendUnEndroit','retientLEndroit','fermeApprentissage',
               'applyCouleur','setCouleur','peinsCouleurs',
               'litEnCeMoment',
               'relisAcces','tireLesCorrectionsPartagees','zoneTout','zoneLabel',
               'appliqueReglage','annonceEtat','ouvreReglages','setGame','ajusteFenetreAuContenu','relisJeuxBulle','peinsListeJeux',
               'majEtiquetteJeu','ouvreListeJeux','fermeListeJeux','bascListeJeux'];
  const broken = fns.filter(f => typeof window[f] !== 'function'
                              && eval(`typeof ${f}`) !== 'function');
  const inertes = [...document.querySelectorAll('button[id]')]
    .map(b => b.id)
    .filter(id => !window.__bound.has(id + ':click'));
  if (missing.length || broken.length || inertes.length) {
    reportError(`démarrage incomplet. éléments: ${missing.join(',') || 'ok'}`
      + ` / fonctions: ${broken.join(',') || 'ok'}`
      + ` / boutons inertes: ${inertes.join(',') || 'ok'}`);
    return false;
  }
  return true;
}

if (typeof traduisPage === 'function') traduisPage();

if (selfCheck()) {
  refreshWindows();
  setInterval(refreshWindows, 8000);
  updateHistUI();
  applyGameHl();
  applyOpacity(false);
  applyCouleur(false);
  peinsCouleurs();
  if (MUET) window.toggleMuet(true);
  applyGhost(true);
  applyMode(true);
  applyAutoFreeze();
  applyBulle();
  if (typeof reprendLeJeuRetenu === 'function') reprendLeJeuRetenu();
  annonceEtat();
  loop();
  drainLoop();
  tutoProposePeutEtre();
}
