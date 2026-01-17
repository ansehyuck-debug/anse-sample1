const generateBtn = document.getElementById('generate');
const menuRecommendation = document.getElementById('menu-recommendation');
const menuImage = document.getElementById('menu-image'); // New: Get reference to the image element
const themeSwitcher = document.getElementById('theme-switcher');
const body = document.body;

const menus = [
    '치킨', '피자', '삼겹살', '떡볶이', '초밥', '파스타', '김치찌개', '된장찌개',
    '부대찌개', '곱창', '족발', '보쌈', '짜장면', '짬뽕', '탕수육', '돈까스',
    '냉면', '국밥', '스테이크', '햄버거'
];

// New: Map menu items to image paths
const menuImageMap = {
    "치킨": "images/치킨.png",
    "피자": "images/피자.png",
    "삼겹살": "images/삼겹살.png",
    "떡볶이": "images/떡볶이.png",
    "초밥": "images/초밥.png",
    "파스타": "images/파스타.png",
    "김치찌개": "images/김치찌개.png",
    "된장찌개": "images/된장찌개.png",
    "부대찌개": "images/부대찌개.png",
    "곱창": "images/곱창.png",
    "족발": "images/족발.png",
    "보쌈": "images/보쌈.png",
    "짜장면": "images/짜장면.png",
    "짬뽕": "images/짬뽕.png",
    "탕수육": "images/탕수육.png",
    "돈까스": "images/돈까스.png",
    "냉면": "images/냉면.png",
    "국밥": "images/국밥.png",
    "스테이크": "images/스테이크.png",
    "햄버거": "images/햄버거.png",
};

function recommendMenu() {
    const randomIndex = Math.floor(Math.random() * menus.length);
    const recommendedMenu = menus[randomIndex];
    menuRecommendation.textContent = recommendedMenu;

    // New: Handle image display
    if (menuImageMap[recommendedMenu]) {
        menuImage.src = menuImageMap[recommendedMenu];
        menuImage.style.display = 'block'; // Show the image
    } else {
        menuImage.src = ''; // Clear source
        menuImage.style.display = 'none'; // Hide the image
    }
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
