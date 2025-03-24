#!/usr/bin/env python3
import requests
import subprocess
import os
import json
import logging
import time
import boto3
from urllib.parse import quote
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

# ====== Конфигурация ======
YANDEX_DISK_OAUTH_TOKEN = os.environ.get("YANDEX_DISK_OAUTH_TOKEN")
DISK_FOLDER_PATH = "disk:/Настя Рыбка/Школа Насти Рыбки/Архив знаний"

YANDEX_SPEECHKIT_API_KEY = os.environ.get("YANDEX_SPEECHKIT_API_KEY")
YANDEX_SPEECHKIT_IAM_TOKEN = os.environ.get("YANDEX_SPEECHKIT_IAM_TOKEN")  # Используется API-ключ

SPEECHKIT_ASYNC_URL = "https://transcribe.api.cloud.yandex.net/speech/stt/v2/longRunningRecognize"
LANGUAGE = "ru-RU"
RECOGNITION_MODEL = "general"

YOBJECT_STORAGE_BUCKET = "video-to-text"
YOBJECT_STORAGE_ACCESS_KEY = os.environ.get("YOBJECT_STORAGE_ACCESS_KEY")
YOBJECT_STORAGE_SECRET_KEY = os.environ.get("YOBJECT_STORAGE_SECRET_KEY")
YOBJECT_STORAGE_ENDPOINT = "https://storage.yandexcloud.net"

PROCESSED_FILES_RECORD = "processed_files.json"
OUTPUT_TEXT_FILE = "recognized_texts.txt"

TEMP_DIR = "temp"

# Интервал сканирования - 12 часов
SCAN_INTERVAL = 43200

logging.basicConfig(filename='video_processor.log',
                    level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

if not os.path.exists(PROCESSED_FILES_RECORD):
    with open(PROCESSED_FILES_RECORD, 'w', encoding='utf-8') as f:
        f.write("{}")

# Инициализация клиента для Yandex Object Storage
s3_client = boto3.client('s3',
                         endpoint_url=YOBJECT_STORAGE_ENDPOINT,
                         aws_access_key_id=YOBJECT_STORAGE_ACCESS_KEY,
                         aws_secret_access_key=YOBJECT_STORAGE_SECRET_KEY)

# ====== Функции для работы с данными ======
def load_processed_files():
    """Загружает список уже обработанных файлов из JSON-файла."""
    if os.path.exists(PROCESSED_FILES_RECORD):
        try:
            with open(PROCESSED_FILES_RECORD, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Ошибка загрузки обработанных файлов: {e}")
            return {}
    return {}

def save_processed_files(processed):
    """Сохраняет обновлённый список обработанных файлов в JSON-файл."""
    try:
        with open(PROCESSED_FILES_RECORD, 'w', encoding='utf-8') as f:
            json.dump(processed, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения обработанных файлов: {e}")

processed_files = load_processed_files()

def list_video_files(folder_path):
    """
    Рекурсивно обходит указанную папку на Яндекс.Диске
    и возвращает список видеофайлов.
    """
    video_files = []
    headers = {"Authorization": f"OAuth {YANDEX_DISK_OAUTH_TOKEN}"}
    try:
        response = requests.get("https://cloud-api.yandex.net/v1/disk/resources",
                                params={"path": folder_path, "limit": 1000},
                                headers=headers)
        if response.status_code == 200:
            items = response.json().get("_embedded", {}).get("items", [])
            for item in items:
                if item.get("type") == "dir":
                    subfolder = item.get("path")
                    video_files.extend(list_video_files(subfolder))
                elif item.get("type") == "file" and item.get("mime_type", "").startswith("video/"):
                    video_files.append(item)
        else:
            logging.error(f"Ошибка получения списка файлов для {folder_path}: {response.text}")
    except Exception as e:
        logging.error(f"Исключение при получении списка файлов для {folder_path}: {e}")
    return video_files

def get_download_url(file_path):
    """Получает ссылку для скачивания файла с Яндекс.Диска."""
    headers = {"Authorization": f"OAuth {YANDEX_DISK_OAUTH_TOKEN}"}
    try:
        response = requests.get("https://cloud-api.yandex.net/v1/disk/resources/download",
                                params={"path": file_path},
                                headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data.get("href")
        else:
            logging.error(f"Ошибка получения ссылки для {file_path}: {response.text}")
            return None
    except Exception as e:
        logging.error(f"Исключение при получении ссылки для {file_path}: {e}")
        return None

def download_file(url, local_path):
    """Скачивает файл по указанной ссылке и сохраняет его локально."""
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return True
    except Exception as e:
        logging.error(f"Ошибка скачивания файла {url}: {e}")
        return False

def extract_audio(video_path, audio_path):
    """
    Извлекает аудиодорожку из видеофайла и конвертирует её в формат OggOpus с моно каналом.
    """
    try:
        command = [
            "ffmpeg", "-i", video_path, "-vn",
            "-c:a", "libopus", "-b:a", "64k",
            "-ac", "1",  # Принудительное преобразование в моно
            audio_path
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            logging.error(f"ffmpeg ошибка для {video_path}: {result.stderr.decode('utf-8')}")
            return False
        return True
    except Exception as e:
        logging.error(f"Исключение при извлечении аудио из {video_path}: {e}")
        return False

def get_audio_duration(file_path):
    """
    Определяет длительность аудиофайла с помощью ffprobe.
    Возвращает длительность в секундах или None в случае ошибки.
    """
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        duration_str = result.stdout.strip()
        return float(duration_str)
    except Exception as e:
        logging.error(f"Ошибка получения длительности аудио {file_path}: {e}")
        return None

def upload_to_object_storage(local_file, object_name):
    """
    Загружает файл в Yandex Object Storage в указанный бакет и возвращает публичную ссылку.
    """
    try:
        s3_client.upload_file(local_file, YOBJECT_STORAGE_BUCKET, object_name)
        public_url = f"{YOBJECT_STORAGE_ENDPOINT}/{YOBJECT_STORAGE_BUCKET}/{quote(object_name)}"
        return public_url
    except ClientError as e:
        logging.error(f"Ошибка загрузки {local_file} в Yandex Object Storage: {e}")
        return None

def async_recognize_speech(file_url, audio_duration, model=RECOGNITION_MODEL):
    """
    Отправляет запрос на асинхронное распознавание аудиофайла.
    Использует динамический интервал ожидания, зависящий от длительности аудио.
    """
    headers = {
        "Authorization": f"Api-Key {YANDEX_SPEECHKIT_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "config": {
            "specification": {
                "languageCode": LANGUAGE,
                "model": model
            },
            "audioEncoding": "OGG_OPUS"
        },
        "audio": {
            "uri": file_url
        }
    }
    try:
        response = requests.post(SPEECHKIT_ASYNC_URL, headers=headers, json=payload)
        logging.debug(f"Ответ на запрос распознавания (POST): {response.text}")
        if response.status_code != 200:
            logging.error(f"Ошибка запроса асинхронного распознавания: {response.text}")
            return ""
        operation = response.json()
        operation_id = operation.get('id')
        if not operation_id:
            logging.error(f"Не получен идентификатор операции: {operation}")
            return ""
        op_url = f"https://operation.api.cloud.yandex.net/operations/{operation_id}"
        logging.info(f"Запущена операция распознавания, id: {operation_id}")

        # Расчет динамического интервала ожидания
        expected_processing_time = audio_duration / 6.0  # Пример: 1 минута -> ~10 сек распознавания
        sleep_interval = max(10, expected_processing_time / 3.0)  # Интервал не меньше 10 секунд
        logging.info(f"Ожидаемое время обработки: {expected_processing_time:.1f} сек, интервал опроса: {sleep_interval:.1f} сек")

        while True:
            time.sleep(sleep_interval)
            op_response = requests.get(op_url, headers=headers)
            logging.debug(f"HTTP статус запроса статуса: {op_response.status_code}")
            logging.debug(f"Ответ статуса операции (GET): {op_response.text}")
            if op_response.status_code != 200:
                logging.error(f"Ошибка получения статуса операции (HTTP {op_response.status_code}): {op_response.text}")
                continue
            op_data = op_response.json()
            if op_data.get("done"):
                if "error" in op_data:
                    logging.error(f"Ошибка распознавания: {op_data['error']}")
                    return ""
                response_data = op_data.get("response", {})
                if "chunks" in response_data:
                    chunks = response_data["chunks"]
                    recognized_text = " ".join(
                        [chunk["alternatives"][0]["text"]
                         for chunk in chunks if chunk.get("alternatives")]
                    )
                    logging.debug(f"Распознанный текст: {recognized_text}")
                    return recognized_text
                else:
                    logging.error("Операция завершена, но результатов распознавания нет.")
                    return ""
            else:
                logging.info("Операция не завершена, ожидаем следующий опрос...")
    except Exception as e:
        logging.error(f"Исключение при асинхронном распознавании: {e}")
        return ""

def process_video_file(file_item):
    """
    Обрабатывает видеофайл:
      - Получает ссылку для скачивания;
      - Скачивает видео;
      - Извлекает аудио, конвертирует в OGG_OPUS с моно каналом;
      - Получает длительность аудио;
      - Загружает аудио в Yandex Object Storage;
      - Отправляет запрос на асинхронное распознавание;
      - Сохраняет распознанный текст;
      - Отмечает файл как обработанный.
    """
    file_path = file_item.get("path")
    if file_path in processed_files:
        logging.info(f"Файл уже обработан: {file_path}")
        return
    logging.info(f"Начало обработки файла: {file_path}")

    download_url = get_download_url(file_path)
    if not download_url:
        logging.error(f"Не удалось получить ссылку для скачивания файла: {file_path}")
        return

    local_video = os.path.join(TEMP_DIR, os.path.basename(file_path))
    local_audio = os.path.splitext(local_video)[0] + ".ogg"

    try:
        if not download_file(download_url, local_video):
            logging.error(f"Не удалось скачать файл: {file_path}")
            return

        if not extract_audio(local_video, local_audio):
            logging.error(f"Не удалось извлечь аудио из файла: {file_path}")
            return

        audio_duration = get_audio_duration(local_audio)
        if not audio_duration:
            logging.error(f"Не удалось получить длительность аудио для файла: {file_path}")
            return

        object_name = os.path.basename(local_audio)
        public_url = upload_to_object_storage(local_audio, object_name)
        if not public_url:
            logging.error(f"Ошибка загрузки аудио в Yandex Object Storage для файла: {file_path}")
            return

        logging.info(f"Аудио успешно загружено, публичная ссылка: {public_url}")

        recognized_text = async_recognize_speech(public_url, audio_duration)
        if recognized_text:
            entry = f"\n=== Файл: {file_path} ===\nРаспознанный текст:\n{recognized_text}\n"
            with open(OUTPUT_TEXT_FILE, 'a', encoding='utf-8') as f:
                f.write(entry)
            logging.info(f"Распознавание успешно для файла: {file_path}")
        else:
            logging.error(f"Распознавание не вернуло текст для файла: {file_path}")

        processed_files[file_path] = True
        save_processed_files(processed_files)

    except Exception as e:
        logging.error(f"Исключение при обработке файла {file_path}: {e}")
    finally:
        for temp_file in [local_video, local_audio]:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception as e:
                    logging.error(f"Не удалось удалить временный файл {temp_file}: {e}")

def main():
    while True:
        try:
            logging.info("Начало сканирования папки на Яндекс.Диске.")
            video_files = list_video_files(DISK_FOLDER_PATH)
            logging.info(f"Найдено видеофайлов: {len(video_files)}")
            for file_item in video_files:
                try:
                    process_video_file(file_item)
                except Exception as e:
                    logging.error(f"Ошибка обработки файла: {e}")
            logging.info(f"Сканирование завершено. Ожидание {SCAN_INTERVAL} секунд.")
        except Exception as e:
            logging.error(f"Ошибка в основном цикле: {e}")
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()
