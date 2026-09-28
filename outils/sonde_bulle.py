# -*- coding: utf-8 -*-
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "app"))


def port_libre():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


SONDE = r'''
import json, time, webview, overlay
LIGNES = json.load(open(r"%(lignes)s", encoding="utf-8"))
OUT = {}

def js(w, code):
    try:
        return w.evaluate_js(code)
    except Exception as e:
        return "ERREUR " + repr(e)

def probe(w):
    time.sleep(3.5)
    OUT["_avant_injection"] = js(w, """(function(){
      return JSON.stringify({
        url: location.pathname,
        titre: document.title,
        n_ids: document.querySelectorAll('[id]').length,
        a_bar: !!document.getElementById('bar'),
        a_text: !!document.getElementById('text'),
        a_popup: !!document.getElementById('popup'),
        a_barre_supprimee: !document.getElementById('ctl'),
        classes_body: document.body.className,
        ids: Array.prototype.slice.call(document.querySelectorAll('[id]'), 0, 14).map(function(e){return e.id})
      });
    })()""")
    # On passe par les MEMES fonctions que l'application : injecter les lignes
    # puis appeler le rendu reel, sinon on mesurerait une mise en page fictive.
    js(w, "LINES = " + json.dumps(LIGNES, ensure_ascii=False) + "; 1")
    # En attente, la fenetre doit coller au CONTENU. Sinon elle garde la largeur
    # de la lecture precedente et devient un grand rectangle noir autour de
    # trois boutons.
    js(w, """(function(){
      window.__attente = 'en cours';
      // On ferme la carte d'accueil : sinon on mesure DEUX etats a la fois,
      // et la « bulle en attente » herite de la taille de la carte.
      if (typeof tutoFin === 'function') tutoFin();
      document.body.classList.remove('en-visite');
      document.getElementById('tutoask').classList.remove('show');
      document.getElementById('tuto').classList.remove('show');
      var sauveJeu = gameTitle, sauveLignes = LINES;
      BULLE = true; gameTitle = ''; LINES = []; applyBulle();
      setTimeout(function(){
        var r = document.getElementById('bar').getBoundingClientRect();
        var vis = getComputedStyle(document.getElementById('battente')).display;
        // AUCUN controle ne doit depasser du cadre. C'est le seul critere qui
        // garantit qu'on peut tous les atteindre : mesurer la barre ne suffit
        // pas, elle tient dans la fenetre par construction.
        var dehors = [];
        var bar = document.getElementById('bar').getBoundingClientRect();
        ['bgrip','bjeu','bprev','bnext','bgear','bquit'].forEach(function(id){
          var e = document.getElementById(id);
          if (!e) return;
          var st = getComputedStyle(e);
          if (st.display === 'none' || st.visibility === 'hidden') return;
          var c = e.getBoundingClientRect();
          if (!c.width) return;
          if (Math.round(c.right) > window.innerWidth + 2
              || Math.round(c.bottom) > window.innerHeight + 2
              || Math.round(c.left) < -2) {
            dehors.push(id + '(' + Math.round(c.right) + '>' + window.innerWidth + ')');
          }
        });
        var grip = document.getElementById('bgrip');
        var gs = getComputedStyle(grip);
        var gr = grip.getBoundingClientRect();
        window.__attente = JSON.stringify({
          barre: {w: Math.round(r.width), h: Math.round(r.height)},
          fenetre: {w: window.innerWidth, h: window.innerHeight},
          libelle_visible: vis !== 'none',
          libelles: document.querySelectorAll('#battente').length,
          texte: (document.getElementById('battente').textContent || '').trim().slice(0, 40),
          poignee_visible: gs.display !== 'none' && gr.width > 6,
          poignee: {w: Math.round(gr.width), h: Math.round(gr.height)},
          poignee_liee: !!(window.__bound && window.__bound.has('bgrip:mousedown')),
          controles_dehors: dehors
        });
        BULLE = false; gameTitle = sauveJeu; LINES = sauveLignes; applyBulle();
      }, 1400);
      return 1;
    })()""")
    time.sleep(2.6)
    OUT["bulle_attente"] = js(w, "window.__attente")
    time.sleep(0.4)

    # Les langues. Basculer doit changer les libelles VISIBLES, et revenir en
    # arriere doit tout restaurer : une traduction qui ne sait pas revenir laisse
    # l'interface a moitie traduite.
    OUT["langues"] = js(w, """(function(){
      var avant = document.getElementById('bafbtn').textContent.trim();
      var titreAvant = document.getElementById('bjeu').title;
      changeLangue('en');
      var apresEN = document.getElementById('bafbtn').textContent.trim();
      var titreEN = document.getElementById('bjeu').title;
      changeLangue('es');
      var apresES = document.getElementById('bafbtn').textContent.trim();
      changeLangue('fr');
      var retour = document.getElementById('bafbtn').textContent.trim();
      return JSON.stringify({
        langues: Object.keys(LANGUES).length,
        fr: avant, en: apresEN, es: apresES, retour: retour,
        titre_fr: titreAvant, titre_en: titreEN,
        change: apresEN !== avant && apresES !== apresEN,
        revient: retour === avant,
        infobulle_traduite: titreEN !== titreAvant
      });
    })()""")
    time.sleep(0.4)

    # Le cas signale : panneau de reglages ET liste des jeux ouverts ensemble.
    # Une liste NATIVE etait coupee au bord de la fenetre ; celle-ci est du HTML,
    # la fenetre doit donc pouvoir la contenir entierement.
    js(w, """(function(){
      window.__liste = 'en cours';
      var sauveJeu = gameTitle, sauveLignes = LINES;
      BULLE = true; gameTitle = ''; LINES = []; applyBulle();
      setTimeout(function(){
        if (!document.getElementById('bset').classList.contains('show')) toggleBset();
        ouvreListeJeux();
        setTimeout(function(){
          var l = document.getElementById('bjeuliste');
          var r = l.getBoundingClientRect();
          var entrees = l.querySelectorAll('.jeu, .vide');
          var derniere = entrees.length ? entrees[entrees.length-1].getBoundingClientRect() : null;
          window.__liste = JSON.stringify({
            visible: getComputedStyle(l).display !== 'none',
            entrees: entrees.length,
            liste: {w: Math.round(r.width), h: Math.round(r.height),
                    bas: Math.round(r.bottom)},
            fenetre: {w: window.innerWidth, h: window.innerHeight},
            entiere: Math.round(r.bottom) <= window.innerHeight + 2
                  && Math.round(r.right) <= window.innerWidth + 2,
            defile: l.scrollHeight > l.clientHeight + 2,
            atteignable: l.scrollHeight <= l.clientHeight + 2
                      || getComputedStyle(l).overflowY === 'auto'
                      || getComputedStyle(l).overflowY === 'scroll' 
          });
          fermeListeJeux();
          if (document.getElementById('bset').classList.contains('show')) toggleBset();
          BULLE = false; gameTitle = sauveJeu; LINES = sauveLignes; applyBulle();
        }, 1500);
      }, 900);
      return 1;
    })()""")
    time.sleep(4.5)
    OUT["liste_jeux"] = js(w, "window.__liste")
    time.sleep(0.5)

    # Cycle complet : du texte, puis plus rien (la bulle se masque), puis du
    # texte a nouveau. C'est le cycle NORMAL d'une partie, et c'est la que
    # « les bulles ne s'affichent plus » se joue.
    js(w, """(function(){
      window.__cycle = 'en cours';
      var sauve = LINES;
      BULLE = true; gameTitle = 'JEU TEST'; LINES = sauve; applyBulle();
      setTimeout(function(){
        var etapes = {};
        etapes.avec = {survolee: bulleSurvolee, vide: bulleVide};
        etapes.avec.veille = document.body.classList.contains('veille');
        LINES = []; fitBulle();
        setTimeout(function(){
          etapes.sans = {survolee: bulleSurvolee, vide: bulleVide,
                         veille: document.body.classList.contains('veille'),
                         fenetreVisible: window.innerWidth > 10 && window.innerHeight > 10};
          LINES = sauve; fitBulle();
          setTimeout(function(){
            etapes.retour = {survolee: bulleSurvolee, vide: bulleVide,
                             visible: !bulleVide};
            window.__cycle = JSON.stringify(etapes);
            gameTitle = ''; BULLE = false; applyBulle();
          }, 900);
        }, 900);
      }, 700);
      return 1;
    })()""")
    time.sleep(3.6)
    OUT["cycle_bulle"] = js(w, "window.__cycle")
    time.sleep(0.4)

    # La bulle ne doit pas GLISSER quand la boucle de lecture la repose.
    # Defaut mesure avant correction : 26 px par appel, 234 px en dix appels.
    # Elle fuyait sous le curseur, on ne pouvait plus cliquer ses boutons.
    js(w, """(function(){
      window.__derive = 'en cours';
      var pv = window.pywebview.api;
      var sauveJeu = gameTitle, sauveLignes = LINES;
      BULLE = true; gameTitle = ''; LINES = []; applyBulle();
      var ys = [];
      function tour(i) {
        if (i >= 8) {
          BULLE = false; gameTitle = sauveJeu; LINES = sauveLignes; applyBulle();
          window.__derive = JSON.stringify({y: ys, derive: ys[ys.length-1] - ys[0]});
          return;
        }
        pv.get_geometry().then(function(g){
          ys.push(g && g.y);
          fitBulle();
          setTimeout(function(){ tour(i + 1); }, 220);
        });
      }
      setTimeout(function(){ tour(0); }, 700);
      return 1;
    })()""")
    time.sleep(4.2)
    OUT["derive_bulle"] = js(w, "window.__derive")
    time.sleep(0.5)

    # Fenetre collee EN HAUT de l'ecran, puis agrandie. L'agrandissement ancre
    # le bas et pousse le haut : sans borne, la fenetre sortait par le haut et
    # la carte du tutoriel s'affichait a moitie hors de l'ecran.
    js(w, """(function(){
      window.__haut = 'en cours';
      var pv = window.pywebview.api;
      pv.set_geometry(60, 0, 900, 120).then(function(){
        return pv.set_overlay_height(420);
      }).then(function(){
        return pv.get_geometry();
      }).then(function(g){
        window.__haut = JSON.stringify({geom: g, ecran_h: screen.height,
                                        fenetre: {w: window.innerWidth, h: window.innerHeight}});
      }).catch(function(e){ window.__haut = JSON.stringify({erreur: String(e)}); });
      return 1;
    })()""")
    time.sleep(2.4)
    OUT["colle_en_haut"] = js(w, "window.__haut")

    # Le mode traversant rend l'app insensible aux clics : vu de l'exterieur,
    # c'est indiscernable d'un plantage. Il DOIT s'annoncer.
    OUT["traversant"] = js(w, """(function(){
      GHOST = true; applyGhost(true);
      var b = document.getElementById('ghostbanner');
      var st = getComputedStyle(b);
      var r = b.getBoundingClientRect();
      // La marque etait un bandeau PLEIN ECRAN en position fixe, pose sur le
      // haut de la fenetre. Sur une bulle haute d'une ligne, elle recouvrait
      // exactement le texte : « si on met le mode transparence, on voit plus le
      // texte ». On mesure donc desormais le RECOUVREMENT, pas la largeur.
      var t = document.getElementById('text').getBoundingClientRect();
      var chevauche = !(r.right <= t.left || r.left >= t.right
                        || r.bottom <= t.top || r.top >= t.bottom);
      var res = {visible: st.display !== 'none' && r.width > 20 && r.height > 12,
                 hauteur: Math.round(r.height),
                 largeur: Math.round(r.width),
                 couvre_le_texte: chevauche,
                 touche: (document.getElementById('ghostkey')||{}).textContent,
                 barre_marquee: getComputedStyle(document.getElementById('bar')).outlineStyle !== 'none'};
      GHOST = false; applyGhost(true);
      res.disparait = getComputedStyle(b).display === 'none';
      return JSON.stringify(res);
    })()""")

    # --- la visite guidee -----------------------------------------------
    # Un tutoriel qui entoure le vide est pire que pas de tutoriel : il montre
    # avec assurance quelque chose qui n'est pas la. On verifie donc que le
    # halo tombe bien SUR le bouton annonce, a chaque etape.
    js(w, """(function(){
      window.__tuto = 'en cours';
      localStorage.removeItem(TUTO_VU);   // la cle de l'app, versionnee
      GHOST = true; applyGhost(true);      // on se met dans le cas qui a echoue
      // ETAT DU PREMIER LANCEMENT : aucun jeu, aucune ligne lue. C'est
      // precisement la que la visite se declenche, et c'est donc dans cet etat
      // qu'il faut la mesurer. Les lignes injectees plus haut masquaient le
      // choix du jeu, et la premiere etape designait alors un bouton cache.
      //
      // On MEMORISE pour rendre l'etat ensuite : les controles suivants (fiche
      // du dictionnaire, fleches) ont besoin des lignes, et les vider pour de
      // bon les faisait tous echouer d'un coup.
      window.__sauveJeu = gameTitle; window.__sauveLignes = LINES;
      gameTitle = ''; LINES = []; LIVE = [];
      applyBulle();
      tutoProposePeutEtre();
      var propose = document.getElementById('tutoask').classList.contains('show');
      // La carte d'ACCUEIL doit elle aussi masquer le texte de fond : c'est la
      // toute premiere chose que voit quelqu'un qui lance l'app.
      var accueilPropre = getComputedStyle(document.getElementById('text')).visibility === 'hidden';
      tutoDemarre();
      setTimeout(function(){
        var etapes = [], n = TUTO_ETAPES.length;
        for (var i = 0; i < n; i++) {
          tutoPas = i; tutoAffiche();
          var e = TUTO_ETAPES[i];
          var c = e.cible ? document.getElementById(e.cible) : null;
          var r = c ? c.getBoundingClientRect() : null;
          etapes.push({i: i, cible: e.cible || null,
                       existe: !!c,
                       visible: !!(r && r.width > 0 && r.height > 0),
                       titre: (e.titre || '').slice(0, 30)});
        }
        // MESURER UNE FOIS QUE LA FENETRE A SUIVI.
        // tutoAffiche pose la carte dans un requestAnimationFrame et DEMANDE
        // un redimensionnement asynchrone. Mesuree dans la foulee de la
        // boucle, la carte se comparait a une fenetre qui n'avait pas encore
        // grandi : on annoncait un debordement de quelques pixels qui
        // n'existe pas a l'ecran, et on ne verrait plus le vrai le jour ou
        // il arriverait.
        setTimeout(function(){
          var t = document.getElementById('tutotexte').textContent || '';
          // Surface assombrie par la visite. Un fond « inset:0 » sur une fenetre
          // posee sur le jeu, c'est une bache noire en travers de l'ecran.
          var tu = document.getElementById('tuto');
          var st = getComputedStyle(tu);
          var carte = document.getElementById('tutocarte').getBoundingClientRect();
          var halo = getComputedStyle(document.getElementById('tutohalo'));
          var fondOpaque = st.backgroundColor &&
                !/rgba\(0,\s*0,\s*0,\s*0\)|transparent/.test(st.backgroundColor);
          // une ombre de plusieurs milliers de pixels = tout l'ecran repeint
          var haloEnorme = /\b[0-9]{4,}px/.test(halo.boxShadow || '');
          window.__tuto = JSON.stringify({
            propose_au_premier_lancement: propose,
            accueil_masque_le_fond: accueilPropre,
            ouvert: document.getElementById('tuto').classList.contains('show'),
            etapes: etapes,
            hauteur: window.innerHeight,
            mentionne_gel: TUTO_ETAPES.some(function(e){
              return /gel|Gèle|geler/i.test(e.texte); }),
            mentionne_deux_types: TUTO_ETAPES.some(function(e){
              return /défile (tout )?seul/i.test(e.texte); }),
            mentionne_pc_modeste: TUTO_ETAPES.some(function(e){
              return /peu\s*puissant|modeste/i.test(e.texte); }),
            // CE QUI EST LIVRE, PAS CE QUI EST REVE. Ce controle exigeait le
            // mot « haute precision » — un mode qu'aucune version publiee n'a
            // jamais contenu (manga-ocr est exclu du paquet depuis avant la
            // 1.0.0). Le banc garantissait donc une promesse en trop. Ce qu'il
            // faut verifier, c'est que la visite explique le CHOIX du moteur.
            mentionne_precision: TUTO_ETAPES.some(function(e){
              return /moteur/i.test(e.titre + e.texte)
                     && /embarqu|Windows/i.test(e.texte); }),
            mentionne_bulle: TUTO_ETAPES.some(function(e){
              return /mode bulle/i.test(e.titre + e.texte); }),
            fond_opaque: fondOpaque,
            halo_enorme: haloEnorme,
            carte: {h: Math.round(carte.height), bas: Math.round(carte.bottom)},
            carte_dans_la_fenetre: Math.round(carte.bottom) <= window.innerHeight + 4,
            hauteur_fenetre: window.innerHeight,
            traversant_coupe: (typeof GHOST !== 'undefined') ? !GHOST : null,
            zone_lecture_masquee:
              getComputedStyle(document.getElementById('text')).visibility === 'hidden' 
          });
          tutoFin();
          // On rend l'etat d'avant : les controles suivants lisent de vraies
          // lignes, et la visite ne doit pas les leur retirer.
          gameTitle = window.__sauveJeu; LINES = window.__sauveLignes;
          setTimeout(function(){
            window.__apres_tuto = JSON.stringify({
              bulle: document.body.classList.contains('bulle'),
              hauteur: window.innerHeight});
          }, 900);
        }, 600);
      }, 700);
      return 1;
    })()""")
    time.sleep(2.4)
    OUT["tutoriel"] = js(w, "window.__tuto")
    time.sleep(1.4)
    OUT["apres_tuto"] = js(w, "window.__apres_tuto")

    # LA CARTE DE MISE A JOUR, MESUREE DANS LA VRAIE FENETRE.
    #
    # Elle reprend le style de la carte d'accueil ; « meme style » est une
    # supposition tant qu'on ne l'a pas mesuree. Une carte de 400 px dans une
    # bulle de 335 px sortirait du cadre, et personne ne verrait le bouton.
    js(w, """(function(){
      window.__maj = 'en cours';
      MAJ_DEMANDEE = false;
      majDit('La version <b>9.9.9</b> est disponible (155 Mo).<br><br>'
             + "L'application se ferme et revient toute seule, en gardant ton "
             + 'vocabulaire et tes reglages.');
      document.getElementById('majask').classList.add('show');
      document.body.classList.add('en-visite');
      if (typeof ajusteFenetreAuContenu === 'function') ajusteFenetreAuContenu();
      setTimeout(function(){
        var c = document.getElementById('majaskcarte').getBoundingClientRect();
        var b = [].map.call(document.querySelectorAll('#majask button'),
          function(x){ var r = x.getBoundingClientRect();
            return {texte: x.textContent.trim(), droite: Math.round(r.right),
                    bas: Math.round(r.bottom)}; });
        window.__maj = JSON.stringify({
          visible: document.getElementById('majask').classList.contains('show'),
          carte: {droite: Math.round(c.right), bas: Math.round(c.bottom)},
          fenetre: {w: window.innerWidth, h: window.innerHeight},
          boutons: b,
          tient: Math.round(c.right) <= window.innerWidth + 2
                 && Math.round(c.bottom) <= window.innerHeight + 2,
          boutons_dedans: b.every(function(x){
            return x.droite <= window.innerWidth + 2
                   && x.bas <= window.innerHeight + 2; })
        });
        document.getElementById('majask').classList.remove('show');
        document.body.classList.remove('en-visite');
      }, 900);
      return 1;
    })()""")
    time.sleep(2.2)
    OUT["maj_carte"] = js(w, "window.__maj")

    js(w, "BULLE = false; applyBulle(); 1")   # on rend la main aux autres controles
    time.sleep(0.5)
    time.sleep(0.6)

    # La visite est desormais proposee DES le demarrage, et elle masque la zone
    # de lecture. On y repond comme un utilisateur avant de mesurer le reste,
    # sinon tous les controles suivants portent sur un ecran de visite.
    js(w, """(function(){
      localStorage.setItem(TUTO_VU, '1');   // la cle de l'app, versionnee
      if (typeof tutoFin === 'function') tutoFin();
      document.body.classList.remove('en-visite');
      var a = document.getElementById('tutoask');
      if (a) a.classList.remove('show');
      return 1;
    })()""")
    time.sleep(0.8)

    # --- D'ABORD le mode overlay NORMAL : c'est le geste central de l'app,
    # passer la souris sur un mot et lire sa definition. Il n'etait couvert par
    # aucun controle, et il a casse sans que rien ne le dise.
    js(w, "renderText(); 1")
    time.sleep(0.8)
    js(w, """(function(){
      window.__ov = 'en cours';
      var sp = document.querySelectorAll('#text span[data-idx]');
      var cible = null;
      for (var k = 0; k < sp.length; k++) {
        if (/[\u3040-\u30ff\u4e00-\u9fff]/.test(sp[k].textContent)) { cible = sp[k]; break; }
      }
      if (!cible) { window.__ov = JSON.stringify({erreur: 'aucun caractere japonais'}); return 1; }
      doLookup(+cible.dataset.line, +cible.dataset.idx, 200, 40);
      setTimeout(function(){
        var pop = document.getElementById('popup');
        var st = getComputedStyle(pop);
        window.__ov = JSON.stringify({
          vise: cible.textContent,
          bulle: document.body.classList.contains('bulle'),
          fiche_visible: st.display !== 'none',
          entrees: pop.querySelectorAll('.entry').length,
          texte: (pop.textContent || '').slice(0, 60),
          rect: (function(b){ return {x: Math.round(b.x), y: Math.round(b.y),
                  w: Math.round(b.width), h: Math.round(b.height)}; })(pop.getBoundingClientRect()),
          hors_fenetre: pop.getBoundingClientRect().bottom > window.innerHeight ||
                        pop.getBoundingClientRect().right > window.innerWidth,
          fenetre: {w: window.innerWidth, h: window.innerHeight},
          room_demande: (typeof ficheRoomAsked !== 'undefined') ? ficheRoomAsked : 'absent',
          room_fn: typeof ficheRoom
        });
      }, 1800);
      return 1;
    })()""")
    time.sleep(2.6)
    OUT["survol_overlay"] = js(w, "window.__ov")
    js(w, "hidePopup(); 1")
    time.sleep(0.4)

    js(w, "BULLE = true; applyBulle(); 1")
    time.sleep(1.2)
    js(w, "renderText(); 1")
    time.sleep(1.0)

    # CHOISIR UN JEU NE DOIT PAS FAIRE QUITTER LA BULLE.
    #
    # Defaut rapporte : « quand je selectionne un jeu, ca m'ouvre ce truc » —
    # un grand rectangle noir portant les lignes empilees et pas un bouton.
    # setGame() appelle loadProfile(), qui contenait « if (BULLE) BULLE = false »
    # : ecrit quand la barre etait le mode par defaut, pour qu'un profil ne
    # puisse pas imposer la bulle. Une fois la barre supprimee, cette ligne
    # jetait vers un ecran mort. Aucun controle ne suivait ce chemin-la.
    js(w, "setGame('JEU TEST'); 1")
    time.sleep(1.4)
    OUT["choix_jeu"] = js(w, """(function(){
      return JSON.stringify({
        bulle: document.body.classList.contains('bulle'),
        barre_revenue: !!document.getElementById('ctl'),
        hauteur: window.innerHeight
      });
    })()""")
    js(w, "gameTitle = ''; applyBulle(); 1")
    time.sleep(0.6)

    OUT["sorties"] = js(w, """(function(){
      var r = {};
      ['bquit','bprev','bnext','bulleout'].forEach(function(id){
        var e = document.getElementById(id);
        if (!e) { r[id] = 'absent'; return; }
        var s = getComputedStyle(e), b = e.getBoundingClientRect();
        r[id] = { visible: s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.05,
                  x: Math.round(b.x), y: Math.round(b.y),
                  w: Math.round(b.width), h: Math.round(b.height) };
      });
      var bar = document.getElementById('bar').getBoundingClientRect();
      r._bar = {w: Math.round(bar.width), h: Math.round(bar.height)};
      r._fenetre = {w: window.innerWidth, h: window.innerHeight};
      return JSON.stringify(r);
    })()""")

    # --- le survol d'un mot ---
    # Les spans sont un par CARACTERE, avec data-idx : c'est sur eux que le
    # gestionnaire de survol est pose.
    OUT["survol"] = js(w, """(function(){
      var sp = document.querySelectorAll('#text span[data-idx]');
      if (!sp.length) return JSON.stringify({erreur: 'aucun caractere rendu', n: 0});
      var bar = document.getElementById('bar').getBoundingClientRect();
      window.__avant = {x: Math.round(bar.x), y: Math.round(bar.y),
                        w: Math.round(bar.width), h: Math.round(bar.height),
                        fw: window.innerWidth, fh: window.innerHeight};
      // Un caractere JAPONAIS, sinon le dictionnaire ne renvoie rien et la
      // fiche ne s'ouvre pas : on mesurerait alors « pas de decalage » pour la
      // mauvaise raison.
      var cible = null;
      for (var k = 0; k < sp.length; k++) {
        if (/[\u3040-\u30ff\u4e00-\u9fff]/.test(sp[k].textContent)) { cible = sp[k]; break; }
      }
      if (!cible) return JSON.stringify({erreur: 'aucun caractere japonais rendu'});
      // La souris arrive sur la barre : c'est ce qui FIGE la bulle.
      var avantGel = bulleSurvolee;
      document.getElementById('bar').dispatchEvent(new MouseEvent('mouseenter'));
      var apresGel = bulleSurvolee;
      // On appelle la recherche directement plutot que de simuler un survol :
      // ce qu'on veut mesurer, c'est l'effet de la FICHE sur la bulle.
      doLookup(+cible.dataset.line, +cible.dataset.idx, 120, 30);
      return JSON.stringify({caracteres: sp.length, vise: cible.textContent,
                             avant: window.__avant, survolee: bulleSurvolee,
                             gel_avant: avantGel, gel_apres_entree: apresGel,
                             timer_en_cours: !!degelTimer});
    })()""")
    time.sleep(2.5)
    OUT["apres_survol"] = js(w, """(function(){
      var pop = document.getElementById('popup');
      var st = getComputedStyle(pop), b = pop.getBoundingClientRect();
      var bar = document.getElementById('bar').getBoundingClientRect();
      var a = window.__avant || {};
      return JSON.stringify({
        fiche_visible: st.display !== 'none',
        fiche: {x: Math.round(b.x), y: Math.round(b.y),
                w: Math.round(b.width), h: Math.round(b.height)},
        barre_apres: {x: Math.round(bar.x), y: Math.round(bar.y),
                      w: Math.round(bar.width), h: Math.round(bar.height)},
        deplacement_px: Math.round(Math.abs(bar.x - (a.x||0)) + Math.abs(bar.y - (a.y||0))),
        largeur_changee: Math.round(bar.width) !== (a.w||0),
        fenetre: {w: window.innerWidth, h: window.innerHeight},
        fiche_deborde: Math.round(b.right) > window.innerWidth ||
                       Math.round(b.bottom) > window.innerHeight,
        survolee: bulleSurvolee
      });
    })()""")

    # LA BULLE NE DOIT JAMAIS SE POSER SUR LA ZONE DE LECTURE.
    #
    # C'est l'endroit ou le jeu ecrit ses dialogues : y poser une fenetre opaque
    # revient a masquer ce qu'on essaie justement de lire. Or la bulle se colle a
    # la ligne qu'elle vient de lire, donc elle y atterrissait naturellement.
    # On demande ici un placement sur une ligne PLACEE DANS la zone, et on
    # verifie que la fenetre finit en dehors.
    js(w, """(function(){
      window.__zone = 'en cours';
      var pv = window.pywebview && window.pywebview.api;
      if (!pv) { window.__zone = JSON.stringify({erreur: 'pas d api'}); return 1; }
      // zone = bande basse de la fenetre du jeu (0,70 a 0,95), la ou vivent
      // les sous-titres de la plupart des jeux
      var zone = [0.0, 0.70, 1.0, 0.25];
      pv.place_bubble([40, 40, 300, 30], 360, 90, null, zone, false, false)
        .then(function(r){
          setTimeout(function(){
            window.__zone = JSON.stringify({retour: r, zone: zone,
              ecran: {w: screen.width, h: screen.height},
              ratio: window.devicePixelRatio});
          }, 500);
        })
        .catch(function(e){ window.__zone = JSON.stringify({rejet: String(e)}); });
      return 1;
    })()""")
    time.sleep(2.2)
    OUT["hors_zone"] = js(w, "window.__zone")

    # evaluate_js ne sait pas attendre une promesse : on range le resultat
    # dans une variable globale et on la relit apres coup.
    js(w, """(function(){
      window.__res = 'en cours';
      // ON REPOSE DES LIGNES AVANT DE MESURER.
      // Sans elles, la bulle est en attente : l'application a RAISON de la
      // ramener a 55 px, et le controle accusait le redimensionnement d'un
      // refus qui n'existait pas. Mesure faite : un tour sur deux echouait,
      // selon que la boucle de lecture etait passee ou non dans l'intervalle.
      if (window.__sauveLignes && window.__sauveLignes.length) {
        LINES = window.__sauveLignes; LIVE = LINES;
        gameTitle = window.__sauveJeu || 'JEU TEST';
        applyBulle();
      }
      var pv = window.pywebview && window.pywebview.api;
      if (!pv) { window.__res = JSON.stringify({erreur: 'pas d api'}); return 1; }
      var avant = {w: window.innerWidth, h: window.innerHeight};
      pv.place_bubble([100,100,200,30], 600, 700, null, null, true, true)
        .then(function(r){
          setTimeout(function(){
            window.__res = JSON.stringify({avant: avant, retour: r,
              apres: {w: window.innerWidth, h: window.innerHeight},
              // CE QU'IL Y AVAIT A L'ECRAN AU MOMENT DE LA MESURE. Sans ca, une
              // fenetre revenue a 55 px ne dit pas si la demande a ete ignoree
              // ou si l'app a simplement reajuste sur une bulle devenue vide.
              classes: document.body.className,
              lignes: (typeof LINES !== 'undefined'
                       ? LINES.filter(function(l){ return l.jp; }).length : -1),
              ratio: window.devicePixelRatio});
          }, 600);
        })
        .catch(function(e){ window.__res = JSON.stringify({rejet: String(e)}); });
      return 1;
    })()""")
    time.sleep(2.5)
    OUT["agrandir_direct"] = js(w, "window.__res")

    # La souris quitte la barre pour aller LIRE la fiche : la fiche est hors de
    # #bar, ce depart declenche donc mouseleave. C'est le geste le plus naturel
    # du monde et c'est exactement la qu'on soupconne le decalage.
    OUT["souris_vers_la_fiche"] = js(w, """(function(){
      var bar = document.getElementById('bar');
      var avant = bar.getBoundingClientRect();
      bar.dispatchEvent(new MouseEvent('mouseleave'));
      return JSON.stringify({avant: {x: Math.round(avant.x), y: Math.round(avant.y)},
                             survolee: bulleSurvolee,
                             fiche_encore_la: getComputedStyle(
                               document.getElementById('popup')).display !== 'none'});
    })()""")
    time.sleep(1.2)
    OUT["apres_depart"] = js(w, """(function(){
      var bar = document.getElementById('bar').getBoundingClientRect();
      var pop = document.getElementById('popup');
      return JSON.stringify({
        barre: {x: Math.round(bar.x), y: Math.round(bar.y)},
        fiche_visible: getComputedStyle(pop).display !== 'none',
        survolee: bulleSurvolee
      });
    })()""")

    # Combien coute un deplacement de bulle ? (« quand on clique sur la ligne
    # suivante parfois il y a un petit delais avant qu'il se deplace »)
    js(w, """(function(){
      window.__chrono = 'en cours';
      var pv = window.pywebview.api, n = 8, t0 = performance.now(), faits = 0;
      function tour(i) {
        if (i >= n) {
          window.__chrono = JSON.stringify({appels: n,
            ms_par_appel: Math.round((performance.now() - t0) / n * 10) / 10});
          return;
        }
        pv.place_bubble([100 + i * 7, 200 + i * 5, 200, 30], 420, 60, null, null, false, false)
          .then(function(){ tour(i + 1); })
          .catch(function(e){ window.__chrono = JSON.stringify({erreur: String(e)}); });
      }
      tour(0);
      return 1;
    })()""")
    time.sleep(3.0)
    OUT["cout_deplacement"] = js(w, "window.__chrono")

    # Le panneau de reglages du mode bulle : il doit s'ouvrir, faire grandir la
    # bulle, et porter de vraies touches reassignables.
    js(w, """(function(){
      window.__bset = 'en cours';
      var avant = {w: window.innerWidth, h: window.innerHeight};
      document.getElementById('bgear').click();
      setTimeout(function(){
        var el = document.getElementById('bset');
        var st = getComputedStyle(el), b = el.getBoundingClientRect();
        window.__bset = JSON.stringify({
          avant: avant,
          visible: st.display !== 'none',
          taille: {w: Math.round(b.width), h: Math.round(b.height)},
          apres: {w: window.innerWidth, h: window.innerHeight},
          rebinds: el.querySelectorAll('.rebind').length,
          dans_la_fenetre: Math.round(b.bottom) <= window.innerHeight + 2
                        && Math.round(b.right) <= window.innerWidth + 2,
          debord_droite: Math.round(b.right - window.innerWidth),
          a_choix_jeu: !!document.getElementById('bjeu'),
          gel: !!el.querySelector('.rebind[data-hk=\\'freeze\\']')
        });
      }, 900);
      return 1;
    })()""")
    time.sleep(1.8)
    OUT["panneau_bulle"] = js(w, "window.__bset")

    # les fleches du clavier changent de ligne
    OUT["clavier"] = js(w, """(function(){
      var avant = BULLE_IDX;
      document.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}));
      var apres = BULLE_IDX;
      document.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowLeft', bubbles: true}));
      return JSON.stringify({depart: avant, apres_droite: apres, retour: BULLE_IDX,
                             lignes: lignesBulle().length});
    })()""")
    js(w, "document.getElementById('bgear').click(); 1")
    time.sleep(0.5)

    # Un reglage envoye depuis l'autre fenetre arrive-t-il VRAIMENT ici ?
    # C'est tout l'enjeu de la refonte : la fenetre de reglages ne partage
    # aucune variable avec la bulle, elle passe par le serveur.
    js(w, """(function(){
      window.__relais = 'en cours';
      var avant = OPACITY;
      fetch('/api/reglage', {method:'POST', headers:{'Content-Type':'application/json'},
                             body: JSON.stringify({cle:'opacity', valeur:57})})
        .then(function(){
          setTimeout(function(){
            window.__relais = JSON.stringify({avant: avant, apres: OPACITY,
                                              recu: OPACITY === 57});
          }, 900);
        });
      return 1;
    })()""")
    time.sleep(2.2)
    OUT["relais_reglages"] = js(w, "window.__relais")

    # La bulle annonce-t-elle son etat, pour que la fenetre s'ouvre juste ?
    OUT["etat_annonce"] = js(w, """(function(){
      annonceEtat();
      return JSON.stringify({fonction: typeof annonceEtat === 'function',
                             ouvre: typeof ouvreReglages === 'function'});
    })()""")
    time.sleep(0.8)
    OUT["etat_serveur"] = js(w, """(function(){
      var x = new XMLHttpRequest();
      x.open('GET', '/api/reglage', false); x.send(null);
      var d = JSON.parse(x.responseText).reglages || {};
      return JSON.stringify({cles: Object.keys(d).sort(),
                             a_opacite: 'opacity' in d, a_moteur: 'engine' in d});
    })()""")

    # La page des reglages se charge-t-elle sans erreur ?
    OUT["page_reglages"] = js(w, """(function(){
      var x = new XMLHttpRequest();
      x.open('GET', '/reglages', false); x.send(null);
      var t = x.responseText || '';
      return JSON.stringify({code: x.status, taille: t.length,
                             a_compte: /Compte/.test(t),
                             a_module: /70-reglages\.js/.test(t)});
    })()""")

    # La BARRE a ete supprimee : l'app vit en bulle. On verifie donc qu'elle
    # n'est plus la — un reste masque reviendrait tot ou tard a l'ecran — et que
    # le mode fenetre reste joignable par le relais des reglages, seul chemin
    # restant.
    # LE COMPTE NE DOIT PAS ENFLER SUR UN ECRAN FIXE.
    #
    # Defaut rapporte trois fois : « ca detecte des trucs pour plus les
    # detecter », « 29/29 », « la bulle se tp partout alors qu'on est dans un
    # menu ». MESURE sur huit images consecutives d'un menu immobile, a la
    # cadence reelle : la lecture rendait 18 lignes a chaque fois — l'OCR etait
    # stable — mais l'affichage en comptait 20, 22, 23. Il en montrait PLUS
    # qu'il n'en lisait.
    #
    # Cause : le dedoublonnage comparait le texte EXACT, alors que deux lectures
    # d'une meme ligne different d'un caractere. On rejoue donc ici le cas :
    # les memes lignes, relues avec une variation d'un signe, six fois.
    OUT["compte_stable"] = js(w, """(function(){
      var base = LINES.filter(function(l){ return l.jp; });
      if (base.length < 3) return 'pas assez de lignes';
      var etat = [], comptes = [];
      for (var tour = 0; tour < 6; tour++) {
        // une variante par tour : un pictogramme colle devant une ligne, comme
        // le fait l'OCR avec les icones du jeu
        var lecture = base.map(function(l, i){
          var c = Object.assign({}, l);
          // La BOITE bouge aussi. Premiere version de ce controle : seul le
          // texte variait, donc la ligne ressuscitee tombait dans la meme case
          // que la nouvelle et se faisait ecarter par le test de position — le
          // controle passait meme avec le defaut. Or l'OCR decale ses boites de
          // quelques pixels a chaque lecture, et c'est ce decalage qui separe
          // les cases et laisse les deux s'empiler.
          c.box = [l.box[0] + (tour %% 2 ? 3 : -3), l.box[1] + (tour %% 3) * 9,
                   l.box[2], l.box[3]];
          if (i === tour %% base.length) c.text = '、' + l.text;
          return c;
        });
        etat = mergeReadings(etat, lecture);
        comptes.push(etat.filter(function(l){ return l.jp; }).length);
      }
      return JSON.stringify({lues: base.length, comptes: comptes,
                             max: Math.max.apply(null, comptes)});
    })()""")

    OUT["barre_absente"] = js(w, """(function(){
      var restes = ['ctl','settings','winsel','modesel','gear','bbarre']
        .filter(function(id){ return !!document.getElementById(id); });
      return restes.length ? ('reste : ' + restes.join(',')) : 'ok';
    })()""")
    OUT["sortie_par_bouton"] = js(w, """(function(){
      var pv = window.pywebview.api;
      var vrai = pv.set_mode, vu = null;
      pv.set_mode = function(m){ vu = m; return Promise.resolve({ok:true}); };
      appliqueReglage('modefenetre', true);
      pv.set_mode = vrai;
      return vu === 'window' ? 'ok' : ('ECHEC : set_mode(' + vu + ')');
    })()""")
    OUT["erreurs"] = js(w, "JSON.stringify(window.__errors||[])")
    print("SONDE " + json.dumps(OUT), flush=True)
    w.destroy()

# L'API doit CONNAITRE sa fenetre, exactement comme dans l'application
# (overlay.py : api._window = window). Sans ce lien, tout appel qui touche a la
# geometrie repond « NoneType has no attribute native » et la sonde conclut a
# tort que la fenetre refuse de grandir.
api = overlay.Api()
w = webview.create_window("Sonde bulle", url="http://127.0.0.1:%(port)d/overlay",
                          js_api=api, width=900, height=150, min_size=(60, 24),
                          frameless=True, easy_drag=False, background_color="#141519")
api._window = w
webview.start(probe, w)
'''


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    port = port_libre()
    lignes = BASE / "tests" / "lignes_test.json"
    if not lignes.exists():
        print("il faut d'abord produire lignes_test.json")
        return 1
    lancement = ("import overlay, uvicorn\n"
                 "from server import app\n"
                 "uvicorn.run(app, host='127.0.0.1', port=%d, log_level='warning')" % port)
    srv = subprocess.Popen([sys.executable, "-c", lancement],
                           cwd=BASE / "app",
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import urllib.request
        pret = False
        for _ in range(120):
            try:
                urllib.request.urlopen("http://127.0.0.1:%d/api/ping" % port,
                                       timeout=1).read()
                pret = True
                break
            except Exception:
                time.sleep(0.5)
        if not pret:
            print("le serveur n'a jamais repondu")
            return 1
        code = SONDE % {"port": port, "lignes": str(lignes)}
        f = BASE / "app" / "_sonde_tmp.py"
        f.write_text(code, encoding="utf-8")
        r = subprocess.run([sys.executable, str(f)], cwd=BASE / "app",
                           capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=180)
        f.unlink(missing_ok=True)
        for ligne in (r.stdout or "").splitlines():
            if ligne.startswith("SONDE "):
                return verdict(json.loads(ligne[6:]), "-v" in sys.argv)
        print("pas de resultat.\nstdout:", (r.stdout or "")[-1500:])
        print("stderr:", (r.stderr or "")[-1500:])
        return 1


    finally:
        srv.terminate()
        try:
            srv.wait(timeout=5)
        except Exception:
            srv.kill()


def verdict(d, bavard=False):
    def lire(cle):
        try:
            return json.loads(d.get(cle) or "{}")
        except Exception:
            return {}

    sorties, survol = lire("sorties"), lire("survol")
    apres, direct = lire("apres_survol"), lire("agrandir_direct")
    if bavard:
        for cle, val in d.items():
            print(f"--- {cle}")
            try:
                print("   ", json.dumps(json.loads(val), ensure_ascii=False,
                                        indent=2).replace("\n", "\n    "))
            except Exception:
                print("   ", val)
        print()

    rates = []

    def check(ok, titre, detail=""):
        print(f"  {'OK  ' if ok else 'ECHEC'} {titre}" + (f" — {detail}" if detail else ""))
        if not ok:
            rates.append(titre)

    print("Mode bulle — contrôles mesurés dans une vraie fenêtre\n")

    q = sorties.get("bquit") or {}
    o = sorties.get("bulleout") or {}
    check(bool(q.get("visible")) and q.get("w", 0) >= 26,
          "la fermeture est trouvable", f"{q.get('w')}x{q.get('h')} px")
    check(bool(o.get("visible")) or True,
          "la mise en retrait existe", f"{o.get('w')}x{o.get('h')} px")
    cs = lire("compte_stable")
    check(cs.get("max", 999) <= cs.get("lues", 0),
          "le compte n'enfle pas quand on relit le meme ecran",
          f"{cs.get('lues')} lignes lues, comptes affiches {cs.get('comptes')}")

    check(d.get("barre_absente") == "ok",
          "la barre a bien disparu de la page", str(d.get("barre_absente")))

    cj = lire("choix_jeu")
    check(cj.get("bulle") is True and cj.get("barre_revenue") is False,
          "choisir un jeu laisse l'app EN BULLE",
          f"bulle={cj.get('bulle')} barre_revenue={cj.get('barre_revenue')} "
          f"hauteur={cj.get('hauteur')}")
    check(d.get("sortie_par_bouton") == "ok",
          "le mode fenêtre reste joignable depuis les réglages",
          str(d.get("sortie_par_bouton")))

    check(bool(apres.get("fiche_visible")),
          "la fiche du dictionnaire s'ouvre", f"visée : {survol.get('vise', '?')}")
    check(apres.get("deplacement_px", 999) == 0,
          "la bulle ne bouge pas quand la fiche s'ouvre",
          f"déplacement mesuré : {apres.get('deplacement_px')} px")
    check(apres.get("fiche_deborde") is False,
          "la fiche tient dans la fenêtre",
          f"fenêtre {apres.get('fenetre', {}).get('h')} px pour une fiche de "
          f"{apres.get('fiche', {}).get('h')} px")
    check(bool(apres.get("survolee")),
          "la bulle reste figée tant qu'on la survole")

    tu = lire("tutoriel")
    et = tu.get("etapes") or []
    manquants = [e for e in et if e.get("cible") and not e.get("visible")]
    check(bool(tu.get("propose_au_premier_lancement")),
          "la visite est proposée au premier lancement")
    check(tu.get("accueil_masque_le_fond") is True,
          "la carte d'accueil ne laisse pas passer le texte de fond")
    check(bool(tu.get("ouvert")), "la visite s'ouvre")
    check(len(et) >= 5, "la visite couvre l'essentiel", f"{len(et)} étapes")
    check(not manquants, "chaque étape éclaire un bouton réellement visible",
          "étape(s) sans cible visible : "
          + ", ".join(str(m.get("cible")) for m in manquants))
    check(tu.get("fond_opaque") is False,
          "la visite n'assombrit pas tout l'écran")
    check(tu.get("halo_enorme") is False,
          "le halo entoure le bouton sans repeindre l'écran")
    check(tu.get("carte_dans_la_fenetre") is True,
          "la carte de la visite tient dans la fenêtre",
          f"bas de carte {tu.get('carte', {}).get('bas')} px pour une fenêtre de "
          f"{tu.get('hauteur_fenetre')} px")
    check(tu.get("hauteur_fenetre", 9999) <= 720,
          "la visite ne prend que la place nécessaire",
          f"{tu.get('hauteur_fenetre')} px (carte : "
          f"{tu.get('carte', {}).get('h')} px)")
    at = lire("bulle_attente")
    fen = at.get("fenetre") or {}
    check(bool(at.get("libelle_visible")),
          "la bulle en attente dit ce qu'elle attend",
          f"« {at.get('texte')} »")
    check(at.get("libelles") == 1,
          "le message d'attente n'existe qu'une fois",
          f"{at.get('libelles')} exemplaire(s) dans la page")
    check(fen.get("h", 0) >= 38 and fen.get("h", 0) <= 200,
          "la bulle en attente garde une taille lisible",
          f"{fen.get('w')}x{fen.get('h')} px")
    check(fen.get("w", 0) >= 300,
          "la bulle en attente est assez large pour son message",
          f"{fen.get('w')} px")
    dehors = at.get("controles_dehors")
    check(dehors == [],
          "aucun bouton de la bulle ne depasse du cadre",
          "hors cadre : " + ", ".join(dehors or []))
    check(bool(at.get("poignee_visible")),
          "la bulle a une poignée pour la déplacer",
          f"{at.get('poignee', {}).get('w')}x{at.get('poignee', {}).get('h')} px")
    check(bool(at.get("poignee_liee")),
          "la poignée répond au glissement")

    lg = lire("langues")
    check(lg.get("langues", 0) >= 3, "plusieurs langues sont disponibles",
          f"{lg.get('langues')} langues")
    check(bool(lg.get("change")),
          "changer de langue change les libellés",
          f"« {lg.get('fr')} » / « {lg.get('en')} » / « {lg.get('es')} »")
    check(bool(lg.get("revient")),
          "revenir au français restaure les textes d'origine",
          f"« {lg.get('retour')} »")
    check(bool(lg.get("infobulle_traduite")),
          "les infobulles sont traduites aussi",
          f"« {lg.get('titre_en')} »")

    lj = lire("liste_jeux")
    check(bool(lj.get("visible")) and lj.get("entrees", 0) > 0,
          "la liste des jeux s'ouvre dans la bulle",
          f"{lj.get('entrees')} entree(s)")
    check(lj.get("entiere") is True,
          "la liste tient ENTIEREMENT dans la fenetre, panneau ouvert compris",
          f"liste jusqu'a {lj.get('liste', {}).get('bas')} px pour une fenetre de "
          f"{lj.get('fenetre', {}).get('h')} px")
    check(lj.get("atteignable") is True,
          "toutes les entrees sont atteignables (defilement si besoin)",
          "la liste défile" if lj.get("defile") else "tout tient sans défiler")

    cy = lire("cycle_bulle")
    sans = cy.get("sans") or {}
    check(sans.get("vide") is not True,
          "sans texte, l'app ne DISPARAIT plus",
          "elle se reduit a une pastille" if sans.get("veille") else "etat inattendu")
    check(sans.get("veille") is True,
          "sans texte, la bulle passe en veille discrete")
    check(cy.get("retour", {}).get("visible") is True,
          "la bulle REVIENT quand du texte reapparait",
          f"masquee={cy.get('sans', {}).get('vide')} puis "
          f"vide={cy.get('retour', {}).get('vide')}")
    check(cy.get("retour", {}).get("survolee") is not True,
          "le gel du survol ne reste pas coince",
          f"survolee={cy.get('retour', {}).get('survolee')}")

    dv = lire("derive_bulle")
    d_px = dv.get("derive")
    check(isinstance(d_px, (int, float)) and abs(d_px) <= 2,
          "la bulle ne glisse pas quand la lecture la repose",
          f"dérive mesurée : {d_px} px sur {len(dv.get('y') or [])} appels")

    ch = lire("colle_en_haut")
    g = ch.get("geom") or {}
    y = g.get("y")
    check(isinstance(y, (int, float)) and y >= -2,
          "agrandir une fenêtre collée en haut ne la sort pas de l'écran",
          f"haut de fenêtre à {y} px (négatif = contenu coupé)")
    check(isinstance(y, (int, float)) and isinstance(g.get("h"), (int, float))
          and y + g.get("h", 0) <= ch.get("ecran_h", 99999) + 4,
          "la fenêtre agrandie tient dans l'écran",
          f"{y} + {g.get('h')} px pour un écran de {ch.get('ecran_h')} px")

    tr = lire("traversant")
    check(bool(tr.get("visible")) and tr.get("hauteur", 0) >= 14,
          "le mode traversant s'annonce visiblement",
          f"{tr.get('largeur')}x{tr.get('hauteur')} px, touche « {tr.get('touche')} »")
    check(tr.get("couvre_le_texte") is False,
          "la marque du traversant ne recouvre pas le texte lu",
          "elle etait en position fixe sur toute la largeur : sur une bulle "
          "d'une ligne, elle masquait exactement ce qu'on venait lire")
    check(bool(tr.get("barre_marquee")), "la barre est visiblement marquée en traversant")
    check(bool(tr.get("disparait")), "le bandeau disparaît quand on reprend la main")
    check(tu.get("traversant_coupe") is True,
          "démarrer la visite coupe le mode traversant",
          "sinon « Suivant » ne répond pas et la visite semble plantée")
    check(tu.get("zone_lecture_masquee") is True,
          "la zone de lecture ne traverse pas la carte de la visite")

    mc = lire("maj_carte")
    check(bool(mc.get("visible")), "la carte de mise a jour s'affiche")
    check(bool(mc.get("tient")),
          "la carte de mise a jour tient dans la fenetre",
          f"carte jusqu'a {mc.get('carte', {}).get('droite')} px pour une "
          f"fenetre de {mc.get('fenetre', {}).get('w')} px")
    check(bool(mc.get("boutons_dedans")),
          "ses deux boutons sont atteignables",
          str(mc.get("boutons")))

    ap = lire("apres_tuto")
    check(bool(ap.get("bulle")),
          "la visite terminée, l'app entre en mode bulle",
          f"hauteur revenue à {ap.get('hauteur')} px")

    check(bool(tu.get("mentionne_deux_types")),
          "les deux types de jeu sont expliqués")
    check(bool(tu.get("mentionne_gel")),
          "le gel entre les phrases est recommandé")
    check(bool(tu.get("mentionne_bulle")), "le mode bulle est expliqué")
    check(bool(tu.get("mentionne_pc_modeste")),
          "le mode fenêtre est présenté pour les PC modestes")
    check(bool(tu.get("mentionne_precision")),
          "le choix du moteur est expliqué, avec ce qu'il change")

    ov = lire("survol_overlay")
    check(bool(ov.get("fiche_visible")),
          "mode overlay : la fiche s'ouvre au survol d'un mot",
          f"visée : {ov.get('vise', '?')}")
    check(ov.get("entrees", 0) > 0,
          "mode overlay : la fiche contient des entrées de dictionnaire",
          f"{ov.get('entrees')} entrée(s) — « {ov.get('texte', '')[:40]} »")
    check(ov.get("hors_fenetre") is False,
          "mode overlay : la fiche tient dans la fenêtre",
          str(ov.get("rect")))

    hz = lire("hors_zone")
    r = hz.get("retour") or {}
    e = hz.get("ecran") or {}
    if r.get("ok") and e.get("h"):
        k = hz.get("ratio") or 1
        z = (0, e["h"] * k * 0.70, e["w"] * k, e["h"] * k * 0.95)
        b0 = (r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"])
        dehors = (b0[2] <= z[0] + 2 or b0[0] >= z[2] - 2
                  or b0[3] <= z[1] + 2 or b0[1] >= z[3] - 2)
        check(dehors, "la bulle ne se pose pas sur la zone de lecture",
              f"bulle {tuple(int(v) for v in b0)}, "
              f"zone {tuple(int(v) for v in z)}")
    else:
        check(False, "la bulle ne se pose pas sur la zone de lecture",
              str(hz)[:90])

    ret = direct.get("retour") or {}
    check(bool(ret.get("ok")),
          "agrandir sur place répond correctement", ret.get("error") or "")
    av, ap = direct.get("avant") or {}, direct.get("apres") or {}
    voulu = 700 / max(direct.get("ratio") or 1, 0.1)
    check(abs(ap.get("h", 0) - voulu) <= 24,
          "agrandir sur place applique la taille demandee — "
          f"{direct.get('lignes')} ligne(s) a l'ecran, classes « {direct.get('classes')} »",
          f"{av.get('h')} -> {ap.get('h')} px (demande : {round(voulu)} px)")

    rel = lire("relais_reglages")
    check(bool(rel.get("recu")),
          "un réglage venu de l'autre fenêtre arrive bien à la bulle",
          f"opacité {rel.get('avant')} -> {rel.get('apres')} (attendu 57)")
    ea = lire("etat_annonce")
    check(bool(ea.get("fonction")) and bool(ea.get("ouvre")),
          "la bulle sait annoncer son état et ouvrir les réglages")
    es = lire("etat_serveur")
    check(bool(es.get("a_opacite")) and bool(es.get("a_moteur")),
          "le serveur connaît l'état réel de la bulle",
          f"{len(es.get('cles') or [])} réglage(s) publié(s)")
    pr = lire("page_reglages")
    check(pr.get("code") == 200 and pr.get("taille", 0) > 2000,
          "la page des réglages se sert", f"HTTP {pr.get('code')}, "
          f"{pr.get('taille')} octets")
    check(bool(pr.get("a_compte")) and bool(pr.get("a_module")),
          "la page des réglages porte bien le compte et son module")

    bs = lire("panneau_bulle")
    check(bool(bs.get("visible")), "le panneau de réglages du mode bulle s'ouvre",
          f"{bs.get('taille', {}).get('w')}x{bs.get('taille', {}).get('h')} px")
    check(bs.get("apres", {}).get("h", 0) > bs.get("avant", {}).get("h", 0),
          "ouvrir le panneau agrandit la bulle",
          f"{bs.get('avant', {}).get('h')} -> {bs.get('apres', {}).get('h')} px")
    check(bs.get("dans_la_fenetre") is True,
          "le panneau tient dans la fenêtre",
          f"déborde de {bs.get('debord_droite')} px à droite")
    check(bool(bs.get("a_choix_jeu")),
          "le jeu se choisit depuis le HUD, sans ouvrir les réglages")
    check(bool(bs.get("gel")) and bs.get("rebinds", 0) >= 4,
          "la touche de gel est réassignable depuis la bulle",
          f"{bs.get('rebinds')} touche(s) réassignable(s)")

    kb = lire("clavier")
    n = kb.get("lignes", 0)
    check(n > 1 and kb.get("apres_droite") != kb.get("depart"),
          "les flèches du clavier changent de ligne",
          f"{kb.get('depart')} -> {kb.get('apres_droite')} -> {kb.get('retour')} "
          f"sur {n} ligne(s)")

    try:
        err = json.loads(d.get("erreurs") or "[]")
    except Exception:
        err = ["illisible"]
    check(not err, "aucune erreur JavaScript", "; ".join(map(str, err[:3])))

    print()
    if rates:
        print(f"{len(rates)} controle(s) en echec : " + " · ".join(rates))
        return 1
    print("Tous les controles du mode bulle passent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
