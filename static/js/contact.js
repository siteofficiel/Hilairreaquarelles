/* Page contact : carte interactive — zone de ~75 km autour d'Yvetot-Bocage */
(function () {
  "use strict";
  var el = document.getElementById("map");
  if (!el || typeof L === "undefined") return;

  var center = [49.4894, -1.5048];            // Yvetot-Bocage (Manche)
  var map = L.map(el, { scrollWheelZoom: false }).setView(center, 8);

  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(map);

  /* cercle de 75 km */
  L.circle(center, {
    radius: 75000,
    color: "#1a9d9a",
    weight: 1.6,
    opacity: 0.9,
    fillColor: "#1a9d9a",
    fillOpacity: 0.10
  }).addTo(map);

  L.circle(center, {
    radius: 2000,
    color: "#11596a",
    weight: 1.2,
    fillColor: "#11596a",
    fillOpacity: 0.55
  }).addTo(map);

  L.marker(center, {
    title: "Yvetot-Bocage — Normandie"
  }).addTo(map).bindPopup("<strong>Yvetot-Bocage</strong><br>Manche — Normandie<br><em>Zone d’environ 75 km autour</em>");

  /* zoom molette uniquement après un clic (confort de défilement) */
  map.on("click", function () { map.scrollWheelZoom.enable(); });
  map.on("mouseout", function () { map.scrollWheelZoom.disable(); });
})();
