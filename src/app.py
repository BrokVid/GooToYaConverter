import sys
import os
import json
import math
import re
import threading
import time
import queue
import pyperclip
import webbrowser
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from flask import Flask, render_template, jsonify, request

# Проверка наличия pywebview
try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False

# === КОНСТАНТЫ ===

CONFIG_FILENAME = "calibration.json"

# Базовые калибровочные точки
BASE_CALIBRATION = [
    ((56.82811805737119, 60.61426164412377), (56.828106, 60.614287)),
    ((56.86259891560065, 60.6572500903253), (56.862586, 60.657278)),
    ((56.906666700192716, 60.63861543087929), (56.906652, 60.638628)),
    ((56.909591402519915, 60.5950190263033), (56.909575, 60.595034)),
    ((56.87863660391573, 60.51722444081701), (56.87863, 60.517245)),
    ((56.781989564663476, 60.53752005594862), (56.781985, 60.537538)),
    ((56.78862468710676, 60.651199174559736), (56.78862, 60.651223)),
    ((56.80968834490725, 60.56463415653675), (56.809684, 60.564653)),
    ((56.79674324537193, 60.620513467301855), (56.796731, 60.620529)),
    ((56.826145898242764, 60.60015154151012), (56.826133, 60.600177)),
    ((56.89324984612583, 60.57766089933516), (56.893228, 60.577675)),
    ((56.885031152408864, 60.50838738450612), (56.885019, 60.508406)),
    ((56.88387294721526, 60.5001406084767), (56.883864, 60.500160)),
    ((59.938910517751964, 30.3142877746221), (59.938946, 30.314283)),
    ((59.87644544335019, 30.374270379623916), (59.876472, 30.374265)),
    ((59.962981728189405, 30.494793702118574), (59.962993, 30.494808)),
    ((60.06028554274266, 30.41687044365594), (60.060287, 30.416894)),
    ((55.178505866136376, 61.458797115710254), (55.178509, 61.458815)),
    ((56.31857864399124, 44.00491972362694), (56.318603, 44.004937)),
    ((56.33901617217321, 43.95225351295961), (56.339029, 43.952260)),
    ((56.398701063262536, 43.985588829111364), (56.398709, 43.985600)),
    ((57.1508971355925, 65.55846964059829), (57.150906, 65.558491)),
    ((57.17835206448346, 65.56925933783715), (57.178346, 65.569273)),
    ((57.11876675058166, 65.48813022260148), (57.118771, 65.488159)),
    ((62.02797499644836, 129.76162940491085), (62.027965, 129.761650)),
    ((62.05203840919141, 129.71767049344646), (62.052036, 129.717689)),
    ((56.140030547089054, 47.24760888056219), (56.140049, 47.247614)),
    ((56.12298277856921, 47.26660062665822), (56.123003, 47.266606)),
    ((56.149800604524664, 47.17474603595798), (56.149809, 47.174721)),
    ((56.13225084586679, 47.15316591517464), (56.132254, 47.153140)),
    ((51.8242809475715, 107.57781015145557), (51.824287, 107.577818))
]

# Коэффициенты линейного преобразования (fallback)
DEFAULT_A, DEFAULT_B, DEFAULT_C = 1.00002178, -0.000409512697, 0.0235679088
DEFAULT_D, DEFAULT_E, DEFAULT_F = -0.0000552760272, 0.99995881, 0.00565924534

# Регулярное выражение для парсинга координат
coord_re = re.compile(r'([-+]?\d*\.\d+),\s*([-+]?\d*\.\d+)')


# === ФУНКЦИИ КОНВЕРТАЦИИ ===

def get_distance(lat1, lon1, lat2, lon2):
    """Вычисляет расстояние между двумя точками (упрощённая формула)."""
    avg_lat = math.radians((lat1 + lat2) / 2.0)
    dlat = lat1 - lat2
    dlon = (lon1 - lon2) * math.cos(avg_lat)
    return math.sqrt(dlat**2 + dlon**2)


def convert_coords_advanced(glat, glon, calibration_data):
    """Конвертирует координаты Google в Yandex методом IDW-интерполяции."""
    if not calibration_data:
        ylat = DEFAULT_A * glat + DEFAULT_B * glon + DEFAULT_C
        ylon = DEFAULT_D * glat + DEFAULT_E * glon + DEFAULT_F
        return f"{ylat:.6f}, {ylon:.6f}"

    total_weight = 0
    sum_dlat = 0
    sum_dlon = 0
    p = 2

    for (g_lat, g_lon), (y_lat, y_lon) in calibration_data:
        dist = get_distance(glat, glon, g_lat, g_lon)
        if dist < 0.0000001:
            return f"{y_lat:.6f}, {y_lon:.6f}"
        
        weight = 1.0 / (dist ** p)
        total_weight += weight
        sum_dlat += (y_lat - g_lat) * weight
        sum_dlon += (y_lon - g_lon) * weight
    
    if total_weight == 0:
        return f"{glat:.6f}, {glon:.6f}"

    final_dlat = sum_dlat / total_weight
    final_dlon = sum_dlon / total_weight
    return f"{(glat + final_dlat):.6f}, {(glon + final_dlon):.6f}"


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def wait_for_new_paste(timeout=None):
    """Ожидает новое содержимое в буфере обмена."""
    initial_content = pyperclip.paste()
    start_time = time.time()
    
    while True:
        time.sleep(0.1)
        current_content = pyperclip.paste()
        
        if current_content != initial_content:
            return current_content
            
        if timeout is not None:
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(f'Таймаут ожидания: {timeout} сек.')


def reverse_geocode(lat, lon):
    """Получает название города по координатам через Nominatim API."""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&accept-language=ru"
        req = urllib.request.Request(url, headers={'User-Agent': 'GooToYaConverter/1.0'})
        
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            address = data.get('address', {})
            
            city = (address.get('city') or 
                   address.get('town') or 
                   address.get('village') or 
                   address.get('municipality') or
                   address.get('county') or
                   address.get('state'))
            
            country = address.get('country', '')
            
            if city and country:
                return f"{city}, {country}"
            elif city:
                return city
            elif country:
                return country
            else:
                return "Город не найден"
                
    except (urllib.error.HTTPError, urllib.error.URLError):
        return "Не удалось получить данные"
    except Exception as e:
        print(f"Ошибка геокодинга: {e}")
        return "Город не найден"


def guess_source_type(text):
    """
    Определяет источник координаты по количеству знаков после запятой.
    Если знаков > 7 — это Google, если <= 7 — Yandex.
    """
    matches = re.findall(r'\.(\d+)', text)
    if not matches:
        return "Неизвестно"
    
    # Берем максимальную точность из найденных чисел (обычно их два: широта и долгота)
    max_precision = max(len(x) for x in matches)
    
    if max_precision > 7:
        return "Google"
    else:
        return "Yandex"


def get_location_for_point_sync(point_data):
    """Синхронно получает местоположение для точки калибровки."""
    try:
        coords_str = point_data.get('google', '')
        m = coord_re.search(coords_str)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
            time.sleep(1.2)  # Rate limit для Nominatim
            return reverse_geocode(lat, lon)
    except Exception as e:
        print(f"Ошибка получения локации: {e}")
    return "Город не найден"


# === КЛАССЫ ===

class AppState:
    """Состояние приложения: калибровочные данные и флаги режимов."""
    
    def __init__(self):
        self.training_data = []
        self.is_monitoring = False
        self.is_calibrating = False
        self.monitor_thread = None
        self.last_clipboard = ""
        self.last_found_coords = ""
        self.last_result_coords = ""
        self.pending_google = None
        self.calibration_status_text = ""
        
        # Определяем, запущено ли приложение из EXE или из исходников
        self.is_frozen = getattr(sys, 'frozen', False)
        
        if self.is_frozen:
            # Запущено из EXE (PyInstaller) — используем AppData
            self.config_dir = self.get_appdata_dir()
            self.config_path = self.config_dir / CONFIG_FILENAME
        else:
            # Запущено из исходников — используем папку проекта
            project_root = Path(__file__).resolve().parent.parent  # src -> корень проекта
            self.config_dir = project_root / 'data'
            self.config_path = self.config_dir / CONFIG_FILENAME
        
        try:
            os.makedirs(self.config_dir, exist_ok=True)
        except Exception as e:
            print(f"Ошибка создания директории: {e}")

    def get_resource_path(self, relative_path):
        """Возвращает путь к ресурсу (для PyInstaller)."""
        if self.is_frozen:
            # Запущено из EXE — ресурсы в временной папке
            base_path = sys._MEIPASS
        else:
            # Запущено из исходников — ресурсы в папке src/
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)

    def get_appdata_dir(self):
        """Возвращает путь к директории конфигурации в AppData."""
        app_data = os.getenv('APPDATA')
        if not app_data:
            app_data = os.path.expanduser("~")
        return Path(app_data) / "GooToYaConverter"

    def load_config(self):
        """Загружает калибровочные данные из файла."""
        try:
            if not os.path.exists(self.config_path):
                initial = [{
                    "google": f"{g[0]}, {g[1]}", 
                    "yandex": f"{y[0]}, {y[1]}", 
                    "location": ""
                } for g, y in BASE_CALIBRATION]
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(initial, f, indent=4, ensure_ascii=False)
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.training_data = json.load(f)
            
            for point in self.training_data:
                if 'location' not in point:
                    point['location'] = ""
                if point.get('location') in ["Загрузка...", "Loading..."]:
                    point['location'] = ""
            
            self.is_monitoring = False
            self.is_calibrating = False
            
            return True
        except Exception as e:
            print(f"Ошибка загрузки конфига: {e}")
            return False

    def save_config(self):
        """Сохраняет калибровочные данные в файл."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.training_data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Ошибка сохранения конфига: {e}")
            return False
            
    def get_calib_list(self):
        """Возвращает список калибровочных точек для конвертации."""
        calib_list = []
        for p in self.training_data:
            try:
                g_l, g_o = map(float, p["google"].split(", "))
                y_l, y_o = map(float, p["yandex"].split(", "))
                calib_list.append(((g_l, g_o), (y_l, y_o)))
            except:
                continue
        return calib_list


class GeocodingWorker:
    """Фоновый воркер для определения местоположения."""
    
    def __init__(self):
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
    
    def add_task(self, point):
        """Добавляет точку в очередь на геокодинг."""
        point['location'] = "Загрузка..."
        self.queue.put(point)
    
    def _worker(self):
        """Обрабатывает очередь геокодинга."""
        while True:
            try:
                point = self.queue.get()
                if point is None:
                    break
                
                location = get_location_for_point_sync(point)
                point['location'] = location
                state.save_config()
                
                self.queue.task_done()
            except Exception as e:
                print(f"Ошибка воркера: {e}")


# === ИНИЦИАЛИЗАЦИЯ ===

state = AppState()
state.load_config()
geocoding_service = GeocodingWorker()


# === ЛОГИКА ОПРЕДЕЛЕНИЯ ПОРЯДКА КООРДИНАТ ===

def check_swap_heuristic(coord1, coord2, state=None):
    """
    Определяет правильный порядок координат: (Google, Yandex).
    Использует правило: у Google больше 7 знаков после запятой (через guess_source_type).
    """
    type1 = guess_source_type(coord1)
    type2 = guess_source_type(coord2)
    
    # Если первая — Yandex, а вторая — Google, меняем их местами
    if type1 == "Yandex" and type2 == "Google":
        return coord2, coord1
        
    return coord1, coord2


# === МОНИТОРИНГ БУФЕРА ОБМЕНА ===

def monitor_clipboard_task():
    """Фоновый мониторинг буфера обмена для конвертации/калибровки."""
    while state.is_monitoring:
        try:
            # Ожидаем новое содержимое
            try:
                text = wait_for_new_paste(timeout=1)
            except TimeoutError:
                continue
            
            if not text or len(text) > 5000:
                continue
            
            state.last_clipboard = text
            
            m = coord_re.search(text)
            if not m:
                continue
                
            coords_str = f"{m.group(1)}, {m.group(2)}"
            
            # === РЕЖИМ КАЛИБРОВКИ ===
            if state.is_calibrating:
                if state.pending_google is None:
                    # Первая координата пары
                    state.pending_google = coords_str
                    src_type = guess_source_type(coords_str)
                    
                    if src_type == "Google":
                        wait_for = "Yandex (короткие)"
                    elif src_type == "Yandex":
                        wait_for = "Google (длинные)"
                    else:
                        wait_for = "вторую координату"
                        
                    state.calibration_status_text = f"Получен {src_type}. Скопируйте {wait_for}..."
                    print(f"[КАЛИБРОВКА] Первая координата: {src_type}")
                else:
                    # Вторая координата пары
                    raw_1 = state.pending_google
                    raw_2 = coords_str
                    
                    if raw_1 == raw_2:
                        print("[КАЛИБРОВКА] Одинаковые координаты, пропуск")
                        continue
                    
                    type_1 = guess_source_type(raw_1)
                    type_2 = guess_source_type(raw_2)
                    
                    print(f"[КАЛИБРОВКА] Координата 1: {type_1}, Координата 2: {type_2}")
                    
                    # Проверка что типы разные
                    if type_1 == type_2:
                        state.calibration_status_text = f"⚠️ Обе координаты {type_1}! Нужна пара: Google + Yandex"
                        print(f"[КАЛИБРОВКА] Обе координаты {type_1}, отклонено")
                        continue
                    
                    # Определяем порядок: Google, потом Yandex
                    final_google, final_yandex = check_swap_heuristic(raw_1, raw_2, state)
                    
                    state.calibration_status_text = "🌍 Определяю местоположение..."
                    
                    # Получаем местоположение синхронно
                    try:
                        m_google = coord_re.search(final_google)
                        if m_google:
                            lat, lon = float(m_google.group(1)), float(m_google.group(2))
                            time.sleep(1.2)
                            location = reverse_geocode(lat, lon)
                        else:
                            location = "Город не найден"
                    except Exception as e:
                        print(f"Ошибка геокодинга: {e}")
                        location = "Город не найден"
                    
                    # Добавляем точку
                    new_point = {
                        "google": final_google, 
                        "yandex": final_yandex, 
                        "location": location
                    }
                    
                    state.training_data.append(new_point)
                    state.save_config()
                    
                    print(f"[КАЛИБРОВКА] Добавлено: {location} | G: {final_google} | Y: {final_yandex}")
                    
                    state.pending_google = None
                    state.calibration_status_text = f"✅ Добавлено: {location}. Скопируйте следующую пару..."
                
                continue

            # === РЕЖИМ КОНВЕРТАЦИИ ===
            glat, glon = float(m.group(1)), float(m.group(2))
            
            if len(m.group(1)) < 2 and len(m.group(2)) < 2:
                continue

            calib_list = state.get_calib_list()
            res = convert_coords_advanced(glat, glon, calib_list)
            
            pyperclip.copy(res)
            state.last_clipboard = res
            state.last_found_coords = coords_str
            state.last_result_coords = res
            
            print(f"[КОНВЕРТАЦИЯ] {coords_str} -> {res}")
            
        except Exception as e:
            print(f"Ошибка мониторинга: {e}")
            import traceback
            traceback.print_exc()
            state.is_monitoring = False
            break


# === FLASK ПРИЛОЖЕНИЕ ===

# Определяем пути к ресурсам
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    # Абсолютный путь к папке src
    base_dir = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))

template_folder = os.path.join(base_dir, 'templates')
static_folder = os.path.join(base_dir, 'static')

app = Flask(__name__, 
            template_folder=template_folder, 
            static_folder=static_folder,
            static_url_path='/static')

app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.route('/')
def index():
    """Главная страница."""
    return render_template('index.html')


@app.route('/api/convert', methods=['POST'])
def api_convert():
    """API: Ручная конвертация координат."""
    data = request.json
    text = data.get('coords', '')
    m = coord_re.search(text)
    if m:
        try:
            glat, glon = float(m.group(1)), float(m.group(2))
            calib_list = state.get_calib_list()
            res = convert_coords_advanced(glat, glon, calib_list)
            return jsonify(success=True, result=res)
        except Exception as e:
            return jsonify(success=False, error=str(e))
    return jsonify(success=False, error="Неверный формат координат")


@app.route('/api/status')
def api_status():
    """API: Текущий статус приложения."""
    status = "stopped"
    if state.is_monitoring:
        status = "calibrating" if state.is_calibrating else "working"
    
    return jsonify(
        status=status,
        last_found=state.last_found_coords,
        last_result=state.last_result_coords,
        points_count=len(state.training_data),
        calibration_status=state.is_calibrating,
        calibration_message=state.calibration_status_text,
        pending_google=state.pending_google is not None
    )


@app.route('/api/monitoring/start', methods=['POST'])
def start_monitoring():
    """API: Запуск мониторинга буфера обмена."""
    if not state.is_monitoring:
        state.is_monitoring = True
        state.is_calibrating = False
        state.pending_google = None
        thread = threading.Thread(target=monitor_clipboard_task, daemon=True)
        thread.start()
    return jsonify(success=True)


@app.route('/api/calibration/start', methods=['POST'])
def start_calibration():
    """API: Запуск режима калибровки."""
    state.is_calibrating = True

    if not state.is_monitoring:
        state.is_monitoring = True
        thread = threading.Thread(target=monitor_clipboard_task, daemon=True)
        thread.start()
        
    state.pending_google = None
    state.calibration_status_text = "Режим калибровки. Скопируйте первую координату..."
    return jsonify(success=True)


@app.route('/api/monitoring/stop', methods=['POST'])
def stop_monitoring():
    """API: Остановка мониторинга."""
    state.is_monitoring = False
    state.is_calibrating = False
    state.pending_google = None
    state.calibration_status_text = ""
    return jsonify(success=True)


@app.route('/api/calibration/data', methods=['GET', 'DELETE'])
def calibration_data():
    """API: Получение/удаление калибровочных данных."""
    if request.method == 'GET':
        return jsonify(state.training_data)
    
    if request.method == 'DELETE':
        items_to_delete = request.json
        if not items_to_delete:
            return jsonify(success=False)
            
        new_data = []
        for item in state.training_data:
            should_delete = False
            for del_item in items_to_delete:
                if (item['google'].strip() == del_item['google'].strip() and 
                    item['yandex'].strip() == del_item['yandex'].strip()):
                    should_delete = True
                    break
            if not should_delete:
                new_data.append(item)
        
        state.training_data = new_data
        state.save_config()
        return jsonify(success=True)


@app.route('/api/calibration/save', methods=['POST'])
def save_calib():
    """API: Сохранение калибровочных данных."""
    success = state.save_config()
    return jsonify(success=success)


@app.route('/api/calibration/load', methods=['POST'])
def load_calib():
    """API: Загрузка калибровочных данных."""
    success = state.load_config()
    return jsonify(success=success)


@app.route('/api/calibration/import', methods=['POST'])
def import_calib():
    """API: Импорт калибровочных данных из JSON."""
    try:
        new_data = request.json
        if not isinstance(new_data, list):
            return jsonify(success=False, error="Неверный формат")
            
        valid_count = 0
        for item in new_data:
            if 'google' in item and 'yandex' in item:
                is_exist = any(
                    x['google'] == item['google'] and x['yandex'] == item['yandex'] 
                    for x in state.training_data
                )
                if not is_exist:
                    if 'location' not in item:
                        item['location'] = ""
                    state.training_data.append(item)
                    valid_count += 1
        
        state.save_config()
        return jsonify(success=True, count=valid_count)
    except Exception as e:
        return jsonify(success=False, error=str(e))


@app.route('/api/calibration/export', methods=['POST'])
def export_calib():
    """API: Экспорт калибровочных данных в JSON."""
    return jsonify(state.training_data)


@app.route('/api/clipboard/copy', methods=['POST'])
def clipboard_copy():
    """API: Копирование текста в буфер обмена."""
    text = request.json.get('text', '')
    pyperclip.copy(text)
    return jsonify(success=True)


@app.route('/api/calibration/update-locations', methods=['POST'])
def update_locations():
    """API: Обновление местоположений для точек без геоданных."""
    updated_count = 0
    for point in state.training_data:
        loc = point.get('location', '')
        if not loc or loc in ["Город не найден", "Не удалось получить данные", "Загрузка..."]:
             geocoding_service.add_task(point)
             updated_count += 1
    
    return jsonify(success=True, message=f"В очередь добавлено: {updated_count}", count=updated_count)


# === ЗАПУСК ПРИЛОЖЕНИЯ ===

def open_window(port):
    """Открывает окно в режиме приложения или браузере."""
    url = f'http://127.0.0.1:{port}'
    print(f"Открытие... {url}")

    win_w, win_h = 780, 700
    win_x, win_y = 80, 80
    
    # Edge в режиме App
    try:
        subprocess.Popen(
            f'start msedge --app={url} --window-size={win_w},{win_h} --window-position={win_x},{win_y}',
            shell=True
        )
        return
    except:
        pass
    
    # Chrome в режиме App
    try:
        subprocess.Popen(
            f'start chrome --app={url} --window-size={win_w},{win_h} --window-position={win_x},{win_y}',
            shell=True
        )
        return
    except:
        pass
    
    # Обычный браузер
    webbrowser.open_new_tab(url)


if __name__ == '__main__':
    PORT = 5002
    
    if HAS_WEBVIEW:
        try:
            window = webview.create_window(
                'Google → Yandex Coords', 
                app,
                width=780,
                height=700,
                resizable=True,
                min_size=(560, 440),
                background_color='#0f0f23'
            )
            webview.start()
            sys.exit(0)
        except Exception as e:
            print(f"Ошибка webview: {e}. Переключение на браузер.")
    
    threading.Timer(1.0, lambda: open_window(PORT)).start()
    app.run(port=PORT, debug=False)
