// Supabase Configuration
const SB_URL = 'https://bksuhgixknsqzzxahuni.supabase.co';
const SB_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJrc3VoZ2l4a25zcXp6eGFodW5pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzAxOTUzNDMsImV4cCI6MjA4NTc3MTM0M30.bivQXNhnNoeWPToLmCmi_Ik74S2_NJg_PuVZe68Vtas';

// Supabase 초기화 (글로벌 노출)
if (typeof supabase !== 'undefined') {
    window.supabaseClient = supabase.createClient(SB_URL, SB_KEY);
}
const supabaseClient = window.supabaseClient;

async function initHeader() {
    console.log('Header script starting...');
    const placeholder = document.getElementById('header-placeholder');
    if (!placeholder) return;

    try {
        const resp = await fetch('header.html');
        if (!resp.ok) throw new Error('Header load failed');
        
        const html = await resp.text();
        placeholder.innerHTML = html;

        // --- 초기 언어 설정 및 번역 강제 적용 ---
        if (window.i18n) {
            const currentLang = window.i18n.getLanguage() || 'ko';
            console.log('Syncing header language to:', currentLang);
            
            // 1. 버튼 텍스트 설정 (KO/EN)
            const langBtnSpan = document.querySelector('#language-switcher span');
            if (langBtnSpan) langBtnSpan.textContent = currentLang.toUpperCase();
            
            // 2. HTML lang 속성 동기화
            document.documentElement.lang = currentLang;

            // 3. 헤더 및 모달 내부 모든 data-i18n 요소 강제 번역
            const i18nElements = placeholder.querySelectorAll('[data-i18n]');
            i18nElements.forEach(el => {
                if (typeof window.i18n.translateElement === 'function') {
                    window.i18n.translateElement(el);
                }
            });
        }

        setupHeaderEventListeners();

        if (supabaseClient) {
            supabaseClient.auth.onAuthStateChange((event, session) => {
                updateAuthUI(session?.user);
            });
            const { data: { user } } = await supabaseClient.auth.getUser();
            updateAuthUI(user);
        }

        updateThemeIcon(document.documentElement.classList.contains('dark'));

    } catch (err) {
        console.error('Header error:', err);
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

    document.getElementById('login-button')?.addEventListener('click', async () => {
        await supabaseClient.auth.signInWithOAuth({
            provider: 'google',
            options: { redirectTo: window.location.href }
        });
    });

    document.getElementById('logout-button-dropdown')?.addEventListener('click', async () => {
        await supabaseClient.auth.signOut();
        location.reload();
    });

    const modal = document.getElementById('account-modal');
    document.getElementById('my-account-btn')?.addEventListener('click', () => {
        modal?.classList.remove('hidden');
        dropdown?.classList.add('hidden');
        switchTab('overview');
    });

    document.getElementById('close-modal')?.addEventListener('click', () => modal?.classList.add('hidden'));
    modal?.addEventListener('click', (e) => { if (e.target === modal) modal.classList.add('hidden'); });

    document.getElementById('nav-overview')?.addEventListener('click', () => switchTab('overview'));
    document.getElementById('nav-settings')?.addEventListener('click', () => switchTab('settings'));
    document.getElementById('nav-account')?.addEventListener('click', () => switchTab('account'));

    const langBtn = document.getElementById('language-switcher');
    if (langBtn && window.i18n) {
        langBtn.addEventListener('click', () => {
            const next = window.i18n.getLanguage() === 'ko' ? 'en' : 'ko';
            window.i18n.setLanguage(next);
            langBtn.querySelector('span').textContent = next.toUpperCase();
            
            // 페이지 전체 번역 실행
            if (typeof window.i18n.translatePage === 'function') {
                window.i18n.translatePage();
            }
            
            window.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: next } }));
        });
    }

    setupModalActionListeners();
}

function updateThemeIcon(isDark) {
    const icon = document.querySelector('#theme-switcher .material-symbols-outlined');
    if (icon) icon.textContent = isDark ? 'dark_mode' : 'light_mode';
}

function updateAuthUI(user) {
    const btn = document.getElementById('login-button');
    const prof = document.getElementById('user-profile');
    if (user) {
        btn?.classList.add('hidden');
        prof?.classList.remove('hidden');
        const url = user.user_metadata.avatar_url;
        if (url) {
            const av = document.getElementById('user-avatar');
            if (av) av.style.backgroundImage = `url('${url}')`;
            const mav = document.getElementById('modal-user-avatar');
            if (mav) mav.style.backgroundImage = `url('${url}')`;
        }
        document.getElementById('dropdown-user-name').textContent = user.user_metadata.full_name || 'User';
        document.getElementById('dropdown-user-email').textContent = user.email;
        const modalName = document.getElementById('modal-user-name');
        const modalEmail = document.getElementById('modal-user-email');
        if(modalName) modalName.textContent = user.user_metadata.full_name || 'User';
        if(modalEmail) modalEmail.textContent = user.email;
        checkSubscriptionStatus(user.id);
    } else {
        btn?.classList.remove('hidden');
        prof?.classList.add('hidden');
    }
}

async function checkSubscriptionStatus(uid) {
    try {
        const { data } = await supabaseClient.from('subscriptions').select('status').eq('user_id', uid).maybeSingle();
        const txt = document.getElementById('subscription-status-text');
        const sub = document.getElementById('subscribe-btn');
        const can = document.getElementById('cancel-subscription-btn');
        if (!txt) return;
        if (data && data.status === 'active') {
            txt.innerHTML = '<span class="text-emerald-500 font-black">구독 중</span>';
            if(sub) sub.classList.add('hidden');
            if(can) can.classList.remove('hidden');
        } else {
            txt.textContent = window.i18n ? window.i18n.translate("subscription-benefit") : "";
            if(sub) sub.classList.remove('hidden');
            if(can) can.classList.add('hidden');
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
            if (k === tid) { btn.classList.add('bg-primary', 'text-white'); btn.classList.remove('text-[#49699c]', 'dark:text-slate-400'); }
            else { btn.classList.remove('bg-primary', 'text-white'); btn.classList.add('text-[#49699c]', 'dark:text-slate-400'); }
        }
    });
    const t = document.getElementById('modal-title');
    if (t) { 
        t.setAttribute('data-i18n', tid); 
        if (window.i18n && typeof window.i18n.translateElement === 'function') {
            window.i18n.translateElement(t);
        }
    }
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

initHeader();
