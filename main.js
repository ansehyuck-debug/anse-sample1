const generateBtn = document.getElementById('generate');
const menuRecommendation = document.getElementById('menu-recommendation');
const themeSwitcher = document.getElementById('theme-switcher');
const body = document.body;

const menus = [
    '치킨', '피자', '삼겹살', '떡볶이', '초밥', '파스타', '김치찌개', '된장찌개',
    '부대찌개', '곱창', '족발', '보쌈', '짜장면', '짬뽕', '탕수육', '돈까스',
    '냉면', '국밥', '스테이크', '햄버거'
];

function recommendMenu() {
    const randomIndex = Math.floor(Math.random() * menus.length);
    const recommendedMenu = menus[randomIndex];
    menuRecommendation.textContent = recommendedMenu;
}

// --- Theme Switcher Logic ---
themeSwitcher.addEventListener('click', () => {
    body.classList.toggle('dark-mode');
    if (body.classList.contains('dark-mode')) {
        localStorage.setItem('theme', 'dark-mode');
    } else {
        localStorage.removeItem('theme');
    }
});

// 페이지 로드 시 저장된 테마를 확인하고 적용합니다.
document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        body.classList.add(savedTheme);
    }
    // 페이지가 처음 로드될 때 메뉴를 추천합니다.
    recommendMenu();
});

generateBtn.addEventListener('click', recommendMenu);
