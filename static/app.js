// Optimized Cyberpunk App
class CyberApp {
    constructor() {
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupIntersectionObserver();
        this.startPerformanceMonitoring();
    }

    setupEventListeners() {
        // Используем делегирование событий для производительности
        document.addEventListener('click', this.handleClick.bind(this), { passive: true });
        document.addEventListener('submit', this.handleSubmit.bind(this), { passive: false });

        // Оптимизированный resize handler
        let resizeTimeout;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => this.handleResize(), 100);
        }, { passive: true });
    }

    handleClick(e) {
        const target = e.target;

        // Wave эффект для кнопок
        if (target.classList.contains('btn-cyber')) {
            this.createWaveEffect(target, e);
        }

        // Глитч эффект для текста
        if (target.classList.contains('glitch-text')) {
            this.triggerGlitchEffect(target);
        }
    }

    handleSubmit(e) {
        const form = e.target;

        // Показываем состояние загрузки
        const submitBtn = form.querySelector('button[type="submit"]');
        if (submitBtn) {
            this.showLoadingState(submitBtn);
        }
    }

    createWaveEffect(element, event) {
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

        const rect = element.getBoundingClientRect();
        const wave = document.createElement('div');
        wave.className = 'wave-effect';
        wave.style.left = (event.clientX - rect.left) + 'px';
        wave.style.top = (event.clientY - rect.top) + 'px';

        element.appendChild(wave);
        setTimeout(() => wave.remove(), 600);
    }

    triggerGlitchEffect(element) {
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

        element.style.animation = 'glitch-anim 0.3s linear';
        setTimeout(() => element.style.animation = '', 300);
    }

    showLoadingState(button) {
        const originalText = button.innerHTML;
        button.innerHTML = '<div class="btn-cyber-loading"></div>';
        button.disabled = true;

        // Автоматическое восстановление через 5 секунд (на случай ошибки)
        setTimeout(() => {
            button.innerHTML = originalText;
            button.disabled = false;
        }, 5000);
    }

    setupIntersectionObserver() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');

                    // Ленивая загрузка фонов
                    if (entry.target.classList.contains('lazy-bg')) {
                        entry.target.classList.add('loaded');
                    }
                }
            });
        }, {
            rootMargin: '50px',
            threshold: 0.1
        });

        // Наблюдаем за элементами для ленивой загрузки
        document.querySelectorAll('.lazy-bg, .daily-task, .grid-cell').forEach(el => {
            observer.observe(el);
        });
    }

    createParticles() {
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

        const container = document.getElementById('particles');
        if (!container) return;

        // Ограничиваем количество частиц для производительности
        for (let i = 0; i < 15; i++) {
            const particle = document.createElement('div');
            particle.className = 'particle optimized-transform';
            particle.style.left = Math.random() * 100 + 'vw';
            particle.style.animationDelay = Math.random() * 10 + 's';
            container.appendChild(particle);
        }
    }

    startPerformanceMonitoring() {
        // Мониторинг производительности в development
        if (window.location.hostname === 'localhost') {
            const observer = new PerformanceObserver((list) => {
                list.getEntries().forEach((entry) => {
                    console.log(`${entry.name}: ${entry.duration}ms`);
                });
            });

            observer.observe({ entryTypes: ['measure', 'navigation', 'resource'] });
        }
    }

    handleResize() {
        // Оптимизация для мобильных устройств
        const isMobile = window.innerWidth < 768;
        document.body.classList.toggle('mobile-view', isMobile);
    }
}

// Инициализация приложения когда DOM готов
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new CyberApp());
} else {
    new CyberApp();
}

// Service Worker для кэширования (опционально)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => console.log('SW registered'))
            .catch(error => console.log('SW registration failed'));
    });
}
