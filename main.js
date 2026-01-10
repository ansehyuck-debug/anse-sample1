const generateBtn = document.getElementById('generate');
const lottoNumbers = document.querySelectorAll('.number');

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

generateBtn.addEventListener('click', generateAndDisplay);

// Initial generation
generateAndDisplay();
