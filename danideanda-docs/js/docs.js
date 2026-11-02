(function () {
    "use strict";

    var toggle = document.querySelector("[data-menu-toggle]");
    var sidebar = document.getElementById("docs-sidebar");

    if (toggle && sidebar) {
        toggle.addEventListener("click", function () {
            var open = sidebar.classList.toggle("is-open");
            toggle.setAttribute("aria-expanded", open ? "true" : "false");
        });

        // Al elegir un documento en móvil, cerramos el menú.
        sidebar.addEventListener("click", function (event) {
            if (event.target.closest("a") && window.matchMedia("(max-width: 900px)").matches) {
                sidebar.classList.remove("is-open");
                toggle.setAttribute("aria-expanded", "false");
            }
        });
    }

    // Resalta el enlace actual si el servidor no lo hizo.
    var path = window.location.pathname;
    var links = document.querySelectorAll(".docs-nav a");
    var found = false;

    links.forEach(function (link) {
        if (link.classList.contains("active")) {
            found = true;
        }
    });

    if (!found) {
        links.forEach(function (link) {
            var href = link.getAttribute("href");
            var matches = href === path ||
                (href === "/" && (path === "/" || path === "/index.html")) ||
                (href !== "/" && path === href);
            if (matches) {
                link.classList.add("active");
                link.setAttribute("aria-current", "page");
                found = true;
            }
        });
    }
})();
