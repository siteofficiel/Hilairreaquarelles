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
      var show = f === "*" || cat === f;
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
