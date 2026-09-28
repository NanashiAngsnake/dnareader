let MAJ = {possible: false};
let MAJ_SUIVI = null;

function depuisQuand(t) {
  const s = Math.max(0, Date.now() / 1000 - t);
  if (s < 90) return 'à l\'instant';
  if (s < 5400) return `il y a ${Math.round(s / 60)} min`;
  if (s < 172800) return `il y a ${Math.round(s / 3600)} h`;
  return `il y a ${Math.round(s / 86400)} jours`;
}

function majPoids(o) {
  if (!o) return '';
  return `(${(o / 1e6).toFixed(0)} Mo)`;
}

function majNotes(texte) {
  const e = $('majnotes');
  e.textContent = (texte || '').trim().slice(0, 1200)
                  || 'Pas de détail publié pour cette version.';
}

function majPeins() {
  $('majsection').hidden = !MAJ.possible;
  if (!MAJ.possible) return;

  $('majlocale').textContent = MAJ.version_locale || '?';
  $('majauto').classList.toggle('on', !!MAJ.auto);
  $('majauto').textContent = MAJ.auto ? 'Automatiquement' : 'Jamais';

  const a_montrer = !!MAJ.version_distante && !MAJ.ignoree;
  $('majtrouvee').hidden = !a_montrer;
  if (a_montrer) {
    $('majdistante').textContent = MAJ.version_distante;
    $('majpoids').textContent = majPoids(MAJ.octets);
    majNotes(MAJ.notes);
  }

  const enCours = MAJ.phase === 'telechargement';
  $('majprogres').hidden = !enCours;
  $('majinstaller').disabled = enCours;
  if (enCours) {
    const pct = MAJ.octets ? Math.min(100, MAJ.recus * 100 / MAJ.octets) : 0;
    $('majbarre').value = pct;
    $('majrecus').textContent =
      `${(MAJ.recus / 1e6).toFixed(0)} / ${(MAJ.octets / 1e6).toFixed(0)} Mo`;
  }

  if (MAJ.erreur) {
    $('majetat').textContent = MAJ.erreur;
  } else if (MAJ.ignoree) {
    $('majetat').textContent = `Version ${MAJ.version_distante} ignorée.`;
  } else if (!MAJ.version_distante) {
    $('majetat').textContent = MAJ.dernier_controle
      ? `À jour, vérifié ${depuisQuand(MAJ.dernier_controle)}.` : '';
  } else {
    $('majetat').textContent = '';
  }
}

async function majRelis() {
  try {
    MAJ = await fetch('/api/maj').then(r => r.json());
  } catch (e) { return; }
  majPeins();

  if (MAJ.phase === 'telechargement' && !MAJ_SUIVI) {
    MAJ_SUIVI = setInterval(majRelis, 700);
  }

  if (MAJ.phase === 'prete' && MAJ_SUIVI && !MAJ.ignoree) {
    majArreteLeSuivi();
    await majLance();
  }
  if (MAJ.phase === 'echec' && MAJ_SUIVI) {
    majArreteLeSuivi();
    dit(`Mise à jour interrompue : ${MAJ.erreur}`, 'ko');
  }
}

function majArreteLeSuivi() {
  if (MAJ_SUIVI) { clearInterval(MAJ_SUIVI); MAJ_SUIVI = null; }
}

async function majLance() {
  dit('Installation : l\'application va se fermer et revenir.', '');
  const r = await poste('/api/maj/installer');
  if (!r.ok) { dit(`Installation impossible : ${r.raison}`, 'ko'); return; }
  const pv = window.pywebview && window.pywebview.api;
  if (pv && typeof pv.close_app === 'function') {
    setTimeout(() => pv.close_app(), 600);
  } else {
    dit('Installateur lancé. Ferme DNAreader pour le laisser travailler.', '');
  }
}

function majBranche() {
  if (!$('majsection')) return;

  $('majinstaller').onclick = async () => {
    const r = await poste('/api/maj/telecharger');
    if (!r.ok) { dit(`Téléchargement impossible : ${r.raison}`, 'ko'); return; }
    dit('Téléchargement de la mise à jour…', '');
    majArreteLeSuivi();
    MAJ_SUIVI = setInterval(majRelis, 700);
    majRelis();
  };

  $('majannuler').onclick = async () => {
    await poste('/api/maj/annuler');
    majArreteLeSuivi();
    dit('Téléchargement annulé.', '');
    majRelis();
  };

  async function renonce(message) {
    majArreteLeSuivi();
    await poste('/api/maj/annuler');
    dit(message, '');
  }

  $('majplustard').onclick = async () => {
    await renonce('On en reparle au prochain démarrage.');
    $('majtrouvee').hidden = true;
  };

  $('majignorer').onclick = async () => {
    const v = MAJ.version_distante;
    await renonce('…');
    const r = await poste('/api/maj/ignorer', {version: v});
    if (!r.ok) { dit(r.raison || 'refusé', 'ko'); return; }
    dit(`Version ${r.version_ignoree} ignorée. La suivante sera proposée.`, '');
    majRelis();
  };

  $('majauto').onclick = async () => {
    await poste('/api/maj/auto', {actif: !MAJ.auto});
    majRelis();
  };

  $('majmaintenant').onclick = async () => {
    dit('Recherche…', '');
    MAJ = await poste('/api/maj/chercher');
    majPeins();
    dit(MAJ.version_distante ? `Version ${MAJ.version_distante} disponible.`
                             : 'Aucune nouvelle version.', '');
  };

  majRelis();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', majBranche);
} else {
  majBranche();
}
