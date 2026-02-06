const SB_URL = 'https://bksuhgixknsqzzxahuni.supabase.co';
const SB_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJrc3VoZ2l4a25zcXp6eGFodW5pIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzAxOTUzNDMsImV4cCI6MjA4NTc3MTM0M30.bivQXNhnNoeWPToLmCmi_Ik74S2_NJg_PuVZe68Vtas';

if (typeof supabase !== 'undefined') window.supabaseClient = supabase.createClient(SB_URL, SB_KEY);
const supabaseClient = window.supabaseClient;

async function initHeader() {
    const placeholder = document.getElementById('header-placeholder');
    if (!placeholder) return;

    try {
        const resp = await fetch('header.html');
        if (!resp.ok) return;
        placeholder.innerHTML = await resp.text();

        const syncLang = () => {
            if (window.i18n?.applyTranslations) {
                const lang = window.i18n.getLanguage();
                document.documentElement.lang = lang;
                const btn = placeholder.querySelector('#language-switcher span');
                if (btn) btn.textContent = lang.toUpperCase();
                window.i18n.applyTranslations();
            } else {
                setTimeout(syncLang, 30);
            }
        };
        syncLang();
        setupEventListeners(placeholder);

        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('mock') === 'true') {
            updateAuthUI({ id: 'mock', email: 'test@anse.ai.kr', user_metadata: { full_name: '테스트 계정' } });
        } else if (supabaseClient) {
            supabaseClient.auth.onAuthStateChange((_, session) => updateAuthUI(session?.user));
            const { data: { user } } = await supabaseClient.auth.getUser();
            updateAuthUI(user);
        }
        updateThemeIcon(document.documentElement.classList.contains('dark'));
    } catch (e) {}
}

function setupEventListeners(p) {
    p.querySelector('#theme-switcher')?.addEventListener('click', () => {
        const isDark = document.documentElement.classList.toggle('dark');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        updateThemeIcon(isDark);
    });

    p.querySelector('#menu-button')?.addEventListener('click', () => p.querySelector('#mobile-menu')?.classList.toggle('hidden'));

    const av = p.querySelector('#user-avatar'), dr = p.querySelector('#profile-dropdown');
    av?.addEventListener('click', (e) => { e.stopPropagation(); dr?.classList.toggle('hidden'); });
    window.addEventListener('click', () => dr?.classList.add('hidden'));

    const mod = p.querySelector('#account-modal');
    p.querySelector('#my-account-btn')?.addEventListener('click', () => {
        mod?.classList.remove('hidden');
        dr?.classList.add('hidden');
        switchTab('overview');
    });
    p.querySelector('#close-modal')?.addEventListener('click', () => mod?.classList.add('hidden'));
    mod?.addEventListener('click', (e) => e.target === mod && mod.classList.add('hidden'));

    ['overview', 'settings', 'account'].forEach(id => {
        p.querySelector(`#nav-${id}`)?.addEventListener('click', () => switchTab(id));
    });

    p.querySelector('#language-switcher')?.addEventListener('click', () => {
        if (!window.i18n) return;
        const next = window.i18n.getLanguage() === 'ko' ? 'en' : 'ko';
        window.i18n.setLanguage(next);
        p.querySelector('#language-switcher span').textContent = next.toUpperCase();
        window.dispatchEvent(new CustomEvent('languageChanged', { detail: { language: next } }));
    });

    p.querySelector('#withdraw-btn')?.addEventListener('click', async () => {
        if (!confirm(window.i18n?.translate("withdraw-confirm") || "Delete account?")) return;
        const { data: { user } } = await supabaseClient.auth.getUser();
        if (!user) return;
        const res = await fetch('/api/withdraw', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ user_id: user.id }) });
        if ((await res.json()).success) { await supabaseClient.auth.signOut(); location.reload(); }
    });
}

function updateThemeIcon(isDark) {
    const icon = document.querySelector('#theme-switcher .material-symbols-outlined');
    if (icon) icon.textContent = isDark ? 'dark_mode' : 'light_mode';
}

function updateAuthUI(user) {
    const loginBtn = document.getElementById('login-button'), prof = document.getElementById('user-profile');
    if (!loginBtn || !prof) return;
    if (user) {
        loginBtn.classList.add('hidden'); prof.classList.remove('hidden');
        document.getElementById('dropdown-user-name').textContent = user.user_metadata.full_name || 'User';
        document.getElementById('dropdown-user-email').textContent = user.email;
        const mN = document.getElementById('modal-user-name'), mE = document.getElementById('modal-user-email');
        if(mN) mN.textContent = user.user_metadata.full_name || 'User';
        if(mE) mE.textContent = user.email;
        checkSubscriptionStatus(user.id);
    } else {
        loginBtn.classList.remove('hidden'); prof.classList.add('hidden');
    }
}

async function checkSubscriptionStatus(uid) {
    try {
        const { data } = await supabaseClient.from('subscriptions').select('status').eq('user_id', uid).maybeSingle();
        const txt = document.getElementById('subscription-status-text');
        if (txt) {
            if (data?.status === 'active') txt.innerHTML = '<span class="text-emerald-500 font-black">구독 중</span>';
            else txt.textContent = window.i18n?.translate("subscription-benefit") || "";
        }
    } catch (e) {}
}

function switchTab(tid) {
    const tabs = ['overview', 'settings', 'account'];
    tabs.forEach(id => {
        document.getElementById(`section-${id}`)?.classList.toggle('hidden', id !== tid);
        const btn = document.getElementById(`nav-${id}`);
        if (btn) btn.className = (id === tid) ? "w-full text-left px-3 py-2 rounded-lg bg-primary text-white text-sm font-bold flex items-center gap-2" : "w-full text-left px-3 py-2 rounded-lg text-[#49699c] dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-800 text-sm font-bold flex items-center gap-2 transition-colors";
    });
    const t = document.getElementById('modal-title');
    if (t) { t.setAttribute('data-i18n', tid); window.i18n?.applyTranslations(); }
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initHeader);
else initHeader();
