// Unsplash API Access Key를 여기에 입력하세요.
// https://unsplash.com/developers 에서 회원가입 후 Access Key를 발급받을 수 있습니다.
const unsplashAccessKey = 'YOUR_UNSPLASH_ACCESS_KEY';

const generateBtn = document.getElementById('generate');
const menuRecommendation = document.getElementById('menu-recommendation');
const menuImage = document.getElementById('menu-image');
const themeSwitcher = document.getElementById('theme-switcher');
const body = document.body;

const menus = [
    '치킨', '피자', '삼겹살', '떡볶이', '초밥', '파스타', '김치찌개', '된장찌개',
    '부대찌개', '곱창', '족발', '보쌈', '짜장면', '짬뽕', '탕수육', '돈까스',
    '냉면', '국밥', '스테이크', '햄버ガー'
];

async function getMenuImage(menu) {
    // 이미지를 표시하고, API 호출을 시작하기 전에 기본 placeholder를 보여줄 수 있습니다.
    menuImage.style.display = 'block';
    menuImage.src = `https://via.placeholder.com/200x200.png?text=${menu}`;

    // Unsplash API를 사용하여 메뉴에 맞는 이미지를 검색합니다.
    try {
        const response = await fetch(`https://api.unsplash.com/search/photos?query=${menu}&client_id=${unsplashAccessKey}`);
        if (!response.ok) {
            throw new Error('Unsplash API request failed');
        }
        const data = await response.json();
        if (data.results && data.results.length > 0) {
            menuImage.src = data.results[0].urls.small;
        }
    } catch (error) {
        console.error('Error fetching image from Unsplash:', error);
        // API 호출에 실패하면 placeholder 이미지가 계속 표시됩니다.
    }
}

function recommendMenu() {
    const randomIndex = Math.floor(Math.random() * menus.length);
    const recommendedMenu = menus[randomIndex];
    menuRecommendation.textContent = recommendedMenu;
    getMenuImage(recommendedMenu);
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
