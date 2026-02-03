(function() {
    function getLanguage() {
        const savedLang = localStorage.getItem('language');
        if (savedLang) return savedLang;
        
        const browserLang = navigator.language || navigator.userLanguage;
        return browserLang.startsWith('ko') ? 'ko' : 'en';
    }

    function setLanguage(lang) {
        localStorage.setItem('language', lang);
        document.documentElement.lang = lang;
        applyTranslations(lang);
    }

    function applyTranslations(lang) {
        const t = translations[lang];
        if (!t) return;

        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (t[key]) {
                if (el.tagName === 'META') {
                    el.setAttribute('content', t[key]);
                } else if (el.tagName === 'TITLE') {
                    document.title = t[key];
                } else {
                    el.textContent = t[key];
                }
            }
        });

        // Update specific meta tags
        const metaTitle = document.querySelector('meta[property="og:title"]');
        if (metaTitle) {
             const pageType = window.location.pathname.includes('sentiment') ? 'us' : 'korea';
             metaTitle.setAttribute('content', t['title-' + pageType]);
        }
    }

    function initLanguageSwitcher() {
        const lang = getLanguage();
        document.documentElement.lang = lang;

        const headerActions = document.querySelector('header .flex.flex-wrap.items-center.justify-end');
        if (headerActions) {
            if (document.getElementById('language-switcher')) return;

            const langBtn = document.createElement('button');
            langBtn.id = 'language-switcher';
            langBtn.className = 'flex h-10 w-10 items-center justify-center rounded-lg bg-[#f0f3f9] dark:bg-slate-800 text-[#0d131c] dark:text-white mr-2 shrink-0';
            langBtn.innerHTML = `<span class="text-xs font-bold">${lang.toUpperCase()}</span>`;
            langBtn.addEventListener('click', () => {
                const currentLang = document.documentElement.lang;
                const newLang = currentLang === 'ko' ? 'en' : 'ko';
                setLanguage(newLang);
                langBtn.querySelector('span').textContent = newLang.toUpperCase();
                window.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: newLang } }));
            });
            
            const themeSwitcher = document.getElementById('theme-switcher');
            if (themeSwitcher) {
                headerActions.insertBefore(langBtn, themeSwitcher);
            } else {
                headerActions.appendChild(langBtn);
            }
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            initLanguageSwitcher();
            applyTranslations(getLanguage());
        });
    } else {
        initLanguageSwitcher();
        applyTranslations(getLanguage());
    }

    window.i18n = {
        getLanguage: getLanguage,
        setLanguage: setLanguage,
        translate: function(key) {
            return (translations[getLanguage()] && translations[getLanguage()][key]) || key;
        }
    };
})();
