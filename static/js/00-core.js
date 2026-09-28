window.__errors = [];
function reportError(what) {
  window.__errors.push(what);
  try {
    const el = document.getElementById('status');
    if (el) {
      el.textContent = '⚠ ' + what;
      el.style.color = '#e06a6a';
      el.title = window.__errors.join('\n');
    }
    const d = document.getElementById('dot');
    if (d) d.className = 'err';
  } catch (e) {}
}
window.addEventListener('error', ev => {
  const src = (ev.filename || '').split('/').pop();
  reportError(`${ev.message} (${src}:${ev.lineno})`);
});
window.addEventListener('unhandledrejection', ev =>
  reportError('promesse rejetée : ' + (ev.reason && ev.reason.message || ev.reason)));

window.__bound = new Set();
const _addEL = EventTarget.prototype.addEventListener;
EventTarget.prototype.addEventListener = function (type, fn, opts) {
  if (this && this.id) window.__bound.add(this.id + ':' + type);
  return _addEL.call(this, type, fn, opts);
};

const $ = id => document.getElementById(id);
function si(id, action) {
  const e = document.getElementById(id);
  if (e) action(e);
}
async function api(path, body) {
  const r = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body||{})});
  return r.json();
}
function esc(s){ return String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

const IS_JP = /[぀-ヿ㐀-䶿一-鿿ｦ-ﾟ々〆ー]/;

let gameTitle = '';
let COUVERT = '';
let PLEIN_ECRAN = '';
let LINES = [];
let HOTKEYS = {capture: 'f8', toggle: 'f9', ghost: 'f10', zone: 'ctrl+shift+a', muet: 'f6', souris: 'f2'};

let profileTouch = () => {};

let docked = false;

let MODE = localStorage.getItem('kgr_mode') || 'lecture';
const MODE_FENETRE = !document.body || !document.getElementById('bnav');
const FR = new Map();
let TAGS = {};
fetch('/api/tags').then(r=>r.json()).then(t=>TAGS=t);
function tagNote(t){ return (TAGS[t] && TAGS[t].notes) || t; }
function posTag(t){ return TAGS[t] && ['partOfSpeech','pos'].includes(TAGS[t].category); }

function setDot(s){ $('dot').className = s; }
function setStatus(s){ $('status').textContent = s; }
