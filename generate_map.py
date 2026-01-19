#!/usr/bin/env python3
"""
Генератор GeoJSON карты из calibration.json для отображения в GitHub README
"""
import json
from pathlib import Path


def load_calibration_data(file_path):
    """Загружает данные калибровки из JSON файла"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_coordinates(coord_string):
    """Парсит строку координат в формате 'lat, lon' в список [lon, lat]"""
    # GeoJSON требует формат [longitude, latitude], а не [latitude, longitude]
    lat, lon = map(float, coord_string.split(','))
    return [lon, lat]


def create_geojson(calibration_data):
    """Создает GeoJSON структуру из данных калибровки"""
    features = []
    
    for idx, point in enumerate(calibration_data, 1):
        # Используем координаты Google как основные
        google_coords = parse_coordinates(point['google'])
        yandex_coords_str = point['yandex']
        
        # Создаем feature для каждой пары калибровочных точек
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": google_coords
            },
            "properties": {
                "title": f"Калибровочная точка #{idx}",
                "google": point['google'],
                "yandex": yandex_coords_str,
                "marker-color": "#FF6B6B",
                "marker-size": "medium",
                "marker-symbol": "circle"
            }
        }
        features.append(feature)
    
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    return geojson


def generate_map_file(output_path, geojson_data):
    """Сохраняет GeoJSON в файл"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(geojson_data, f, ensure_ascii=False, indent=2)
    print(f"✓ Карта сохранена в {output_path}")
    print(f"✓ Всего точек на карте: {len(geojson_data['features'])}")


def main():
    # Пути к файлам
    script_dir = Path(__file__).parent
    calibration_file = script_dir / 'calibration.json'
    output_file = script_dir / 'calibration_map.geojson'
    
    # Проверка существования файла
    if not calibration_file.exists():
        print(f"❌ Файл {calibration_file} не найден!")
        return
    
    # Генерация карты
    print("🗺️  Генерация карты калибровочных точек...")
    calibration_data = load_calibration_data(calibration_file)
    geojson_data = create_geojson(calibration_data)
    generate_map_file(output_file, geojson_data)
    
    print("\n📋 Для отображения карты в README добавьте:")
    print(f"```geojson")
    print("Вставьте содержимое calibration_map.geojson")
    print("```")
    print("\nИли используйте ссылку на файл в репозитории GitHub")


if __name__ == "__main__":
    main()
