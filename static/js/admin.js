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
