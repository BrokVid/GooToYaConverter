document.addEventListener('DOMContentLoaded', function () {
    // === ЭЛЕМЕНТЫ ИНТЕРФЕЙСА ===
    const elements = {
        googleInput: document.getElementById('googleInput'),
        yandexOutput: document.getElementById('yandexOutput'),
        convertBtn: document.getElementById('convertBtn'),

        startBtn: document.getElementById('startBtn'),
        stopBtn: document.getElementById('stopBtn'),
        foundCoords: document.getElementById('foundCoords'),
        resultCoords: document.getElementById('resultCoords'),

        calibrationToggle: document.getElementById('calibrationToggle'),
        calibrationContent: document.getElementById('calibrationContent'),
        cardHeader: document.querySelector('.card-header.collapsible'),

        calibStartBtn: document.getElementById('calibStartBtn'),
        calibStopBtn: document.getElementById('calibStopBtn'),
        pointsCount: document.getElementById('pointsCount'),
        calibTableBody: document.getElementById('calibTableBody'),

        deleteSelectedBtn: document.getElementById('deleteSelectedBtn'),
        saveBtn: document.getElementById('saveBtn'),
        loadBtn: document.getElementById('loadBtn'),
        exportBtn: document.getElementById('exportBtn'),
        updateLocationsBtn: document.getElementById('updateLocationsBtn'),

        statusIndicator: document.getElementById('statusIndicator'),
        statusDot: document.querySelector('.status-dot'),
        statusText: document.getElementById('statusText'),

        copyBtns: document.querySelectorAll('.copy-btn')
    };

    let pollingInterval = null;
    let isMonitoring = false;
    let isCalibrating = false;

    // === ИНИЦИАЛИЗАЦИЯ ===
    fetchCalibrationData();
    startPolling();

    // === ОБРАБОТЧИКИ СОБЫТИЙ ===

    // Ручная конвертация
    elements.convertBtn.addEventListener('click', async () => {
        const coords = elements.googleInput.value.trim();
        if (!coords) {
            showToast('Введите координаты Google', 'warning');
            return;
        }

        try {
            const response = await fetch('/api/convert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ coords: coords })
            });

            const data = await response.json();

            if (data.success) {
                elements.yandexOutput.value = data.result;
                showToast('Конвертация выполнена', 'success');
            } else {
                showToast(data.error || 'Ошибка конвертации', 'error');
            }
        } catch (error) {
            showToast('Ошибка сети', 'error');
            console.error(error);
        }
    });

    // Автоматическая конвертация - Старт
    elements.startBtn.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/monitoring/start', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                updateStatusUI('working');
            }
        } catch (e) { console.error(e); }
    });

    // Автоматическая конвертация - Стоп
    elements.stopBtn.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/monitoring/stop', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                updateStatusUI('stopped');
            }
        } catch (e) { console.error(e); }
    });

    // Переключение секции калибровки
    elements.calibrationToggle.addEventListener('click', () => {
        elements.calibrationContent.classList.toggle('expanded');
        elements.cardHeader.classList.toggle('collapsed');
    });

    // Калибровка - Старт
    elements.calibStartBtn.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/calibration/start', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                updateStatusUI('calibrating');
            }
        } catch (e) { console.error(e); }
    });

    // Калибровка - Стоп
    elements.calibStopBtn.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/monitoring/stop', { method: 'POST' }); // Стоп общий
            const data = await response.json();
            if (data.success) {
                updateStatusUI('stopped');
            }
        } catch (e) { console.error(e); }
    });

    // Копирование
    elements.copyBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.dataset.copy;
            const input = document.getElementById(targetId);
            if (input && input.value) {
                // Пытаемся скопировать через API браузера
                navigator.clipboard.writeText(input.value).then(() => {
                    showToast('Скопировано!', 'info');
                }).catch(err => {
                    // Если не вышло (например, нет фокуса), просим бэкенд
                    fetch('/api/clipboard/copy', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text: input.value })
                    }).then(() => showToast('Скопировано!', 'info'));
                });
            }
        });
    });

    // Действия с таблицей
    elements.deleteSelectedBtn.addEventListener('click', deleteSelectedPoints);
    elements.saveBtn.addEventListener('click', saveCalibration);
    elements.loadBtn.addEventListener('click', loadCalibration);
    elements.exportBtn.addEventListener('click', exportCalibration);
    elements.updateLocationsBtn.addEventListener('click', updateLocations);

    // === ФУНКЦИИ ===

    function startPolling() {
        if (pollingInterval) clearInterval(pollingInterval);
        pollingInterval = setInterval(async () => {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();

                // Обновляем статус
                if (data.status !== (isMonitoring ? (isCalibrating ? 'calibrating' : 'working') : 'stopped')) {
                    // Синхронизация статуса с сервером при первой загрузке или расхождениях
                    // (Упрощенно обновляем UI по данным сервера)
                    updateStatusUI(data.status);
                }

                // Обновляем поля авто-конвертации
                if (data.last_found && elements.foundCoords.value !== data.last_found) {
                    elements.foundCoords.value = data.last_found;
                }
                if (data.last_result && elements.resultCoords.value !== data.last_result) {
                    elements.resultCoords.value = data.last_result;
                    // Анимация обновления
                    elements.resultCoords.parentElement.classList.add('pulse-animation');
                    setTimeout(() => elements.resultCoords.parentElement.classList.remove('pulse-animation'), 1000);
                }

                // Обновляем статус калибровки
                if (data.calibration_status) {
                    const statusLabel = document.querySelector('.status-badge');
                    if (data.calibration_message) {
                        window.lastCalibrationMessage = data.calibration_message;
                        // Форсируем обновление текста если уже в режиме калибровки
                        if (isCalibrating) {
                            elements.statusText.textContent = data.calibration_message;
                        }
                    }
                }

                // Если количество точек изменилось на сервере, обновляем таблицу
                if (data.points_count !== parseInt(elements.pointsCount.textContent)) {
                    fetchCalibrationData();
                }

            } catch (e) {
                // Ошибка опроса (сервер может быть недоступен при закрытии)
            }
        }, 1000);
    }

    function updateStatusUI(status) {
        elements.statusDot.className = 'status-dot'; // сброс
        elements.startBtn.disabled = false;
        elements.stopBtn.disabled = true;
        elements.calibStartBtn.disabled = false;
        elements.calibStopBtn.disabled = true;

        if (status === 'working') {
            elements.statusDot.classList.add('working');
            elements.statusText.textContent = 'Работает';
            elements.startBtn.disabled = true;
            elements.stopBtn.disabled = false;
            elements.calibStartBtn.disabled = true; // Нельзя калибровать пока работает авто
            isMonitoring = true;
            isCalibrating = false;
        } else if (status === 'calibrating') {
            elements.statusDot.classList.add('calibrating');

            // Если есть сообщение от сервера, показываем его
            if (window.lastCalibrationMessage) {
                elements.statusText.textContent = window.lastCalibrationMessage;
            } else {
                elements.statusText.textContent = 'Калибровка...';
            }

            elements.calibStartBtn.disabled = true;
            elements.calibStopBtn.disabled = false;
            elements.startBtn.disabled = true;
            isMonitoring = true;
            isCalibrating = true;
            // Развернем секцию если она свернута
            if (!elements.calibrationContent.classList.contains('expanded')) {
                elements.calibrationToggle.click();
            }
        } else {
            elements.statusDot.classList.add('stopped');
            elements.statusText.textContent = 'Остановлено';
            isMonitoring = false;
            isCalibrating = false;
        }
    }

    async function fetchCalibrationData() {
        try {
            const response = await fetch('/api/calibration/data');
            const data = await response.json();
            renderTable(data);
        } catch (e) { console.error(e); }
    }

    function renderTable(data) {
        elements.pointsCount.textContent = data.length;
        elements.calibTableBody.innerHTML = '';

        // Группировка
        const groups = {};
        data.forEach(item => {
            const loc = item.location || 'Неизвестно';
            if (!groups[loc]) groups[loc] = [];
            groups[loc].push(item);
        });

        // Разделение на группы (>=2) и одиночные
        const groupedCities = [];
        const singleItems = [];

        Object.keys(groups).forEach(city => {
            if (groups[city].length >= 2 && city !== 'Неизвестно' && city !== 'Город не найден') {
                groupedCities.push({ city: city, items: groups[city] });
            } else {
                singleItems.push(...groups[city]);
            }
        });

        // Сортировка групп от А до Я
        groupedCities.sort((a, b) => a.city.localeCompare(b.city));

        // Добавляем группу "Остальные", если есть одиночные элементы
        if (singleItems.length > 0) {
            // Одиночные сортируем от А до Я по городу
            singleItems.sort((a, b) => {
                const locA = a.location || 'яяя';
                const locB = b.location || 'яяя';
                return locA.localeCompare(locB);
            });
            groupedCities.push({ city: 'Остальные', items: singleItems, isOthers: true });
        }

        // Хелперы для координат
        const getLat = str => {
            const parts = str.split(',');
            return parts.length > 0 ? parseFloat(parts[0]) : 0;
        };
        const getLon = str => {
            const parts = str.split(',');
            return parts.length > 1 ? parseFloat(parts[1]) : 0;
        };

        // Внутри группы сортировка по широте (по возрастанию)
        groupedCities.forEach(group => {
            if (!group.isOthers) {
                group.items.sort((a, b) => getLat(a.yandex) - getLat(b.yandex));
            }
        });

        const createYandexLink = (coordsStr) => {
            const lat = getLat(coordsStr);
            const lon = getLon(coordsStr);
            return `https://yandex.ru/maps?l=sat%2Cskl&ll=${lon}%2C${lat}&mode=whatshere&whatshere%5Bpoint%5D=${lon}%2C${lat}&whatshere%5Bzoom%5D=19&z=19`;
        };

        let visualIndex = 1;

        // Рендер групп
        groupedCities.forEach(group => {
            // Уникальный ID для группы
            const groupId = 'group-' + Math.random().toString(36).substr(2, 9);

            // Заголовок группы
            const headerTr = document.createElement('tr');
            headerTr.className = 'group-header';
            headerTr.dataset.groupId = groupId;
            // Добавляем стрелочку для индикации
            headerTr.innerHTML = `<td colspan="5">
                <span style="display: inline-block; transition: transform 0.2s; margin-right: 8px;">▼</span>
                ${group.city} (${group.items.length})
            </td>`;

            // Обработчик сворачивания
            headerTr.addEventListener('click', () => {
                const rows = document.querySelectorAll(`.group-row-${groupId}`);
                const isHidden = rows[0].classList.contains('group-hidden');

                rows.forEach(r => r.classList.toggle('group-hidden'));

                // Вращаем стрелочку
                const arrow = headerTr.querySelector('span');
                arrow.style.transform = isHidden ? 'rotate(0deg)' : 'rotate(-90deg)';
            });

            elements.calibTableBody.appendChild(headerTr);

            // Элементы группы
            group.items.forEach(row => renderRow(row, groupId));
        });

        // function renderRow(row, groupId = '') - теперь принимает ID группы
        function renderRow(row, groupId) {
            const tr = document.createElement('tr');
            if (groupId) {
                tr.classList.add(`group-row-${groupId}`); // Связываем с заголовком
            }

            const location = row.location || 'Загрузка...';
            const link = createYandexLink(row.yandex);

            tr.innerHTML = `
                <td>${visualIndex++}</td>
                <td>${row.google}</td>
                <td>
                    <a href="${link}" target="_blank" class="coord-link" style="color: inherit; border-bottom: 1px dashed rgba(255,255,255,0.3); text-decoration: none;">
                        ${row.yandex}
                    </a>
                </td>
                <td class="location-cell">${location}</td>
                <td>
                    <button class="btn-delete-row" type="button" title="Удалить">
                        <svg viewBox="0 0 24 24" fill="none"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z" fill="currentColor"/></svg>
                    </button>
                </td>
            `;

            // Клик по ряду для выделения
            tr.addEventListener('click', (e) => {
                // Игнорируем клик, если он был по ссылке или кнопке
                if (!e.target.closest('button') && !e.target.closest('a')) {
                    tr.classList.toggle('selected');
                }
            });

            // Клик по кнопке удаления
            const delBtn = tr.querySelector('.btn-delete-row');
            delBtn.addEventListener('click', (e) => {
                e.stopPropagation(); // Чтобы не выделять ряд при удалении
                deletePointByRow(tr);
            });

            elements.calibTableBody.appendChild(tr);
        }
    }

    // Удаление конкретной строки
    async function deletePointByRow(tr) {
        tr.classList.add('selected');
        await deleteSelectedPoints();
    }

    // Сохраняем совместимость с глобальным вызовом, если он где-то остался
    window.deletePoint = function (btn) {
        const tr = btn.closest('tr');
        if (tr) deletePointByRow(tr);
    };

    async function deleteSelectedPoints() {
        const selectedRows = document.querySelectorAll('#calibTableBody tr.selected');
        if (selectedRows.length === 0) {
            showToast('Выберите точки для удаления', 'warning');
            return;
        }

        const pointsToDelete = [];
        selectedRows.forEach(row => {
            pointsToDelete.push({
                google: row.children[1].textContent.trim(),
                yandex: row.children[2].textContent.trim()
            });
        });

        try {
            const response = await fetch('/api/calibration/data', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(pointsToDelete)
            });
            if ((await response.json()).success) {
                fetchCalibrationData();
                showToast(`Удалено точек: ${pointsToDelete.length}`, 'success');
            }
        } catch (e) {
            showToast('Ошибка удаления', 'error');
        }
    }

    async function saveCalibration() {
        try {
            const response = await fetch('/api/calibration/save', { method: 'POST' });
            const data = await response.json();
            if (data.success) showToast('Конфигурация сохранена', 'success');
            else showToast('Ошибка сохранения', 'error');
        } catch (e) { showToast('Ошибка сети', 'error'); }
    }

    async function exportCalibration() {
        // Скачивание файла calibration.json
        try {
            const response = await fetch('/api/calibration/export', { method: 'POST' });
            const data = await response.json();

            // Создаем Blob и ссылку для скачивания
            const dataStr = JSON.stringify(data, null, 4);
            const blob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(blob);

            const a = document.createElement('a');
            a.href = url;
            a.download = 'calibration.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            showToast('Файл сохранен в Загрузки', 'success');
        } catch (e) { showToast('Ошибка экспорта', 'error'); }
    }

    // Скрытый инпут для загрузки файла
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.json';
    fileInput.style.display = 'none';
    document.body.appendChild(fileInput);

    fileInput.addEventListener('change', handleFileUpload);

    async function loadCalibration() {
        // Триггерим клик по скрытому инпуту
        fileInput.click();
    }

    async function handleFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = async (e) => {
            try {
                const json = JSON.parse(e.target.result);
                // Отправляем на сервер
                const response = await fetch('/api/calibration/import', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(json)
                });
                const res = await response.json();

                if (res.success) {
                    showToast(`Импортировано точек: ${res.count}`, 'success');
                    fetchCalibrationData();
                } else {
                    showToast('Ошибка импорта: ' + res.error, 'error');
                }
            } catch (err) {
                showToast('Ошибка чтения файла', 'error');
            }
            // Сброс value чтобы можно было выбрать тот же файл снова
            fileInput.value = '';
        };
        reader.readAsText(file);
    }

    async function updateLocations() {
        try {
            const response = await fetch('/api/calibration/update-locations', { method: 'POST' });
            const data = await response.json();
            if (data.success) {
                showToast('Обновление местоположений запущено...', 'info');
                // Периодически обновляем таблицу чтобы видеть прогресс
                const interval = setInterval(() => {
                    fetchCalibrationData();
                }, 2000);
                // Останавливаем через 60 секунд
                setTimeout(() => clearInterval(interval), 60000);
            }
        } catch (e) {
            showToast('Ошибка сети', 'error');
        }
    }


    function showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        let icon = '';
        if (type === 'success') icon = '<svg class="toast-icon" viewBox="0 0 24 24" fill="none"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" fill="currentColor"/></svg>';
        else if (type === 'error') icon = '<svg class="toast-icon" viewBox="0 0 24 24" fill="none"><path d="M12 2C6.47 2 2 6.47 2 12s4.47 10 10 10 10-4.47 10-10S17.53 2 12 2zm5 13.59L15.59 17 12 13.41 8.41 17 7 15.59 10.59 12 7 8.41 8.41 7 12 10.59 15.59 7 17 8.41 13.41 12 17 15.59z" fill="currentColor"/></svg>';
        else if (type === 'warning') icon = '<svg class="toast-icon" viewBox="0 0 24 24" fill="none"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" fill="currentColor"/></svg>';
        else icon = '<svg class="toast-icon" viewBox="0 0 24 24" fill="none"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z" fill="currentColor"/></svg>';

        toast.innerHTML = `
            ${icon}
            <span class="toast-message">${message}</span>
            <button class="toast-close" onclick="this.parentElement.classList.add('hiding'); setTimeout(() => this.parentElement.remove(), 300);">
                <svg viewBox="0 0 24 24" fill="none"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" fill="currentColor"/></svg>
            </button>
        `;

        container.appendChild(toast);

        // Автоудаление
        setTimeout(() => {
            if (toast.parentElement) {
                toast.classList.add('hiding');
                setTimeout(() => toast.remove(), 300);
            }
        }, 3000);
    }
});
