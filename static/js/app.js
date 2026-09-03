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

/* Galerie : filtrage par catégorie, en douceur */
(function () {
  "use strict";
  var bar = document.querySelector(".filter-bar");
  var grid = document.getElementById("gallery-grid");
  if (!bar || !grid) return;

  var items = Array.prototype.slice.call(grid.querySelectorAll(".work"));
  var count = document.getElementById("gallery-count");
  var total = items.length;

  bar.addEventListener("click", function (e) {
    var btn = e.target.closest(".filter-btn");
    if (!btn) return;
    bar.querySelectorAll(".filter-btn").forEach(function (b) {
      b.classList.toggle("is-active", b === btn);
    });
    var f = btn.getAttribute("data-filter");
    var visible = 0;
    items.forEach(function (it) {
      var cat = (it.getAttribute("data-category") || "").trim();
      var tn = (it.getAttribute("data-tn") || "").trim();
      var show = f === "*" || (f.indexOf("tn:") === 0 ? tn === f.slice(3) : cat === f);
      if (show) visible++;
      it.style.display = show ? "" : "none";
    });
    if (count) count.textContent = visible + (visible > 1 ? " œuvres" : " œuvre");
  });

  /* catégories portées par les cartes (remplies côté serveur plus tard) */
  items.forEach(function (it) {
    var meta = it.querySelector(".work-meta");
    if (!it.getAttribute("data-category") && meta) {
      it.setAttribute("data-category", meta.textContent.split("·")[0].trim());
    }
  });
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



/* ═══════════ Conformité cookies — choix mémorisé 6 mois ═══════════ */
function hlConsent() {
  var m = document.cookie.match(/(?:^|;\s*)hl_consent=(oui|non)/);
  return m ? m[1] : null;
}
function hlSetConsent(v) {
  document.cookie = "hl_consent=" + v + ";max-age=15552000;path=/;samesite=lax";
  var bar = document.getElementById("cookie-bar");
  if (bar) bar.hidden = true;
  if (v === "oui") window.hlMapMount();
}
(function () {
  var bar = document.getElementById("cookie-bar");
  if (!bar) return;
  var a = document.getElementById("ck-accept");
  var r = document.getElementById("ck-refuse");
  if (a) a.addEventListener("click", function () { hlSetConsent("oui"); });
  if (r) r.addEventListener("click", function () { hlSetConsent("non"); });
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
  var gate = document.getElementById("map-consent");
  if (hlConsent() === "oui") { window.hlMapMount(); return; }
  if (gate) {
    gate.hidden = false;
    var b = document.getElementById("map-load");
    if (b) b.addEventListener("click", function () {
      hlSetConsent("oui");
      gate.hidden = true;
      window.hlMapMount();
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
