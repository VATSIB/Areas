import os
import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime, timedelta, timezone
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

def extract_level(level_str):
    if not level_str:
        return 0
    if "AGL" in level_str or "AMSL" in level_str:
        numeric_value = int(level_str.replace("AGL", "").replace("AMSL", ""))
        return int((numeric_value * 3.280839895) / 100)
    elif "F" in level_str:
        return int(level_str.replace("F", ""))
    return 0


def determine_remark(level_str):
    if not level_str:
        return ""
    if "AGL" in level_str:
        return "MAGL"
    elif "AMSL" in level_str:
        return "MAMSL"
    elif "F" in level_str:
        return "FL"
    return ""


def fetch_xml_data():
    url = os.getenv("XML_DATA_URL", "").strip()
    if not url:
        raise ValueError("❌ XML_DATA_URL не задан в secrets")

    # Определяем, использовать ли прокси
    use_proxy = os.getenv("USE_PROXY", "false").strip().lower() in ("true", "1", "yes")
    proxy_settings = None

    if use_proxy:
        http_proxy = os.getenv("HTTP_PROXY", "").strip()
        https_proxy = os.getenv("HTTPS_PROXY", "").strip()
        if http_proxy and https_proxy:
            proxy_settings = {"http": http_proxy, "https": https_proxy}
        elif http_proxy:
            proxy_settings = {"http": http_proxy, "https": http_proxy}
        else:
            print("⚠️  USE_PROXY=true, но HTTP_PROXY/HTTPS_PROXY не заданы. Используем прямое соединение.")
            use_proxy = False

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "ru,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Sec-Ch-Ua": '"Microsoft Edge";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Cache-Control": "max-age=0",
        "Referer": "https://app.matfmc.ru/agreedroutesview/AirspaceAvailabilityBulletin.aspx?source=gc&tab=tra"
    }

    try:
        print(f"📡 Запрос к: {url}")
        if use_proxy:
            print(f"🔌 Используется прокси: {proxy_settings}")
        
        response = requests.get(
            url,
            headers=headers,
            proxies=proxy_settings,
            timeout=20,
            verify=False
        )
        response.raise_for_status()
        print(f"✅ Успешно! Статус: {response.status_code}")
        return response.text

    except requests.exceptions.ProxyError as e:
        print(f"❌ Ошибка прокси: {e}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка запроса: {e}")
        return None


def process_tra_zone(tra, target_date):
    zc = tra.find("zc").text.strip() if tra.find("zc") is not None else ""
    if not any(code in zc for code in ["UNNT", "UNKL", "UIII"]):
        return None

    area_code = tra.find("areacode").text.strip() if tra.find("areacode") is not None else ""
    level_from = tra.find("levelfrom").text if tra.find("levelfrom") is not None else ""
    level_to = tra.find("levelto").text if tra.find("levelto") is not None else ""
    date_from = tra.find("datefrom").text if tra.find("datefrom") is not None else ""
    date_to = tra.find("dateto").text if tra.find("dateto") is not None else ""

    try:
        start = datetime.strptime(date_from, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
        end = datetime.strptime(date_to, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    if start.date() <= target_date <= end.date():
        remark_from = determine_remark(level_from)
        remark_to = determine_remark(level_to)
        remark = remark_from if remark_from == remark_to else f"{remark_from}, {remark_to}".strip(", ")

        return {
            "name": area_code,
            "minimum_fl": extract_level(level_from),
            "maximum_fl": extract_level(level_to),
            "start_datetime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_datetime": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "remark": remark,
            "active_date": target_date.strftime("%Y-%m-%d")
        }
    return None


def main():
    xml_data = fetch_xml_data()
    if not xml_data:
        print("❌ Не удалось загрузить XML данные.")
        exit(1)

    try:
        root = ET.fromstring(xml_data)
        today = datetime.now(timezone.utc).date()
        tomorrow = today + timedelta(days=1)
        areas = []

        for tra in root.findall("tra"):
            for day in [today, tomorrow]:
                res = process_tra_zone(tra, day)
                if res:
                    areas.append(res)

        now = datetime.now(timezone.utc)
        result = {
            "notice_info": {
                "valid_wef": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "valid_til": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "released_on": now.strftime("%Y-%m-%dT%H:%M:%SZ")
            },
            "areas": areas
        }

        with open("output.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4, ensure_ascii=False)

        print("✅ output.json успешно создан")

    except ET.ParseError as e:
        print(f"❌ Ошибка парсинга XML: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        exit(1)


if __name__ == "__main__":
    main()
