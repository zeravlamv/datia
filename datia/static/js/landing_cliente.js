/* =====================================================
   DATIA · landing_cliente.js — Showcase de Producto
   ===================================================== */

(function () {
    'use strict';

    /* Animación de entrada al hacer scroll */
    function initReveal() {
        var items = document.querySelectorAll('.sc-item');
        if (!items.length) return;

        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (e) {
                if (e.isIntersecting) {
                    e.target.classList.add('sc-visible');
                    io.unobserve(e.target);
                }
            });
        }, { threshold: 0.08 });

        items.forEach(function (el) { io.observe(el); });
    }

    document.addEventListener('DOMContentLoaded', initReveal);
})();
