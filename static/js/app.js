/* Hilaire Legentil — interactions du site public */
(function () {
  "use strict";

  /* --- en-tête : état scrollé ------------------------------------- */
  var header = document.getElementById("site-header");
  function onScroll() {
    if (!header) return;
    header.classList.toggle("is-scrolled", window.scrollY > 40);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* --- menu mobile ------------------------------------------------ */
  var toggle = document.getElementById("nav-toggle");
  var nav = document.getElementById("site-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      document.body.classList.toggle("nav-open", open);
    });
    nav.addEventListener("click", function (e) {
      if (e.target.closest("a")) {
        nav.classList.remove("is-open");
        toggle.setAttribute("aria-expanded", "false");
        document.body.classList.remove("nav-open");
      }
    });
  }

  /* --- apparition progressive ------------------------------------- */
  var els = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && els.length) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add("is-visible");
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -4% 0px" });
    els.forEach(function (el) { io.observe(el); });
  } else {
    els.forEach(function (el) { el.classList.add("is-visible"); });
  }

  /* --- horodatage anti-spam du formulaire -------------------------- */
  var ts = document.getElementById("form-ts");
  if (ts) ts.value = Math.floor(Date.now() / 1000);

  /* --- messages flash : disparition douce -------------------------- */
  document.querySelectorAll(".flash").forEach(function (f) {
    setTimeout(function () {
      f.style.transition = "opacity .6s, transform .6s";
      f.style.opacity = "0";
      f.style.transform = "translateY(8px)";
      setTimeout(function () { f.remove(); }, 700);
    }, 6000);
  });
})();

/* Galerie : filtres en menus déroulants + tri automatique des œuvres */
(function () {
  "use strict";
  var root = document.getElementById("hl-filters");
  var grid = document.getElementById("gallery-grid");
  if (!root || !grid) return;

  var items = Array.prototype.slice.call(grid.querySelectorAll(".work"));
  items.forEach(function (it, i) { it.setAttribute("data-idx", String(i)); });
  var countEl = document.getElementById("gallery-count");
  var chipsEl = document.getElementById("hl-chips");
  var resetBtn = document.getElementById("hl-reset");
  var ATTR = { sujet: "data-sujet", ambiance: "data-amb",
               technique: "data-tech", annee: "data-year" };
  var LABELS = { sujet: "Sujet", ambiance: "Ambiance",
                 technique: "Technique", annee: "Année" };
  var GROUPS = ["sujet", "ambiance", "technique", "annee"];
  var state = { sujet: "", ambiance: "", technique: "", annee: "", sort: "gallery" };

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function yearOf(it) { return parseInt(it.getAttribute("data-year"), 10) || 0; }

  /* ---- menus déroulants : ouverture, clavier, sélection ---- */
  var dds = [];
  function closeAll() {
    dds.forEach(function (dd) {
      dd.classList.remove("is-open");
      var b = dd.querySelector(".hl-dd-btn");
      if (b) b.setAttribute("aria-expanded", "false");
    });
  }
  root.querySelectorAll(".hl-dd").forEach(function (dd) {
    var btn = dd.querySelector(".hl-dd-btn");
    var menu = dd.querySelector(".hl-dd-menu");
    if (!btn || !menu) return;
    dds.push(dd);
    btn.addEventListener("click", function () {
      var open = dd.classList.contains("is-open");
      closeAll();
      if (!open) { dd.classList.add("is-open"); btn.setAttribute("aria-expanded", "true"); }
    });
    menu.addEventListener("click", function (e) {
      var opt = e.target.closest(".hl-dd-opt");
      if (!opt) return;
      select(dd.getAttribute("data-g"), opt.getAttribute("data-v"));
      closeAll();
      btn.focus();
    });
    menu.addEventListener("keydown", function (e) {
      var opts = Array.prototype.slice.call(menu.querySelectorAll(".hl-dd-opt"));
      if (e.key === "Escape") { e.preventDefault(); closeAll(); btn.focus(); }
      else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        var i = opts.indexOf(document.activeElement);
        var n = e.key === "ArrowDown"
          ? (i < 0 ? 0 : Math.min(i + 1, opts.length - 1))
          : (i < 0 ? opts.length - 1 : Math.max(i - 1, 0));
        if (opts[n]) opts[n].focus();
      }
      else if (e.key === "Home") { e.preventDefault(); if (opts[0]) opts[0].focus(); }
      else if (e.key === "End") { e.preventDefault(); if (opts.length) opts[opts.length - 1].focus(); }
    });
    dd.addEventListener("focusout", function (e) {
      if (!dd.contains(e.relatedTarget)) {
        dd.classList.remove("is-open");
        btn.setAttribute("aria-expanded", "false");
      }
    });
  });
  document.addEventListener("click", function (e) {
    if (!document.body.contains(root)) return;
    if (!root.contains(e.target)) closeAll();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeAll();
  });

  function select(g, v) {
    if (g === "sort") { state.sort = v || "gallery"; }
    else { state[g] = v || ""; }
    syncDD(g);
    apply();
  }
  function syncDD(g) {
    var dd = root.querySelector('.hl-dd[data-g="' + g + '"]');
    if (!dd) return;
    var val = g === "sort" ? state.sort : (state[g] || "");
    var chosen = null;
    dd.querySelectorAll(".hl-dd-opt").forEach(function (o) {
      var sel = o.getAttribute("data-v") === val;
      o.classList.toggle("is-sel", sel);
      o.setAttribute("aria-selected", sel ? "true" : "false");
      if (sel) chosen = o;
    });
    var lab = dd.querySelector(".hl-dd-val");
    if (lab && chosen) lab.textContent = chosen.getAttribute("data-l") || chosen.textContent;
    dd.classList.toggle("is-set", g !== "sort" && !!state[g]);
  }

  /* ---- filtrage + tri automatique : la grille se réorganise seule ---- */
  function apply() {
    var visible = items.filter(function (it) {
      for (var gi = 0; gi < GROUPS.length; gi++) {
        var g = GROUPS[gi];
        if (state[g] && (it.getAttribute(ATTR[g]) || "").trim() !== state[g]) return false;
      }
      return true;
    });
    visible.sort(function (a, b) {
      var ia = +a.getAttribute("data-idx"), ib = +b.getAttribute("data-idx");
      if (state.sort === "recent") { return (yearOf(b) - yearOf(a)) || (ib - ia); }
      if (state.sort === "old") { return (yearOf(a) - yearOf(b)) || (ia - ib); }
      return ia - ib;
    });
    items.forEach(function (it) {
      it.classList.remove("hl-in");
      it.style.display = visible.indexOf(it) < 0 ? "none" : "";
    });
    void grid.offsetWidth; /* relance la douce animation d'entrée */
    visible.forEach(function (it) { grid.appendChild(it); it.classList.add("hl-in"); });

    var n = visible.length;
    if (countEl) {
      countEl.textContent = n === 0
        ? "Aucune aquarelle ne correspond à cette combinaison de filtres."
        : n + (n > 1 ? " œuvres" : " œuvre");
      countEl.classList.toggle("is-empty", n === 0);
    }
    if (chipsEl) {
      chipsEl.innerHTML = GROUPS.filter(function (g) { return state[g]; })
        .map(function (g) {
          return '<button type="button" class="hl-fchip" data-g="' + g + '"' +
            ' aria-label="Retirer le filtre ' + esc(LABELS[g] + " : " + state[g]) + '">' +
            esc(LABELS[g]) + '&nbsp;: ' + esc(state[g]) +
            '<span class="hl-fx" aria-hidden="true">×</span></button>';
        }).join("");
    }
    var active = GROUPS.some(function (g) { return state[g]; });
    if (resetBtn) resetBtn.hidden = !active;
    root.classList.toggle("is-filtered", active);
  }

  if (chipsEl) {
    chipsEl.addEventListener("click", function (e) {
      var chip = e.target.closest(".hl-fchip");
      if (!chip) return;
      select(chip.getAttribute("data-g"), "");
    });
  }
  if (resetBtn) {
    resetBtn.addEventListener("click", function () {
      GROUPS.forEach(function (g) { state[g] = ""; syncDD(g); });
      apply();
      resetBtn.focus();
    });
  }

  /* ---- bouton de tri : chaque clic change l'ordre des œuvres ---- */
  var sortBtn = root.querySelector("#hl-sort");
  if (sortBtn) {
    var SORTS = [["gallery", "Ordre de la galerie"],
                 ["recent", "Plus récentes d'abord"],
                 ["old", "Plus anciennes d'abord"]];
    var sortLab = sortBtn.querySelector(".hl-sort-val");
    sortBtn.addEventListener("click", function () {
      var cur = 0;
      SORTS.forEach(function (sv, k) { if (sv[0] === state.sort) cur = k; });
      var nx = SORTS[(cur + 1) % SORTS.length];
      state.sort = nx[0];
      apply();
      if (sortLab) sortLab.textContent = nx[1];
      sortBtn.setAttribute("title", "Tri actuel : " + nx[1] + " — cliquer pour changer");
    });
  }

  apply();
})();

/* carte : voir bloc conformité en fin de fichier (chargement après consentement) */

/* Administration : confirmations & aperçus d'images */
(function () {
  "use strict";

  /* confirmation avant suppression */
  document.querySelectorAll("form.js-confirm").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      var msg = f.getAttribute("data-confirm") || "Confirmer cette action ?";
      if (!window.confirm(msg)) e.preventDefault();
    });
  });

  /* aperçu local du fichier choisi */
  document.querySelectorAll(".file-input[data-preview]").forEach(function (input) {
    input.addEventListener("change", function () {
      var img = document.getElementById(input.getAttribute("data-preview"));
      var hint = document.getElementById(input.getAttribute("data-hint"));
      var file = input.files && input.files[0];
      if (!file || !img) return;
      img.src = URL.createObjectURL(file);
      img.hidden = false;
      if (hint) hint.textContent = "Aperçu de : " + file.name;
    });
  });
})();



/* ═══════════ Mesure d'audience : uniquement après consentement (CNIL) ═══════════ */
window.hlGaLoad = function () {
  if (window.__hlGaDone) return;
  var d = document.getElementById("hl-wdata");
  var id = d ? (d.getAttribute("data-ga") || "").trim() : "";
  if (!id) return;
  window.__hlGaDone = true;
  var s = document.createElement("script");
  s.async = true;
  s.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(id);
  document.head.appendChild(s);
  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { dataLayer.push(arguments); };
  gtag("js", new Date());
  gtag("config", id, { anonymize_ip: true });
};

/* ═══════════ Conformité cookies — choix par catégorie, preuve datée, 6 mois ═══════════ */
function hlConsent() {
  var m = document.cookie.match(/(?:^|;\s*)hl_consent=([^;]+)/);
  var v = m ? decodeURIComponent(m[1]) : "";
  if (v === "oui") return { done: true, map: true, ga: true, off: true };
  if (v === "non") return { done: true, map: false, ga: false, off: true };
  try {
    var j = JSON.parse(v);
    if (j && j.done) return { done: true, map: !!j.map, ga: !!j.ga, off: !!j.off };
  } catch (e) {}
  return { done: false, map: false, ga: false, off: false };
}
function hlSaveConsent(map, ga, off) {
  var val = encodeURIComponent(JSON.stringify({ done: true, map: !!map, ga: !!ga, off: !!off, ts: Date.now() }));
  document.cookie = "hl_consent=" + val + ";max-age=15552000;path=/;samesite=lax";
}
function hlGaOn() {
  var d = document.getElementById("hl-wdata");
  return !!(d && (d.getAttribute("data-ga") || "").trim());
}
function hlApplyConsent() {
  var c = hlConsent();
  var bar = document.getElementById("cookie-bar");
  /* bandeau masqué dès qu'un choix existe — sauf nouvelle finalité jamais arbitrée */
  if (bar) bar.hidden = !(!c.done || (hlGaOn() && !c.off));
  var m = document.getElementById("ck-map"), g = document.getElementById("ck-ga");
  if (c.done) {
    if (m) m.checked = c.map;
    if (g) g.checked = c.ga;
    if (c.map && typeof window.hlMapMount === "function") window.hlMapMount();
    if (c.ga && hlGaOn() && typeof window.hlGaLoad === "function") window.hlGaLoad();
  }
}
(function () {
  var bar = document.getElementById("cookie-bar");
  if (!bar) return;
  var gaOn = hlGaOn();
  if (gaOn) { var grow = document.getElementById("ck-ga-row"); if (grow) grow.hidden = false; }
  hlApplyConsent();
  var a = document.getElementById("ck-accept");
  var r = document.getElementById("ck-refuse");
  var cu = document.getElementById("ck-custom");
  var opts = document.getElementById("cookie-opts");
  var sv = document.getElementById("ck-save");
  if (a) a.addEventListener("click", function () { hlSaveConsent(true, true, gaOn); hlApplyConsent(); });
  if (r) r.addEventListener("click", function () { hlSaveConsent(false, false, gaOn); hlApplyConsent(); });
  if (cu) cu.addEventListener("click", function () {
    var open = !!(opts && opts.hidden);
    if (opts) opts.hidden = !open;
    cu.setAttribute("aria-expanded", open ? "true" : "false");
  });
  if (sv) sv.addEventListener("click", function () {
    var m = document.getElementById("ck-map");
    var g = document.getElementById("ck-ga");
    hlSaveConsent(m ? m.checked : true, gaOn && g ? g.checked : false, gaOn);
    hlApplyConsent();
  });
})();

/* ═══════════ Carte : chargement uniquement après accord ═══════════ */
window.hlMapMount = function () {
  var el = document.getElementById("map");
  if (!el || el.dataset.mapInit || typeof L === "undefined") return;
  el.dataset.mapInit = "1";
  el.hidden = false;
  var center = [49.4894, -1.5048];
  var map = L.map(el, { scrollWheelZoom: false }).setView(center, 8);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(map);
  L.circle(center, { radius: 75000, color: "#1a9d9a", weight: 1.6, opacity: 0.9,
    fillColor: "#1a9d9a", fillOpacity: 0.10 }).addTo(map);
  L.circle(center, { radius: 2000, color: "#11596a", weight: 1.2,
    fillColor: "#11596a", fillOpacity: 0.55 }).addTo(map);
  var icon = L.divIcon({ className: "",
    html: "<div style=\"width:14px;height:14px;border-radius:50%;background:#11596a;border:3px solid #faf8f3;box-shadow:0 0 0 2px #1a9d9a\"></div>",
    iconSize: [14, 14], iconAnchor: [7, 7] });
  L.marker(center, { icon: icon, title: "Yvetot-Bocage — Normandie" }).addTo(map)
    .bindPopup("<strong>Yvetot-Bocage</strong><br>Manche — Normandie<br><em>Zone d’environ 75 km autour</em>");
  map.on("click", function () { map.scrollWheelZoom.enable(); });
  map.on("mouseout", function () { map.scrollWheelZoom.disable(); });
};
(function () {
  var c = hlConsent();
  var gate = document.getElementById("map-consent");
  if (c.done && c.map) { window.hlMapMount(); return; }
  if (gate) {
    gate.hidden = false;
    var b = document.getElementById("map-load");
    if (b) b.addEventListener("click", function () {
      var cur = hlConsent();
      /* « Charger la carte » = accord pour la carte SEULE (pas pour l'audience) */
      hlSaveConsent(true, cur.done && cur.ga, cur.off);
      gate.hidden = true;
      window.hlMapMount();
      hlApplyConsent();
    });
  }
})();

/* ------------------------------------------------- visionneuse atelier */
(function () {
  "use strict";
  var grid = document.getElementById("atelier-grid");
  if (!grid) return;
  var btns = [].slice.call(grid.querySelectorAll(".atelier-btn"));
  if (!btns.length) return;
  var capPre = grid.getAttribute("data-cap") || "Atelier";
  var idx = 0;
  var lb = document.createElement("div");
  lb.className = "hl-lightbox"; lb.hidden = true;
  lb.setAttribute("role", "dialog"); lb.setAttribute("aria-modal", "true");
  lb.setAttribute("aria-label", "Photo agrandie");
  lb.innerHTML = '<figure><img alt=""><figcaption></figcaption></figure>' +
    '<button type="button" class="hl-lb-btn hl-lb-prev" aria-label="Photo précédente">\u2039</button>' +
    '<button type="button" class="hl-lb-btn hl-lb-next" aria-label="Photo suivante">\u203A</button>' +
    '<button type="button" class="hl-lb-close" aria-label="Fermer">\u2715</button>';
  document.body.appendChild(lb);
  if (btns.length === 1) lb.classList.add("hl-lb-single");
  var img = lb.querySelector("img"), cap = lb.querySelector("figcaption");
  var prev = lb.querySelector(".hl-lb-prev"), next = lb.querySelector(".hl-lb-next");
  var closer = lb.querySelector(".hl-lb-close");
  function show(i) {
    idx = (i + btns.length) % btns.length;
    var b = btns[idx], t = b.querySelector("img");
    img.src = b.getAttribute("data-full") || t.src;
    img.alt = t.alt;
    cap.textContent = capPre + " \u2014 " + (idx + 1) + " / " + btns.length;
    lb.hidden = false;
    document.documentElement.style.overflow = "hidden";
    closer.focus();
  }
  function close() {
    lb.hidden = true;
    document.documentElement.style.overflow = "";
    if (btns[idx]) btns[idx].focus();
  }
  btns.forEach(function (b, i) { b.addEventListener("click", function () { show(i); }); });
  prev.addEventListener("click", function () { show(idx - 1); });
  next.addEventListener("click", function () { show(idx + 1); });
  closer.addEventListener("click", close);
  lb.addEventListener("click", function (e) { if (e.target === lb) close(); });
  document.addEventListener("keydown", function (e) {
    if (lb.hidden) return;
    if (e.key === "Escape") close();
    else if (e.key === "ArrowLeft") show(idx - 1);
    else if (e.key === "ArrowRight") show(idx + 1);
  });
})();

/* --------------------------------------------- carrousels (œuvre & accueil) */
(function () {
  "use strict";
  var car = document.getElementById("wk-carousel");
  if (car) {
    var track = car.querySelector(".wk-track");
    var imgs = [].slice.call(track ? track.children : []);
    var prev = car.querySelector(".wk-prev"), next = car.querySelector(".wk-next");
    var dots = car.querySelector(".wk-dots");
    var i = 0;
    var show = function (k) {
      i = (k + imgs.length) % imgs.length;
      if (track) track.style.transform = "translateX(-" + i * 100 + "%)";
      if (dots) [].forEach.call(dots.children, function (d, n) {
        d.className = n === i ? "on" : "";});
    };
    if (imgs.length > 1) {
      if (dots) imgs.forEach(function (im, k) {
        var d = document.createElement("button");
        d.type = "button";
        d.className = "wk-dot" + (k === 0 ? " on" : "");
        d.setAttribute("aria-label", "Voir l\u2019image " + (k + 1));
        var src = im.querySelector("img");
        if (src) d.style.backgroundImage = "url('" + (src.currentSrc || src.src) + "')";
        d.addEventListener("click", function () { show(k); });
        dots.appendChild(d);
      });
      if (prev) prev.addEventListener("click", function () { show(i - 1); });
      if (next) next.addEventListener("click", function () { show(i + 1); });
      var x0 = null;
      car.addEventListener("touchstart", function (e) { x0 = e.touches[0].clientX; },
                           { passive: true });
      car.addEventListener("touchend", function (e) {
        if (x0 === null) return;
        var dx = e.changedTouches[0].clientX - x0;
        if (Math.abs(dx) > 40) show(dx < 0 ? i + 1 : i - 1);
        x0 = null;
      });
    }

    /* navigation clavier sur le carrousel */
    car.addEventListener("keydown", function (e) {
      if (!lb.hidden) return;
      if (e.key === "ArrowLeft") { show(i - 1); e.preventDefault(); }
      else if (e.key === "ArrowRight") { show(i + 1); e.preventDefault(); }
    });

    /* visionneuse plein écran — jamais de recadrage */
    var lb = document.createElement("div");
    lb.className = "hl-lightbox"; lb.hidden = true;
    lb.setAttribute("role", "dialog"); lb.setAttribute("aria-modal", "true");
    lb.setAttribute("aria-label", "Image agrandie");
    lb.innerHTML = '<figure><img alt=""></figure>' +
      '<button type="button" class="hl-lb-btn hl-lb-prev" aria-label="Image précédente">\u2039</button>' +
      '<button type="button" class="hl-lb-btn hl-lb-next" aria-label="Image suivante">\u203A</button>' +
      '<button type="button" class="hl-lb-close" aria-label="Fermer">\u2715</button>';
    document.body.appendChild(lb);
    if (imgs.length < 2) lb.classList.add("hl-lb-single");
    var zimg = lb.querySelector("img"),
        zprev = lb.querySelector(".hl-lb-prev"),
        znext = lb.querySelector(".hl-lb-next"),
        zclose = lb.querySelector(".hl-lb-close");
    function zshow(k) {
      show(k);
      var im = imgs[i] && imgs[i].querySelector("img");
      if (im) { zimg.src = im.currentSrc || im.src; zimg.alt = im.alt; }
      lb.hidden = false;
      document.documentElement.style.overflow = "hidden";
      zclose.focus();
    }
    function zhide() { lb.hidden = true; document.documentElement.style.overflow = ""; }
    var zoomBtn = car.querySelector(".wk-zoom");
    if (zoomBtn) zoomBtn.addEventListener("click", function () { zshow(i); });
    if (track) track.addEventListener("click", function () { zshow(i); });
    zprev.addEventListener("click", function () { zshow(i - 1); });
    znext.addEventListener("click", function () { zshow(i + 1); });
    zclose.addEventListener("click", zhide);
    lb.addEventListener("click", function (e) { if (e.target === lb) zhide(); });
    document.addEventListener("keydown", function (e) {
      if (lb.hidden) return;
      if (e.key === "Escape") zhide();
      else if (e.key === "ArrowLeft") zshow(i - 1);
      else if (e.key === "ArrowRight") zshow(i + 1);
    });
  }
  var row = document.getElementById("flip-row");
  if (row) {
    var step = function () { return Math.max(240, row.clientWidth * .8); };
    var bp = document.getElementById("flip-prev"), bn = document.getElementById("flip-next");
    if (bp) bp.addEventListener("click", function () {
      row.scrollBy({ left: -step(), behavior: "smooth" }); });
    if (bn) bn.addEventListener("click", function () {
      row.scrollBy({ left: step(), behavior: "smooth" }); });
  }
})();


/* --------------------------------------------- carrousel d'images (accueil) */
(function () {
  "use strict";
  var car = document.getElementById("hc-carousel");
  if (!car) return;
  var imgs = [].slice.call(car.querySelectorAll(".hc-img"));
  if (!imgs.length) return;
  var prev = car.querySelector(".wk-prev"), next = car.querySelector(".wk-next");
  var dots = car.querySelector(".wk-dots");
  var i = 0, timer = null, hovering = false;
  function show(k) {
    i = (k + imgs.length) % imgs.length;
    imgs.forEach(function (im, n) { im.className = "hc-img" + (n === i ? " on" : ""); });
    if (dots) [].forEach.call(dots.children, function (d, n) {
      d.className = "wk-dot" + (n === i ? " on" : ""); });
  }
  if (dots) imgs.forEach(function (im, k) {
    var d = document.createElement("button");
    d.type = "button";
    d.className = "wk-dot" + (k ? "" : " on");
    d.setAttribute("aria-label", "Voir l\u2019image " + (k + 1));
    if (im.tagName === "IMG") d.style.backgroundImage = "url('" + (im.currentSrc || im.src) + "')";
    d.addEventListener("click", function () { show(k); restart(); });
    dots.appendChild(d);
  });
  if (prev) prev.addEventListener("click", function () { show(i - 1); restart(); });
  if (next) next.addEventListener("click", function () { show(i + 1); restart(); });
  var x0 = null;
  car.addEventListener("touchstart", function (e) { x0 = e.touches[0].clientX; },
                       { passive: true });
  car.addEventListener("touchend", function (e) {
    if (x0 === null) return;
    var dx = e.changedTouches[0].clientX - x0;
    if (Math.abs(dx) > 40) show(dx < 0 ? i + 1 : i - 1);
    x0 = null; restart();
  });
  function tick() { if (!hovering) show(i + 1); }
  function restart() { if (timer) clearInterval(timer); timer = setInterval(tick, 5500); }
  car.addEventListener("mouseenter", function () { hovering = true; });
  car.addEventListener("mouseleave", function () { hovering = false; });
  car.addEventListener("focusin", function () { hovering = true; });
  car.addEventListener("focusout", function () { hovering = false; });
  restart();
})();

/* ═══════════ Notifications : nouvelles aquarelles mises en ligne ═══════════ */
/* Mémoire locale (rien n'est envoyé, aucun compte, aucun cookie de plus).  */
(function () {
  "use strict";
  var data = document.getElementById("hl-wdata");
  if (!data) return;
  var slugs = (data.getAttribute("data-works") || "").split(",").filter(Boolean);
  if (!slugs.length) return;

  function lsGet(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { window.localStorage.setItem(k, v); } catch (e) {} }
  function ssGet(k) { try { return window.sessionStorage.getItem(k); } catch (e) { return null; } }
  function ssSet(k, v) { try { window.sessionStorage.setItem(k, v); } catch (e) {} }
  function getSeen() {
    try {
      var v = JSON.parse(lsGet("hlSeen") || "null");
      return Array.isArray(v) ? v : null;
    } catch (e) { return null; }
  }

  var grid = document.getElementById("gallery-grid");
  var seen = getSeen();
  var fresh = seen ? slugs.filter(function (s) { return seen.indexOf(s) < 0; }) : [];

  if (grid) {
    /* page galerie : badge sur les œuvres jamais vues, puis mémoire à jour */
    grid.querySelectorAll(".work").forEach(function (card) {
      var m = (/\/galerie\/([^/?#]+)/.exec(card.getAttribute("href") || "") || [])[1];
      if (m && fresh.indexOf(decodeURIComponent(m)) >= 0) {
        var b = document.createElement("span");
        b.className = "hl-new-badge";
        b.textContent = "Nouvelle aquarelle";
        card.insertBefore(b, card.firstChild);
      }
    });
    lsSet("hlSeen", JSON.stringify(slugs));
    return;
  }

  if (!seen) { lsSet("hlSeen", JSON.stringify(slugs)); return; } /* première visite */
  if (!fresh.length || ssGet("hlToastDone") === "1") return;

  ssSet("hlToastDone", "1");
  var t = document.createElement("div");
  t.className = "hl-toast";
  t.setAttribute("role", "status");
  t.innerHTML =
    '<p class="hl-toast-label">Galerie</p>' +
    '<p class="hl-toast-title">' + (fresh.length === 1
      ? "1 nouvelle aquarelle en ligne"
      : fresh.length + " nouvelles aquarelles en ligne") + '</p>' +
    '<p class="hl-toast-sub">Depuis votre dernière visite.</p>' +
    '<a class="hl-toast-cta" href="' + (data.getAttribute("data-galerie") || "/galerie") + '">Découvrir</a>' +
    '<button type="button" class="hl-toast-x" aria-label="Fermer la notification">&times;</button>';
  document.body.appendChild(t);
  requestAnimationFrame(function () { t.classList.add("is-in"); });
  var closeToast = function () {
    t.classList.remove("is-in");
    setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, 500);
  };
  var x = t.querySelector(".hl-toast-x");
  if (x) x.addEventListener("click", closeToast);
  var cta = t.querySelector(".hl-toast-cta");
  if (cta) cta.addEventListener("click", closeToast);
  var ck = document.getElementById("cookie-bar");
  if (ck && !ck.hidden) t.style.bottom = (ck.offsetHeight + 26) + "px";
})();

/* ═══════════ Alertes navigateur — nouvelles aquarelles (Web Push) ═══════════ */
(function () {
  "use strict";
  var wrap = document.getElementById("hl-bell-wrap");
  var btn = document.getElementById("hl-bell");
  if (!wrap || !btn) return;
  /* le bouton n'apparaît que si le navigateur sait recevoir des pushes */
  if (!("serviceWorker" in navigator) || !("PushManager" in window) ||
      !("Notification" in window) || !window.isSecureContext) return;
  wrap.hidden = false;

  var state = document.getElementById("hl-bell-state");
  var KEY = btn.getAttribute("data-vapid") || "";
  function say(txt, ok) {
    if (!state) return;
    state.textContent = txt;
    state.className = "hl-bell-state" + (ok === undefined ? "" : ok ? " is-ok" : " is-off");
  }
  function b64u(s) {
    var pad = "=".repeat((4 - s.length % 4) % 4);
    var b64 = (s + pad).replace(/-/g, "+").replace(/_/g, "/");
    var raw = atob(b64), arr = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
    return arr;
  }
  function saveSub(sub) {
    return fetch("/push/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sub.toJSON())
    }).then(function (r) { if (!r.ok) throw new Error("save"); });
  }
  function activate(reg) {
    return reg.pushManager.getSubscription().then(function (sub) {
      return sub || reg.pushManager.subscribe(
        { userVisibleOnly: true, applicationServerKey: b64u(KEY) });
    }).then(function (sub) {
      return saveSub(sub).then(function () { return sub; });
    });
  }
  function on() {
    btn.classList.add("is-on");
    btn.querySelector(".hl-bell-txt").textContent = "Alertes activées";
    say("Vous serez averti dans ce navigateur à chaque nouvelle aquarelle.", true);
  }

  /* état au chargement : déjà abonné ? */
  navigator.serviceWorker.register("/sw.js").then(function (reg) {
    return reg.pushManager.getSubscription();
  }).then(function (sub) {
    if (sub && Notification.permission === "granted") {
      return saveSub(sub).then(function () { on(); }).catch(function () {});
    }
  }).catch(function () {});

  btn.addEventListener("click", function () {
    if (btn.classList.contains("is-on")) return;
    say("Demande d'autorisation en cours…");
    Notification.requestPermission().then(function (p) {
      if (p !== "granted") {
        say("Notifications refusées — vous pouvez les réactiver dans les réglages du navigateur.", false);
        return;
      }
      navigator.serviceWorker.register("/sw.js")
        .then(activate)
        .then(on)
        .catch(function () {
          say("Impossible d'activer les alertes pour le moment.", false);
        });
    });
  });
})();