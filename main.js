const generateBtn = document.getElementById('generate');
const lottoNumbers = document.querySelectorAll('.number');
const themeSwitcher = document.getElementById('theme-switcher');
const body = document.body;

function generateLottoNumbers() {
    const numbers = new Set();
    while (numbers.size < 6) {
        numbers.add(Math.floor(Math.random() * 45) + 1);
    }
    return Array.from(numbers).sort((a, b) => a - b);
}

function displayNumbers(numbers) {
    lottoNumbers.forEach((element, index) => {
        element.textContent = numbers[index];
    });
}

function generateAndDisplay() {
    const numbers = generateLottoNumbers();
    displayNumbers(numbers);
}

// Theme switcher logic
themeSwitcher.addEventListener('click', () => {
    body.classList.toggle('dark-mode');
    if (body.classList.contains('dark-mode')) {
        localStorage.setItem('theme', 'dark-mode');
    } else {
        localStorage.removeItem('theme');
    }
});

// Check for saved theme
document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        body.classList.add(savedTheme);
    }

    generateAndDisplay();
});

generateBtn.addEventListener('click', generateAndDisplay);

