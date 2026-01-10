const generateBtn = document.getElementById('generate');
const menuRecommendation = document.getElementById('menu-recommendation');

const menus = [
    '치킨',
    '피자',
    '삼겹살',
    '떡볶이',
    '초밥',
    '파스타',
    '김치찌개',
    '된장찌개',
    '부대찌개',
    '곱창',
    '족발',
    '보쌈',
    '짜장면',
    '짬뽕',
    '탕수육',
    '돈까스',
    '냉면',
    '국밥',
    '스테이크',
    '햄버거'
];

function recommendMenu() {
    const randomIndex = Math.floor(Math.random() * menus.length);
    menuRecommendation.textContent = menus[randomIndex];
}

generateBtn.addEventListener('click', recommendMenu);

// Recommend a menu on initial load
recommendMenu();

