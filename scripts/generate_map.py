#!/usr/bin/env python3
"""
Генератор GeoJSON карты из calibration.json для отображения в GitHub README.
"""
import json
from pathlib import Path


def load_calibration_data(file_path):
    """Загружает данные калибровки из JSON файла."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_coordinates(coord_string):
    """Парсит строку координат в формате [lon, lat] для GeoJSON."""
    lat, lon = map(float, coord_string.split(','))
    return [lon, lat]


def create_geojson(calibration_data):
    """Создает GeoJSON структуру из данных калибровки."""
    features = []
    
    for idx, point in enumerate(calibration_data, 1):
        google_coords = parse_coordinates(point['google'])
        yandex_coords_str = point['yandex']
        
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
    
    return {
        "type": "FeatureCollection",
        "features": features
    }


def generate_map_file(output_path, geojson_data):
    """Сохраняет GeoJSON в файл."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(geojson_data, f, ensure_ascii=False, indent=2)
    print(f"✓ Карта сохранена: {output_path}")
    print(f"✓ Всего точек: {len(geojson_data['features'])}")


def main():
    # Корень проекта — на уровень выше папки scripts
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / 'data'
    calibration_file = data_dir / 'calibration.json'
    output_file = data_dir / 'calibration_map.geojson'
    
    if not calibration_file.exists():
        print(f"❌ Файл {calibration_file} не найден!")
        return
    
    print("🗺️  Генерация карты калибровочных точек...")
    calibration_data = load_calibration_data(calibration_file)
    geojson_data = create_geojson(calibration_data)
    generate_map_file(output_file, geojson_data)


if __name__ == "__main__":
    main()
