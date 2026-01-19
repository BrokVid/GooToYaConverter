import sys
import os
import json
import math
import re
import threading
import time
import pyperclip
import webbrowser
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from flask import Flask, render_template, jsonify, request

# Попытка импорта pywebview (опционально)
try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False

# --- ЛОГИКА КОНВЕРТАЦИИ И КОНСТАНТЫ ---

CONFIG_FILE = "calibration.json"
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

DEFAULT_A, DEFAULT_B, DEFAULT_C = 1.00002178, -0.000409512697, 0.0235679088
DEFAULT_D, DEFAULT_E, DEFAULT_F = -0.0000552760272, 0.99995881, 0.00565924534
coord_re = re.compile(r'([-+]?\d*\.\d+),\s*([-+]?\d*\.\d+)')

def get_distance(lat1, lon1, lat2, lon2):
    avg_lat = math.radians((lat1 + lat2) / 2.0)
    dlat = lat1 - lat2
    dlon = (lon1 - lon2) * math.cos(avg_lat)
    return math.sqrt(dlat**2 + dlon**2)

def convert_coords_advanced(glat, glon, calibration_data):
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

def reverse_geocode(lat, lon):
    """
    Получает название города и страны по координатам через Nominatim (OpenStreetMap).
    Возвращает строку вида "Город, Страна" на русском языке.
    """
    try:
        # Nominatim API - бесплатный, без ключей
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&accept-language=ru"
        
        # Добавляем User-Agent (обязательно для Nominatim)
        req = urllib.request.Request(url, headers={'User-Agent': 'GooToYaConverter/1.0'})
        
        # Делаем запрос с таймаутом
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            address = data.get('address', {})
            
            # Пытаемся получить город из разных полей
            city = (address.get('city') or 
                   address.get('town') or 
                   address.get('village') or 
                   address.get('municipality') or
                   address.get('county') or
                   address.get('state'))
            
            country = address.get('country', '')
            
            # Формируем результат
            if city and country:
                return f"{city}, {country}"
            elif city:
                return city
            elif country:
                return country
            else:
                return "Город не найден"
                
    except urllib.error.HTTPError:
        return "Не удалось получить данные"
    except urllib.error.URLError:
        return "Не удалось получить данные"
    except Exception as e:
        print(f"Geocoding error: {e}")
        return "Город не найден"

# --- СЛУЖЕБНЫЕ КЛАССЫ ---

class GeocodingWorker:
    def __init__(self):
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
    
    def add_task(self, point):
        """Добавляет точку в очередь на геокодирование"""
        # Сразу ставим статус "Загрузка...", чтобы UI реагировал
        point['location'] = "Загрузка..."
        self.queue.put(point)
    
    def _worker(self):
        while True:
            try:
                point = self.queue.get()
                if point is None: break
                
                # Проверяем, может уже заполнено (например, при импорте)
                # или статус не требует обновления (если мы не форсируем)
                # Но здесь мы предполагаем, что раз попало в очередь - надо обновить.
                
                location = get_location_for_point_sync(point)
                point['location'] = location
                state.save_config() # Сохраняем после каждого успешного обновления
                
                self.queue.task_done()
                
            except Exception as e:
                print(f"Worker error: {e}")
            
# Создаем воркер
import queue
geocoding_service = GeocodingWorker()

def get_location_for_point_sync(point_data):
    """Синхронная версия получения локации (с задержкой)"""
    # Если уже похоже на валидный город, пропускаем?
    # Нет, этот метод вызывается воркером явно.
    
    try:
        coords_str = point_data.get('google', '')
        m = coord_re.search(coords_str)
        if m:
            lat, lon = float(m.group(1)), float(m.group(2))
            # Задержка ПЕРЕД запросом, чтобы гарантировать интервал между вызовами
            time.sleep(1.2) 
            return reverse_geocode(lat, lon)
    except Exception as e:
        print(f"Error getting location: {e}")
    return "Город не найден"

def check_swap_heuristic(coord1, coord2, current_calibration):
    """
    Определяет, в каком порядке идут координаты (Google, Yandex) или (Yandex, Google).
    Возвращает кортеж (google_str, yandex_str).
    Использует текущую модель калибровки для проверки ошибки.
    """
    # Парсим числа
    m1 = coord_re.search(coord1)
    m2 = coord_re.search(coord2)
    
    if not m1 or not m2:
        return coord1, coord2
        
    c1 = (float(m1.group(1)), float(m1.group(2)))
    c2 = (float(m2.group(1)), float(m2.group(2)))
    
    # Гипотеза 1: 1=Google, 2=Yandex
    # Конвертируем c1 -> ожидаемый y1
    calib_list = state.get_calib_list()
    
    # Если калибровки нет совсем, используем дефолтные коэффициенты
    # (Дефолтные настроены на Google -> Yandex для Екатеринбурга/России)
    
    # Предсказание для Гипотезы 1 (c1 -> Y)
    # Используем простую линейную модель для быстроты или advanced
    def predict(lat, lon):
        # Если списка нет, берем дефолт
        if not calib_list:
             ylat = DEFAULT_A * lat + DEFAULT_B * lon + DEFAULT_C
             ylon = DEFAULT_D * lat + DEFAULT_E * lon + DEFAULT_F
             return ylat, ylon
        
        # Разбираем строку результата advanced конвертации обратно в float
        # Это немного коряво, но надежно
        res_str = convert_coords_advanced(lat, lon, calib_list)
        try:
            r_lat, r_lon = map(float, res_str.split(','))
            return r_lat, r_lon
        except:
             # Fallback
             return lat, lon

    p1_lat, p1_lon = predict(c1[0], c1[1])
    # Ошибка Гипотезы 1
    err1 = get_distance(p1_lat, p1_lon, c2[0], c2[1])
    
    # Гипотеза 2: 2=Google, 1=Yandex
    p2_lat, p2_lon = predict(c2[0], c2[1])
    # Ошибка Гипотезы 2
    err2 = get_distance(p2_lat, p2_lon, c1[0], c1[1])
    
    print(f"Swap Check: G->Y error={err1:.7f}, Y->G error={err2:.7f}")
    
    # Если ошибка во втором случае значительно меньше (например в 2 раза или просто меньше при больших числах)
    # Но для надежности проверим порог. Координаты почти одинаковые.
    # Обычно ошибка правильной пары < 0.0001 (метры). Неправильной - больше.
    
    if err2 < err1:
        print("Detected SWAP: User likely copied Yandex then Google.")
        return coord2, coord1
    else:
        return coord1, coord2

# --- ФОНОВЫЙ МОНИТОРИНГ ---
def monitor_clipboard_task():
    while state.is_monitoring:
        time.sleep(0.5)
        try:
            text = pyperclip.paste()
            if not text or text == state.last_clipboard:
                continue
            
            if len(text) > 5000:
                state.last_clipboard = text
                continue
                
            state.last_clipboard = text
            m = coord_re.search(text)
            if not m:
                continue
                
            coords_str = f"{m.group(1)}, {m.group(2)}"
            
            if state.is_calibrating:
                if state.pending_google is None:
                    # Это первая скопированная координата из пары
                    state.pending_google = coords_str
                    # Можно помигать в UI, что получена первая часть
                else:
                    # Это вторая координата. Проверяем порядок.
                    raw_1 = state.pending_google
                    raw_2 = coords_str
                    
                    # Применяем эвристику для определения кто есть кто
                    final_google, final_yandex = check_swap_heuristic(raw_1, raw_2, state)
                    
                    new_point = {"google": final_google, "yandex": final_yandex, "location": "Загрузка..."}
                    state.training_data.append(new_point)
                    
                    # Отправляем в очередь геокодирования
                    geocoding_service.add_task(new_point)
                    
                    # Автосохранение
                    state.save_config()
                    
                    state.pending_google = None
                continue

            glat, glon = float(m.group(1)), float(m.group(2))
            if len(m.group(1)) < 2 and len(m.group(2)) < 2: 
                continue

            calib_list = state.get_calib_list()
            res = convert_coords_advanced(glat, glon, calib_list)
            
            pyperclip.copy(res)
            state.last_clipboard = res
            state.last_found_coords = coords_str
            state.last_result_coords = res
            
        except Exception as e:
            print(f"Monitor error: {e}")
            state.is_monitoring = False
            break

# --- FLASK APP ---
# Указываем явные пути к шаблонам и статике для корректной работы в --onefile
template_folder = state.get_resource_path('templates')
static_folder = state.get_resource_path('static')
app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
# Отключаем кеширование статических файлов для разработки
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/convert', methods=['POST'])
def api_convert():
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
    status = "stopped"
    if state.is_monitoring:
        status = "calibrating" if state.is_calibrating else "working"
    
    return jsonify(
        status=status,
        last_found=state.last_found_coords,
        last_result=state.last_result_coords,
        points_count=len(state.training_data),
        calibration_status=state.is_calibrating,
        pending_google=state.pending_google is not None
    )

@app.route('/api/monitoring/start', methods=['POST'])
def start_monitoring():
    if not state.is_monitoring:
        state.is_monitoring = True
        state.is_calibrating = False
        state.pending_google = None
        thread = threading.Thread(target=monitor_clipboard_task, daemon=True)
        thread.start()
    return jsonify(success=True)

@app.route('/api/calibration/start', methods=['POST'])
def start_calibration():
    state.is_calibrating = True
    if not state.is_monitoring:
        state.is_monitoring = True
        thread = threading.Thread(target=monitor_clipboard_task, daemon=True)
        thread.start()
    state.pending_google = None
    return jsonify(success=True)

@app.route('/api/monitoring/stop', methods=['POST'])
def stop_monitoring():
    state.is_monitoring = False
    state.is_calibrating = False
    state.pending_google = None
    return jsonify(success=True)

@app.route('/api/calibration/data', methods=['GET', 'DELETE'])
def calibration_data():
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
                if item['google'] == del_item['google'] and item['yandex'] == del_item['yandex']:
                    should_delete = True
                    break
            if not should_delete:
                new_data.append(item)
        
        state.training_data = new_data
        return jsonify(success=True)

@app.route('/api/calibration/save', methods=['POST'])
def save_calib():
    success = state.save_config()
    return jsonify(success=success)

@app.route('/api/calibration/load', methods=['POST'])
def load_calib():
    success = state.load_config()
    return jsonify(success=success)

@app.route('/api/calibration/import', methods=['POST'])
def import_calib():
    try:
        new_data = request.json
        if not isinstance(new_data, list):
            return jsonify(success=False, error="Invalid format")
            
        # Валидация
        valid_count = 0
        for item in new_data:
            if 'google' in item and 'yandex' in item:
                # Добавляем если нет дубликатов
                is_exist = any(x['google'] == item['google'] and x['yandex'] == item['yandex'] for x in state.training_data)
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
    # Возвращаем JSON напрямую для скачивания на клиенте
    return jsonify(state.training_data)

@app.route('/api/clipboard/copy', methods=['POST'])
def clipboard_copy():
    text = request.json.get('text', '')
    pyperclip.copy(text)
    return jsonify(success=True)

@app.route('/api/calibration/update-locations', methods=['POST'])
def update_locations():
    """
    Обновляет местоположения для проблемных точек.
    """
    updated_count = 0
    for point in state.training_data:
        loc = point.get('location', '')
        # Обновляем, если пусто или ошибка
        if not loc or loc in ["Город не найден", "Не удалось получить данные", "Загрузка..."]:
             geocoding_service.add_task(point)
             updated_count += 1
    
    return jsonify(success=True, message=f"В очередь добавлено точек: {updated_count}", count=updated_count)


def open_window(port):
    """Пытается открыть окно в режиме приложения или просто браузер"""
    url = f'http://127.0.0.1:{port}'
    print(f"Opening... {url}")

    # Размер окна для режима app (Edge/Chrome)
    win_w, win_h = 820, 620
    win_x, win_y = 80, 60
    
    # Попытка открыть Edge в режиме App (Windows)
    try:
        subprocess.Popen(
            f'start msedge --app={url} --window-size={win_w},{win_h} --window-position={win_x},{win_y}',
            shell=True
        )
        return
    except: pass
    
    # Попытка открыть Chrome в режиме App
    try:
        subprocess.Popen(
            f'start chrome --app={url} --window-size={win_w},{win_h} --window-position={win_x},{win_y}',
            shell=True
        )
        return
    except: pass
    
    # Fallback на обычный браузер
    webbrowser.open_new_tab(url)

if __name__ == '__main__':
    PORT = 5001
    
    # Если есть webview и он работает - используем его (хотя из-за pythonnet скорее всего нет)
    if HAS_WEBVIEW:
        try:
            window = webview.create_window(
                'Google → Yandex Coords Pro', 
                app,
                width=780,
                height=600,
                resizable=True,
                min_size=(560, 440),
                background_color='#0f0f23'
            )
            webview.start()
            sys.exit(0)
        except Exception as e:
            print(f"Webview failed: {e}. Switching to browser mode.")
    
    # Запуск в браузере (Fallback)
    threading.Timer(1.0, lambda: open_window(PORT)).start()
    app.run(port=PORT, debug=False)
