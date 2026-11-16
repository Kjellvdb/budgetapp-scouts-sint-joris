document.addEventListener('DOMContentLoaded', () => {
  const config = window.chartConfig;
  if (!config) return;
  const rawExpenses = config.expenses || [];
  const startBudget = parseFloat(config.totalIncome) || 0;
  const earliestDateString = config.earliestDate || '';
  const endDateInput = document.getElementById('endDatePicker');

  function parseLocalDate(iso) {
    const parts = iso.split('-');
    if (parts.length !== 3) return new Date();
    return new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
  }

  function toIsoDate(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  const expensesByDate = {};
  let startDate = earliestDateString ? parseLocalDate(earliestDateString) : new Date();
  startDate.setDate(startDate.getDate() - 1);
  let defaultEndDate = new Date(startDate);
  defaultEndDate.setDate(defaultEndDate.getDate() + 10);
  rawExpenses.forEach((expense) => {
    if (expense.Datum) {
      const date = parseLocalDate(expense.Datum);
      if (date > defaultEndDate) {
        defaultEndDate = new Date(date);
      }
    }
  });

  const valueLabelsPlugin = {
    id: 'valueLabels',
    afterDatasetsDraw(chart) {
      const { ctx, data } = chart;
      ctx.save();
      ctx.font = 'bold 10px sans-serif';
      ctx.textAlign = 'center';
      const meta = chart.getDatasetMeta(0);
      meta.data.forEach((point, index) => {
        const value = data.datasets[0].data[index];
        const text = `€ ${Number(value).toFixed(2)}`;
        ctx.fillStyle = value < 0 ? '#dc3545' : '#198754';
        const yOffset = value < 0 ? 14 : -10;
        ctx.fillText(text, point.x, point.y + yOffset);
      });
      ctx.restore();
    },
  };

  const datepicker = flatpickr(endDateInput, {
    locale: 'nl',
    dateFormat: 'Y-m-d',
    altInput: true,
    altFormat: 'd/m/Y',
    minDate: startDate,
    defaultDate: defaultEndDate,
    onChange: function (selectedDates) {
      if (selectedDates.length > 0) {
        renderCharts(startDate, selectedDates[0]);
      }
    },
  });

  let budgetChart = null;
  let categoryChart = null;
  let dailyExpensesChart = null;
  rawExpenses.forEach((event) => {
    if (!event.Datum || event.Prijs == null) return;
    const key = event.Datum.slice(0, 10);
    if (!expensesByDate[key]) expensesByDate[key] = 0;
    expensesByDate[key] += parseFloat(event.Prijs) || 0;
  });

  function renderCharts(start, end) {
    const labels = [];
    const dataPoints = [];
    const currentDate = new Date(start);
    let runningBudget = startBudget;
    const filteredExpenses = [];
    while (currentDate <= end) {
      const dateKey = toIsoDate(currentDate);
      const displayLabel = currentDate.toLocaleDateString('nl-BE', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
      });
      labels.push(displayLabel);
      const dayExpense = expensesByDate[dateKey] || 0;
      if (dayExpense > 0) {
        rawExpenses.forEach((event) => {
          if (event.Datum && event.Datum.slice(0, 10) === dateKey) {
            filteredExpenses.push(event);
          }
        });
      }
      runningBudget -= dayExpense;
      dataPoints.push(Number(runningBudget.toFixed(2)));
      currentDate.setDate(currentDate.getDate() + 1);
    }

    const canvasBudget = document.getElementById('budgetChart');
    if (canvasBudget) {
      const contextBudget = canvasBudget.getContext('2d');
      if (budgetChart) budgetChart.destroy();
      budgetChart = new Chart(contextBudget, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Resterend Budget',
              data: dataPoints,
              borderWidth: 2.5,
              tension: 0,
              pointRadius: 0,
              pointHoverRadius: 5,
              segment: {
                borderColor: (context) => (context.p1.parsed.y < 0 || context.p0.parsed.y < 0 ? '#dc3545' : '#198754'),
              },
              fill: {
                target: { value: 0 },
                above: 'rgba(25, 135, 84, 0.10)',
                below: 'rgba(220, 53, 69, 0.10)',
              },
            },
          ],
        },
        plugins: [valueLabelsPlugin],
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              grace: '5%',
              ticks: {
                callback: (value) => `€ ${Number(value).toFixed(2)}`,
              },
              grid: { color: '#f1f3f5' },
            },
            x: {
              grid: { color: '#f8f9fa' },
              ticks: {
                maxRotation: 45,
                minRotation: 0,
              },
            },
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                title: (context) => `Datum: ${context[0].label}`,
                label: (context) => ` Resterend budget: € ${Number(context.parsed.y).toFixed(2)}`,
              },
            },
          },
        },
      });
    }

    const categoryTotals = {};
    filteredExpenses.forEach((expense) => {
      const categorie = expense.Categorie || 'Overig';
      if (!categoryTotals[categorie]) categoryTotals[categorie] = 0;
      categoryTotals[categorie] += parseFloat(expense.Prijs) || 0;
    });
    const categorieLabels = Object.keys(categoryTotals);
    const categorieData = Object.values(categoryTotals).map((value) => Number(value.toFixed(2)));
    const doughnutLabelsPlugin = {
      id: 'doughnutLabels',
      afterDatasetsDraw(chart) {
        const { ctx, data } = chart;
        ctx.save();
        ctx.imageSmoothingEnabled = true;
        ctx.imageSmoothingQuality = 'high';
        ctx.font = 'bold 11px sans-serif';
        ctx.textBaseline = 'middle';
        const meta = chart.getDatasetMeta(0);
        const total = data.datasets[0].data.reduce((a, b) => a + b, 0);
        let rightYPositions = [];
        let leftYPositions = [];
        meta.data.forEach((element, index) => {
          const value = data.datasets[0].data[index];
          if (value <= 0) return;
          const percentage = total > 0 ? (value / total) * 100 : 0;
          const { x, y } = element.tooltipPosition();
          const angle = element.startAngle + (element.endAngle - element.startAngle) / 2;
          if (percentage < 15) {
            const outerRadius = element.outerRadius;
            const extraRadius = 28;
            const lineStartX = element.x + Math.cos(angle) * outerRadius;
            const lineStartY = element.y + Math.sin(angle) * outerRadius;
            const lineMidX = element.x + Math.cos(angle) * (outerRadius + extraRadius);
            let targetY = element.y + Math.sin(angle) * (outerRadius + extraRadius);
            const isRightSide = Math.cos(angle) >= 0;
            let yPositions = isRightSide ? rightYPositions : leftYPositions;
            for (let pos of yPositions) {
              if (Math.abs(targetY - pos) < 18) {
                targetY = pos > targetY ? pos - 18 : pos + 18;
              }
            }
            yPositions.push(targetY);
            ctx.strokeStyle = '#adb5bd';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(lineStartX, lineStartY);
            ctx.lineTo(lineMidX, targetY);
            ctx.lineTo(isRightSide ? lineMidX + 12 : lineMidX - 12, targetY);
            ctx.stroke();
            ctx.fillStyle = data.datasets[0].backgroundColor[index];
            ctx.beginPath();
            ctx.arc(lineStartX, lineStartY, 2.5, 0, 2 * Math.PI);
            ctx.fill();
            ctx.textAlign = isRightSide ? 'left' : 'right';
            ctx.fillStyle = '#343a40';
            ctx.fillText(`€ ${value.toFixed(2)}`, isRightSide ? lineMidX + 15 : lineMidX - 15, targetY);
          } else {
            ctx.textAlign = 'center';
            ctx.fillStyle = '#ffffff';
            ctx.shadowColor = 'rgba(0, 0, 0, 0.6)';
            ctx.shadowBlur = 4;
            ctx.shadowOffsetX = 1;
            ctx.shadowOffsetY = 1;
            ctx.fillText(`€ ${value.toFixed(2)}`, x, y);
            ctx.shadowBlur = 0;
          }
        });
        ctx.restore();
      },
    };
    const canvasCategory = document.getElementById('categoryChart');
    if (canvasCategory) {
      const contextCategorie = canvasCategory.getContext('2d');
      if (categoryChart) categoryChart.destroy();
      categoryChart = new Chart(contextCategorie, {
        type: 'doughnut',
        data: {
          labels: categorieLabels.length > 0 ? categorieLabels : ['Geen uitgaven'],
          datasets: [
            {
              data: categorieData.length > 0 ? categorieData : [1],
              backgroundColor: ['#198754', '#ffc107', '#0dcaf0', '#dc3545', '#6c757d', '#6610f2', '#fd7e14', '#20c997'],
              borderWidth: 2,
              borderColor: '#ffffff',
            },
          ],
        },
        plugins: [doughnutLabelsPlugin],
        options: {
          responsive: true,
          maintainAspectRatio: false,
          radius: '60%',
          layout: {
            padding: {
              top: 35,
              bottom: 15,
              left: 50,
              right: 50,
            },
          },
          plugins: {
            legend: {
              position: 'bottom',
              labels: {
                generateLabels: (chart) => {
                  const data = chart.data;
                  if (data.labels.length && data.datasets.length) {
                    return data.labels.map((label, index) => {
                      const value = data.datasets[0].data[index];
                      return {
                        text: `${label}: € ${value.toFixed(2)}`,
                        fillStyle: data.datasets[0].backgroundColor[index],
                        strokeStyle: data.datasets[0].borderColor,
                        lineWidth: data.datasets[0].borderWidth,
                        hidden: false,
                        index: index,
                      };
                    });
                  }
                  return [];
                },
              },
            },
            tooltip: {
              callbacks: {
                label: (context) => ` ${context.label}: € ${Number(context.raw).toFixed(2)}`,
              },
            },
          },
        },
      });
    }

    const dailyLabels = [];
    const dailyData = [];
    let loopCurrentDate = new Date(start);
    while (loopCurrentDate <= end) {
      const dateKey = toIsoDate(loopCurrentDate);
      const displayLabel = loopCurrentDate.toLocaleDateString('nl-BE', {
        day: '2-digit',
        month: '2-digit',
      });
      dailyLabels.push(displayLabel);
      dailyData.push(Number((expensesByDate[dateKey] || 0).toFixed(2)));
      loopCurrentDate.setDate(loopCurrentDate.getDate() + 1);
    }
    const barValuesPlugin = {
      id: 'barValues',
      afterDatasetsDraw(chart) {
        const { ctx, data } = chart;
        ctx.save();
        ctx.font = 'bold 10px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = '#495057';
        const meta = chart.getDatasetMeta(0);
        meta.data.forEach((bar, index) => {
          const value = data.datasets[0].data[index];
          if (value > 0) {
            const text = `€ ${value.toFixed(2)}`;
            ctx.fillText(text, bar.x, bar.y - 6);
          }
        });
        ctx.restore();
      },
    };
    const canvasDaily = document.getElementById('dailyExpensesChart');
    if (canvasDaily) {
      const contextDaily = canvasDaily.getContext('2d');
      if (dailyExpensesChart) dailyExpensesChart.destroy();
      dailyExpensesChart = new Chart(contextDaily, {
        type: 'bar',
        data: {
          labels: dailyLabels,
          datasets: [
            {
              label: 'Uitgaven (€)',
              data: dailyData,
              backgroundColor: 'rgba(25, 135, 84, 0.7)',
              borderColor: '#198754',
              borderWidth: 1,
              borderRadius: 4,
            },
          ],
        },
        plugins: [barValuesPlugin],
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: {
              beginAtZero: true,
              grace: '10%',
              ticks: {
                callback: (value) => `€ ${Number(value).toFixed(2)}`,
              },
              grid: { color: '#f1f3f5' },
            },
            x: {
              grid: { display: false },
              ticks: {
                maxRotation: 45,
                minRotation: 0,
              },
            },
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                title: (context) => `Datum: ${context[0].label}`,
                label: (context) => ` Uitgaven: € ${Number(context.parsed.y).toFixed(2)}`,
              },
            },
          },
        },
      });
    }
  }

  renderCharts(startDate, datepicker.selectedDates[0] || defaultEndDate);
});
