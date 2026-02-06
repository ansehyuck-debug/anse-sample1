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

    // 이 함수를 외부에서 호출할 수 있도록 수정할 예정
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
        // 기존의 버튼 생성 로직은 헤더가 직접 가지고 있으므로 여기서는 초기 lang 설정만 유지
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

    // 외부 노출 객체
    window.i18n = {
        getLanguage: getLanguage,
        setLanguage: setLanguage,
        applyTranslations: function() { applyTranslations(getLanguage()); }, // 핵심: 이 줄을 추가합니다.
        translate: function(key) {
            return (translations[getLanguage()] && translations[getLanguage()][key]) || key;
        }
    };
})();