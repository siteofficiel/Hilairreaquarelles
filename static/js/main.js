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
