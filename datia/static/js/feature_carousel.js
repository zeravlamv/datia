document.addEventListener('DOMContentLoaded', function () {
    if (!window.DatiaFeatureCarouselBound) {
        window.DatiaFeatureCarouselBound = true;
        document.addEventListener('datia:tab-change', function (e) {
            var tabId = e.detail && e.detail.tabId;
            var panel = document.getElementById(tabId);
            if (!panel) return;
            var wrappers = panel.querySelectorAll('.fc-wrapper');
            wrappers.forEach(function (wrapper) {
                if (!wrapper.__datia_fc__) setupCarousel(wrapper);
                else wrapper.__datia_fc__.restart();
            });
        });
    }
    var containers = document.querySelectorAll('.fc-wrapper');
    containers.forEach(function (c) { 
        setupCarousel(c); 
        if (c.__datia_fc__ && typeof c.__datia_fc__.init === 'function') {
            c.__datia_fc__.init();
        }
    });
});

function setupCarousel(container) {
    if (container.__datia_fc__) return;
    var tabs = container.querySelectorAll('.fc-tab');
    var slides = container.querySelectorAll('.fc-slide');
    if (!tabs.length || !slides.length) return;
    var currentIndex = 0;
    var timerID = null;
    var INTERVAL = 5000;

    function activate(index) {
        tabs.forEach(function (tab, i) {
            tab.classList.remove('active');
            tab.classList.remove('completed');
            if (i < index) tab.classList.add('completed');
        });
        slides.forEach(function (slide) { slide.classList.remove('active'); });
        var bar = tabs[index] ? tabs[index].querySelector('.fc-tab-bar') : null;
        if (bar) {
            bar.style.animation = 'none';
            void tabs[index].offsetHeight;
            bar.style.animation = '';
        }
        if (tabs[index]) tabs[index].classList.add('active');
        if (slides[index]) slides[index].classList.add('active');
    }

    function next() {
        currentIndex = (currentIndex + 1) % tabs.length;
        activate(currentIndex);
    }

    function start() {
        if (timerID) clearInterval(timerID);
        timerID = setInterval(next, INTERVAL);
    }

    container.addEventListener('click', function (e) {
        var tabEl = e.target.closest('.fc-tab');
        if (!tabEl) return;
        var idx = Array.from(tabs).indexOf(tabEl);
        if (idx >= 0) {
            currentIndex = idx;
            activate(currentIndex);
            start();
        }
    });

    container.__datia_fc__ = {
        restart: function () {
            currentIndex = 0;
            activate(0);
            start();
        },
        init: function () {
            activate(0);
            start();
        },
        stop: function () {
            if (timerID) clearInterval(timerID);
            timerID = null;
        }
    };

    requestAnimationFrame(function () {
        activate(0);
        start();
    });
}
