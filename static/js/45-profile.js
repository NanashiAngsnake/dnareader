let PROF_LOADING = false;
let profTimer = null;

function collectProfile() {
  return {
    zone: ZONE, opacity: OPACITY, opacitylec: OPACITY_LECTURE,
    fontsize: FS, engine: ENGINE,
    stream: STREAM, enhance: ENHANCE, gamehl: GAMEHL, autofreeze: AUTOFREEZE,
    mode: MODE,
  };
}

async function saveProfile() {
  if (PROF_LOADING || !gameTitle) return;
  const data = collectProfile();
  const pv = window.pywebview && window.pywebview.api;
  if (pv && typeof pv.get_geometry === 'function' && !docked) {
    try { const g = await pv.get_geometry(); if (g) data.geom = g; } catch (e) {}
  }
  try { await api('/api/profile', {game: gameTitle, data}); } catch (e) {}
}

profileTouch = function () {
  if (PROF_LOADING || !gameTitle) return;
  clearTimeout(profTimer);
  profTimer = setTimeout(saveProfile, 600);
};

async function applyProfile(p) {
  PROF_LOADING = true;
  try {
    if (p.zone !== undefined) {
      ZONE = p.zone;
      localStorage.setItem(zoneKey(), JSON.stringify(ZONE));
      zoneLabel();
    }
    if (typeof p.fontsize === 'number') { FS = p.fontsize; applyFS(); }
    if (typeof p.opacity === 'number')  { OPACITY = p.opacity; applyOpacity(true); }
    if (typeof p.opacitylec === 'number') { OPACITY_LECTURE = p.opacitylec; applyOpacity(true); }
    if (typeof p.engine === 'string')   { ENGINE = p.engine; applyEngine(); }
    if (typeof p.enhance === 'string')  { ENHANCE = p.enhance; applyEnhance(); }
    if (typeof p.gamehl === 'boolean')  { GAMEHL = p.gamehl; applyGameHl(); }
    if (typeof p.mode === 'string')     { MODE = p.mode; await applyMode(true); }
    if (typeof p.autofreeze === 'boolean') { AUTOFREEZE = p.autofreeze; applyAutoFreeze(); }
    if (GHOST && !docked) { GHOST = false; applyGhost(true); }
    if (typeof p.stream === 'boolean')  { STREAM = p.stream; await applyStream(); }
    const pv = window.pywebview && window.pywebview.api;
    if (p.geom && pv && typeof pv.set_geometry === 'function' && !docked) {
      const g = await (async () => {
        try { return await pv.get_geometry(); } catch (e) { return null; }
      })();
      const w = g ? g.w : p.geom.w, h = g ? g.h : p.geom.h;
      try { await pv.set_geometry(p.geom.x, p.geom.y, w, h); } catch (e) {}
      if (typeof oublieTailleDemandee === 'function') oublieTailleDemandee();
      if (typeof planifieAjustement === 'function') planifieAjustement();
    }
  } finally { PROF_LOADING = false; }
}

async function loadProfile() {
  if (!gameTitle) return;
  let p = {};
  try {
    const r = await fetch('/api/profile?game=' + encodeURIComponent(gameTitle))
                    .then(r => r.json());
    p = (r && r.profile) || {};
  } catch (e) { return; }
  if (!Object.keys(p).length) {
    let z = null;
    try { z = JSON.parse(localStorage.getItem(zoneKey()) || 'null'); } catch {}
    if (z) { p = {zone: z}; saveProfile(); }
    else { setStatus(`Jeu : ${gameTitle}. Aucun profil, ${(HOTKEYS.zone || 'ctrl+shift+a').toUpperCase()} pour définir la zone`); return; }
  }
  await applyProfile(p);
  setStatus(`Profil de « ${gameTitle} » chargé`);
}
