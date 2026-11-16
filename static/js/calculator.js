let calculatorExpression = '0';

function updateCalcDisplay() {
  document.getElementById('calcDisplay').value = calculatorExpression;
}

function calcAppend(value) {
  if (calculatorExpression === '0' && value !== '.') {
    calculatorExpression = value;
  } else {
    calculatorExpression += value;
  }
  updateCalcDisplay();
}

function calcClear() {
  calculatorExpression = '0';
  updateCalcDisplay();
}

function calcCalculate() {
  try {
    let sanitized = calculatorExpression.replace(/×/g, '*').replace(/÷/g, '/');
    let result = eval(sanitized);
    calculatorExpression = String(result);
    updateCalcDisplay();
  } catch (e) {
    calculatorExpression = 'Fout';
    updateCalcDisplay();
    setTimeout(calcClear, 1500);
  }
}
