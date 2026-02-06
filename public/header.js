// Supabase Configuration
const SB_URL = 'https://bksuhgixknsqzzxahuni.supabase.co';
const SB_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJrc3VoZ2l4a25zcXp6eGFodW5pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzAxOTUzNDMsImV4cCI6MjA4NTc3MTM0M30.bivQXNhnNoeWPToLmCmi_Ik74S2_NJg_PuVZe68Vtas';

if (typeof supabase !== 'undefined') {
    window.supabaseClient = supabase.createClient(SB_URL, SB_KEY);
}
const supabaseClient = window.supabaseClient;

async function initHeader() {
    console.log('Header script starting...');
    const placeholder = document.getElementById('header-placeholder');
    if (!placeholder) {
        console.error('header-placeholder not found');
        return;
    }

    try {
        // 경로를 상대 경로로 변경하여 호환성 높임
        const resp = await fetch('header.html');
        if (!resp.ok) throw new Error('Header load failed: ' + resp.status);
        
        const html = await resp.text();
        placeholder.innerHTML = html;
        console.log('Header HTML injected.');

        // --- 언어 동기화 로직 (localStorage 직접 참조) ---
        const savedLang = localStorage.getItem('language') || 'ko';
        document.documentElement.lang = savedLang;
        
        // 버튼 텍스트 즉시 동기화
        const langBtnSpan = placeholder.querySelector('#language-switcher span');
        if (langBtnSpan) {
            langBtnSpan.textContent = savedLang.toUpperCase();
        }

        let syncAttempts = 0;
        const syncLanguage = () => {
            // window.i18n과 applyTranslations 함수가 모두 로드되었는지 확인
            if (window.i18n && typeof window.i18n.applyTranslations === 'function') {
                // 저장된 언어로 페이지 전체 재번역 실행
                window.i18n.applyTranslations();
                console.log('Header & Page Translations Applied:', savedLang);
            } else if (syncAttempts < 50) { // 최대 2.5초 동안 대기
                syncAttempts++;
                setTimeout(syncLanguage, 50);
            }
        };
        syncLanguage();

        setupHeaderEventListeners();

        // 모의 로그인 및 실제 인증 로직
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('mock') === 'true') {
            const mockUser = { id: 'mock-user-12345', email: 'test@anse.ai.kr', user_metadata: { full_name: '테스트 계정' } };
            updateAuthUI(mockUser);
        } else if (supabaseClient) {
            supabaseClient.auth.onAuthStateChange((event, session) => updateAuthUI(session?.user));
            const { data: { user } } = await supabaseClient.auth.getUser();
            updateAuthUI(user);
        }
        updateThemeIcon(document.documentElement.classList.contains('dark'));

    } catch (err) {
        console.error('Header init error:', err);
    }
}

function setupHeaderEventListeners() {
    document.getElementById('theme-switcher')?.addEventListener('click', () => {
        const isDark = document.documentElement.classList.toggle('dark');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        updateThemeIcon(isDark);
    });

    document.getElementById('menu-button')?.addEventListener('click', () => {
        document.getElementById('mobile-menu')?.classList.toggle('hidden');
    });

    const avatar = document.getElementById('user-avatar');
    const dropdown = document.getElementById('profile-dropdown');
    avatar?.addEventListener('click', (e) => { e.stopPropagation(); dropdown?.classList.toggle('hidden'); });
    window.addEventListener('click', () => dropdown?.classList.add('hidden'));

    const modal = document.getElementById('account-modal');
    document.getElementById('my-account-btn')?.addEventListener('click', () => {
        modal?.classList.remove('hidden');
        dropdown?.classList.add('hidden');
        switchTab('overview');
    });
    document.getElementById('close-modal')?.addEventListener('click', () => modal?.classList.add('hidden'));

    document.getElementById('nav-overview')?.addEventListener('click', () => switchTab('overview'));
    document.getElementById('nav-settings')?.addEventListener('click', () => switchTab('settings'));
    document.getElementById('nav-account')?.addEventListener('click', () => switchTab('account'));

    const langBtn = document.getElementById('language-switcher');
    if (langBtn) {
        langBtn.addEventListener('click', () => {
            const currentLang = document.documentElement.lang || 'ko';
            const newLang = currentLang === 'ko' ? 'en' : 'ko';
            if (window.i18n) {
                window.i18n.setLanguage(newLang);
                langBtn.querySelector('span').textContent = newLang.toUpperCase();
                window.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: newLang } }));
            }
        });
    }

    setupModalActionListeners();
}

function updateThemeIcon(isDark) {
    const icon = document.querySelector('#theme-switcher .material-symbols-outlined');
    if (icon) icon.textContent = isDark ? 'dark_mode' : 'light_mode';
}

function updateAuthUI(user) {
    const loginBtn = document.getElementById('login-button');
    const profile = document.getElementById('user-profile');
    if (user) {
        loginBtn?.classList.add('hidden');
        profile?.classList.remove('hidden');
        document.getElementById('dropdown-user-name').textContent = user.user_metadata.full_name || 'User';
        document.getElementById('dropdown-user-email').textContent = user.email;
        const mName = document.getElementById('modal-user-name');
        const mEmail = document.getElementById('modal-user-email');
        if(mName) mName.textContent = user.user_metadata.full_name || 'User';
        if(mEmail) mEmail.textContent = user.email;
        checkSubscriptionStatus(user.id);
    } else {
        loginBtn?.classList.remove('hidden');
        profile?.classList.add('hidden');
    }
}

async function checkSubscriptionStatus(uid) {
    try {
        const { data } = await supabaseClient.from('subscriptions').select('status').eq('user_id', uid).maybeSingle();
        const txt = document.getElementById('subscription-status-text');
        if (!txt) return;
        if (data && data.status === 'active') {
            txt.innerHTML = '<span class="text-emerald-500 font-black">구독 중</span>';
        } else {
            txt.textContent = window.i18n ? window.i18n.translate("subscription-benefit") : "";
        }
    } catch (e) {}
}

function switchTab(tid) {
    const s = { overview: 'section-overview', settings: 'section-settings', account: 'section-account' };
    const b = { overview: 'nav-overview', settings: 'nav-settings', account: 'nav-account' };
    Object.keys(s).forEach(k => {
        const el = document.getElementById(s[k]);
        if (el) el.classList.toggle('hidden', k !== tid);
        const btn = document.getElementById(b[k]);
        if (btn) {
            if (k === tid) { btn.classList.add('bg-primary', 'text-white'); btn.classList.remove('text-[#49699c]'); }
            else { btn.classList.remove('bg-primary', 'text-white'); btn.classList.add('text-[#49699c]'); }
        }
    });
    const t = document.getElementById('modal-title');
    if (t) { t.setAttribute('data-i18n', tid); window.i18n?.applyTranslations(); }
}

function setupModalActionListeners() {
    document.getElementById('withdraw-btn')?.addEventListener('click', async () => {
        if (!confirm(window.i18n?.translate("withdraw-confirm") || "Delete account?")) return;
        const { data: { user } } = await supabaseClient.auth.getUser();
        if (!user) return;
        try {
            const r = await fetch('/api/withdraw', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: user.id }) });
            if ((await r.json()).success) { alert("Deleted"); await supabaseClient.auth.signOut(); location.reload(); }
        } catch (e) {}
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHeader);
} else {
    initHeader();
}