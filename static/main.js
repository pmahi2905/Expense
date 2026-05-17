function toggleModal(id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.toggle('hidden');
}

document.addEventListener('DOMContentLoaded', () => {
    const flashes = document.querySelectorAll('.flash');
    flashes.forEach(f => {
        setTimeout(() => {
            f.style.transition = 'opacity 0.4s';
            f.style.opacity = '0';
            setTimeout(() => f.remove(), 400);
        }, 3500);
    });

    const dateInputs = document.querySelectorAll('input[type="date"]');
    const today = new Date().toISOString().split('T')[0];
    dateInputs.forEach(input => {
        if (!input.value) input.value = today;
    });

    const chartCanvas = document.getElementById('categoryChart');
    if (chartCanvas && window.categoryData) {
        const labels = Object.keys(window.categoryData);
        const data = Object.values(window.categoryData);
        const colors = ['#6c63ff','#10b981','#f59e0b','#ef4444','#3b82f6','#ec4899','#8b5cf6','#14b8a6'];
        new Chart(chartCanvas, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors.slice(0, labels.length),
                    borderWidth: 0,
                    hoverOffset: 6
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { padding: 16, font: { size: 12, family: 'Inter' }, usePointStyle: true }
                    },
                    tooltip: {
                        callbacks: { label: (ctx) => ` $${ctx.parsed.toFixed(2)}` }
                    }
                },
                cutout: '65%'
            }
        });
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal:not(.hidden)').forEach(m => m.classList.add('hidden'));
    }
});