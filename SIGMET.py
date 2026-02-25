import requests
import json
from datetime import datetime

FIR_LIST = ["UNNT", "UNKL", "UIII"]  # список FIR
URL = "https://aviationweather.gov/api/data/isigmet?format=json"

def fetch_sigmet_multi(fir_list):
    try:
        response = requests.get(URL, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Ошибка запроса: {e}")
        return {}

    if not isinstance(data, list):
        print("Неверный формат данных от API.")
        return {}

    fir_dict = {}

    for item in data:
        fir_id = item.get("firId")
        if fir_id not in fir_list:
            continue

        raw_text = item.get("rawSigmet", "")
        lat_list = []
        lon_list = []

        for point in item.get("coords", []):
            lat = point.get("lat")
            lon = point.get("lon")
            if lat is not None and lon is not None:
                lat_list.append(str(lat))
                lon_list.append(str(lon))

        # Добавляем только если есть данные
        if lat_list or raw_text:
            if fir_id not in fir_dict:
                fir_dict[fir_id] = {
                    "rawString": raw_text,
                    "lat_line": ','.join(lat_list),
                    "lon_line": ','.join(lon_list)
                }
            else:
                # Если уже есть SIGMET для этой FIR, объединяем
                fir_dict[fir_id]["rawString"] += "\n---\n" + raw_text
                fir_dict[fir_id]["lat_line"] += ',' + ','.join(lat_list)
                fir_dict[fir_id]["lon_line"] += ',' + ','.join(lon_list)

    return fir_dict

# Получаем данные
sigmet_data = fetch_sigmet_multi(FIR_LIST)

# Формируем JSON с временем запроса
output_data = {
    "lastFetch": datetime.utcnow().isoformat() + 'Z',
    "FIR": sigmet_data
}

# Сохраняем в файл
with open("sigmet.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=4)

# Выводим для проверки
for fir_id, data in sigmet_data.items():
    print(f"{fir_id} lat:")
    print(data["lat_line"])
    print(f"{fir_id} lon:")
    print(data["lon_line"])





