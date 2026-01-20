import re

def guess_source_type(text):
    """Определяет вероятный источник координаты по точности"""
    matches = re.findall(r'\.(\d+)', text)
    if not matches: return "Неизвестно"
    avg_len = sum(len(x) for x in matches) / len(matches)
    
    print(f"  Text: {text}")
    print(f"  Matches: {matches}")
    print(f"  Avg length: {avg_len:.2f}")
    
    if avg_len > 8.0:
        return "Google"
    elif avg_len <= 8.0:
        return "Yandex"
    return "Неизвестно"

# Тестовые координаты
test_cases = [
    "54.996659, 82.804552",  # Яндекс
    "54.99665704896515, 82.80454371555194",  # Google
    "56.828106, 60.614287",  # Яндекс
    "56.82811805737119, 60.61426164412377",  # Google
]

print("=== Тест функции guess_source_type ===\n")
for i, coords in enumerate(test_cases, 1):
    print(f"Test {i}:")
    result = guess_source_type(coords)
    print(f"  Result: {result}")
    print()

# Проверка логики сравнения
print("\n=== Тест логики проверки разных типов ===\n")
coord1 = "54.996659, 82.804552"
coord2 = "54.99665704896515, 82.80454371555194"

type1 = guess_source_type(coord1)
type2 = guess_source_type(coord2)

print(f"Coord 1 type: {type1}")
print(f"Coord 2 type: {type2}")
print(f"Are they different? {type1 != type2}")
print(f"Both same type? {type1 == type2}")
