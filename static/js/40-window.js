let rsz = null, rszRaf = 0, rszNext = null;
const MIN_W = 280, MIN_HH = 90, MAX_HH = 1400;

async function startResize(bords, ev) {
  const pv = window.pywebview && window.pywebview.api;
  if (!pv || typeof pv.set_geometry !== 'function') return;
  if (docked) {
    if (bords !== 't') { setStatus('Attaché : la largeur suit celle du jeu'); return; }
    ev.preventDefault();
    rsz = {bords: 'dockT', y0: ev.screenY, h0: window.innerHeight};
    document.body.classList.add('resizing');
    return;
  }
  ev.preventDefault();
  const g = await pv.get_geometry();
  if (!g) return;
  rsz = {bords, g, x0: ev.screenX, y0: ev.screenY, r: window.devicePixelRatio || 1};
  document.body.classList.add('resizing');
}

window.addEventListener('mousemove', ev => {
  if (!rsz) return;
  if (rsz.bords === 'dockT') {
    const pv = window.pywebview && window.pywebview.api;
    const h = Math.max(MIN_HH, Math.min(MAX_HH, rsz.h0 - (ev.screenY - rsz.y0)));
    if (pv && typeof pv.set_overlay_height === 'function') pv.set_overlay_height(h);
    return;
  }
  const dx = Math.round((ev.screenX - rsz.x0) * rsz.r);
  const dy = Math.round((ev.screenY - rsz.y0) * rsz.r);
  let {x, y, w, h} = rsz.g;
  if (rsz.bords.includes('l')) { const nw = Math.max(MIN_W, w - dx); x += (w - nw); w = nw; }
  if (rsz.bords.includes('r')) { w = Math.max(MIN_W, w + dx); }
  if (rsz.bords.includes('t')) {
    const nh = Math.max(MIN_HH, Math.min(MAX_HH, h - dy));
    y += (h - nh); h = nh;
  }
  if (rsz.bords.includes('b')) { h = Math.max(MIN_HH, Math.min(MAX_HH, h + dy)); }
  rszNext = [x, y, w, h];
  if (rszRaf) return;
  rszRaf = requestAnimationFrame(() => {
    rszRaf = 0;
    const pv = window.pywebview && window.pywebview.api;
    if (pv && rszNext) pv.set_geometry.apply(pv, rszNext);
  });
});

window.addEventListener('mouseup', () => {
  if (!rsz) return;
  rsz = null; rszNext = null;
  document.body.classList.remove('resizing');
  profileTouch();
});

[['grip', 't'], ['gripL', 'l'], ['gripR', 'r'], ['gripB', 'b'],
 ['gripTL', 'tl'], ['gripTR', 'tr'],
 ['gripBL', 'bl'], ['gripBR', 'br']].forEach(([id, bords]) => {
  const el = $(id);
  if (el) el.addEventListener('mousedown', ev => startResize(bords, ev));
});

async function detache() {
  const pv = window.pywebview && window.pywebview.api;
  if (!pv || typeof pv.undock !== 'function' || !docked) return;
  try { await pv.undock(); } catch (e) {}
  docked = false;
  document.body.classList.remove('docked');
  applyOpacity(false);
}
let dragging = false, dragPending = null, dragRaf = 0;
let dragABouge = false;
const NO_DRAG = 'button, select, input, label, a, #text, #popup, #settings input';
async function startDrag(ev) {
  if (ev.button !== 0) return;
  if (ev.target.closest && ev.target.closest(NO_DRAG)) return;
  const pv = window.pywebview && window.pywebview.api;
  if (!pv) return;
  if (docked) { setStatus('Détache d\'abord pour déplacer la fenêtre'); return; }
  ev.preventDefault();
  dragging = true;
  document.body.style.cursor = 'grabbing';
  const r = window.devicePixelRatio || 1;
  await pv.begin_drag(Math.round(ev.screenX * r), Math.round(ev.screenY * r));
}
window.addEventListener('mousemove', ev => {
  if (!dragging) return;
  const r = window.devicePixelRatio || 1;
  dragPending = [Math.round(ev.screenX * r), Math.round(ev.screenY * r)];
  dragABouge = true;
  if (dragRaf) return;
  dragRaf = requestAnimationFrame(() => {
    dragRaf = 0;
    const pv = window.pywebview && window.pywebview.api;
    if (pv && dragPending) pv.drag_to(dragPending[0], dragPending[1]);
  });
});
window.addEventListener('mouseup', async () => {
  if (!dragging) return;
  const aBouge = dragABouge;
  dragging = false; dragPending = null; dragABouge = false;
  document.body.style.cursor = '';
  const pv = window.pywebview && window.pywebview.api;
  if (pv) pv.end_drag();
  profileTouch();
  if (aBouge && typeof memoriseRepos === 'function') {
    await memoriseRepos();
  }
});

const KEY_LABELS = {capture: 'kcap', toggle: 'ktog', ghost: 'kghost',
                    freeze: 'kfreeze', bulle: 'kbulle', zone: 'kzone',
                    quitter: 'kquit', muet: 'kmuet', souris: 'ksouris'};
const KEY_ALIAS = {kghost2: 'ghost', kghost3: 'ghost', kfreeze2: 'freeze',
                   kbulle2: 'bulle', ktog2: 'toggle'};
function paintHotkeys() {
  for (const [nom, id] of Object.entries(KEY_LABELS)) {
    const el = $(id);
    if (el && HOTKEYS[nom]) el.textContent = HOTKEYS[nom].toUpperCase();
  }
  for (const [id, nom] of Object.entries(KEY_ALIAS)) {
    const el = $(id);
    if (el && HOTKEYS[nom]) el.textContent = HOTKEYS[nom].toUpperCase();
  }
}
let capturingHk = null;
function hkHint(msg) {
  for (const id of ['rebindhint', 'brebindhint']) {
    const el = $(id);
    if (el) el.textContent = msg;
  }
}
document.querySelectorAll('.rebind').forEach(b => {
  b.addEventListener('click', () => {
    capturingHk = b.dataset.hk;
    b.classList.add('on');
    hkHint('appuie sur la touche… (Échap pour annuler)');
  });
});
document.addEventListener('keydown', async ev => {
  if (!capturingHk) return;
  ev.preventDefault(); ev.stopPropagation();
  const bouton = document.querySelector(`.rebind[data-hk="${capturingHk}"]`);
  const nom = capturingHk; capturingHk = null;
  if (bouton) bouton.classList.remove('on');
  if (ev.key === 'Escape') { hkHint('inchangé'); return; }
  const parts = [];
  if (ev.ctrlKey) parts.push('ctrl');
  if (ev.altKey) parts.push('alt');
  if (ev.shiftKey) parts.push('shift');
  const base = ev.key.length === 1 ? ev.key.toLowerCase() : ev.key.toLowerCase();
  if (!['control','alt','shift'].includes(base)) parts.push(base);
  const combo = parts.join('+');
  const r = await api('/api/hotkey', {hotkey: combo, name: nom});
  if (r && r.error) { hkHint(r.error); return; }
  HOTKEYS = Object.assign({}, HOTKEYS, r.hotkeys || {});
  paintHotkeys();
  hkHint(`« ${combo.toUpperCase()} » enregistré`);
}, true);

fetch('/api/hotkey').then(r => r.json()).then(d => {
  const hk = d.hotkeys || {};
  HOTKEYS = Object.assign({}, HOTKEYS, hk);
  paintHotkeys();
  const tog = (hk.toggle || 'f9').toUpperCase();
  if (!gameTitle) setStatus(`Choisis le jeu… (${tog} = masquer/afficher)`);
}).catch(() => {});
