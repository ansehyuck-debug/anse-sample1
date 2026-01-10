const generateBtn = document.getElementById('generate');
const lottoNumbers = document.querySelectorAll('.number');
const themeSwitcher = document.getElementById('theme-switcher');
const body = document.body;
const includeBonusCheckbox = document.getElementById('includeBonus');


function generateLottoNumbers() {
    const numbers = new Set();
    const count = includeBonusCheckbox.checked ? 6 : 5;
    while (numbers.size < count) {
        numbers.add(Math.floor(Math.random() * 45) + 1);
    }
    return Array.from(numbers).sort((a, b) => a - b);
}

function displayNumbers(numbers) {
    lottoNumbers.forEach((element, index) => {
        if (numbers[index]) {
            element.textContent = numbers[index];
            element.style.display = 'inline-block'; // Show the number
        } else {
            element.textContent = '';
            element.style.display = 'none'; // Hide if no number
        }
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

// Check for saved theme and initial generation
document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        body.classList.add(savedTheme);
    }

    generateAndDisplay();
    generateBtn.addEventListener('click', generateAndDisplay);
});


