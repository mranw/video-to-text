import os
import json
import time
import subprocess
import requests
import logging
from urllib.parse import quote
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from modules.utils import load_config
import concurrent.futures

load_dotenv()
config = load_config()

YANDEX_DISK_OAUTH_TOKEN = os.environ.get("YANDEX_DISK_OAUTH_TOKEN")
DISK_FOLDER_PATH = config.get("DISK_FOLDER_PATH")
YANDEX_SPEECHKIT_API_KEY = os.environ.get("YANDEX_SPEECHKIT_API_KEY")
RECOGNITION_MODEL = config.get("RECOGNITION_MODEL", "general")
YOBJECT_STORAGE_BUCKET = config.get("YOBJECT_STORAGE_BUCKET")
YOBJECT_STORAGE_ACCESS_KEY = os.environ.get("YOBJECT_STORAGE_ACCESS_KEY")
YOBJECT_STORAGE_SECRET_KEY = os.environ.get("YOBJECT_STORAGE_SECRET_KEY")
YOBJECT_STORAGE_ENDPOINT = config.get("YOBJECT_STORAGE_ENDPOINT")
SPEECHKIT_ASYNC_URL = config.get("SPEECHKIT_ASYNC_URL")
LANGUAGE = config.get("LANGUAGE", "ru-RU")

# Параметры и настройки
PROCESSED_FILES_RECORD = "processed_files.json"
AUDIO_METADATA_FILE = "audio_files.json"  # Файл для сохранения информации об аудиофайлах
TEMP_DIR = "temp"
SCAN_INTERVAL = 43200  # 12 часов

# ====== Настройка логирования ======
logging.basicConfig(filename='video_processor.log',
                    level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

if not os.path.exists(PROCESSED_FILES_RECORD):
    with open(PROCESSED_FILES_RECORD, 'w', encoding='utf-8') as f:
        f.write("{}")

# ====== Инициализация клиента Yandex Object Storage ======
s3_client = boto3.client('s3',
                         endpoint_url=YOBJECT_STORAGE_ENDPOINT,
                         aws_access_key_id=YOBJECT_STORAGE_ACCESS_KEY,
                         aws_secret_access_key=YOBJECT_STORAGE_SECRET_KEY)


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

def save_audio_metadata(metadata_list):
    try:
        with open(AUDIO_METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(metadata_list, f, ensure_ascii=False, indent=4)
        logging.info("Аудио метаданные успешно сохранены.")
    except Exception as e:
        logging.error(f"Ошибка сохранения аудио метаданных: {e}")

def load_audio_metadata():
    try:
        with open(AUDIO_METADATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Ошибка загрузки аудио метаданных: {e}")
        return []


processed_files = load_processed_files()
# Глобальный список для хранения метаданных аудиофайлов в режиме deferred-general
audio_metadata_list = []


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
            return response.json().get("href")
        else:
            logging.error(f"Ошибка получения ссылки для {file_path}: {response.text}")
            return None
    except Exception as e:
        logging.error(f"Исключение при получении ссылки для {file_path}: {e}")
        return None


def download_file(url, local_path):
    """Скачивает файл по указанной ссылке и сохраняет его локально."""
    try:
        logging.info(f"Начало загрузки файла: {local_path}")
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))  # Получаем размер файла, если он доступен
            downloaded_size = 0
            chunk_size = 8192  # Размер чанка для чтения
            start_time = time.time()
            last_log_time = start_time

            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        current_time = time.time()

                        # Логирование каждые 10 секунд или по завершении загрузки
                        if current_time - last_log_time >= 10 or downloaded_size == total_size:
                            elapsed_time = current_time - start_time
                            download_speed = downloaded_size / (elapsed_time * 1024)  # КБ/с

                            if total_size > 0:
                                progress = (downloaded_size / total_size) * 100
                                logging.info(
                                    f"Загружено: {downloaded_size} / {total_size} байт ({progress:.2f}%), скорость: {download_speed:.2f} КБ/с")
                            else:
                                logging.info(f"Загружено: {downloaded_size} байт, скорость: {download_speed:.2f} КБ/с")

                            last_log_time = current_time

        logging.info(f"Файл успешно загружен: {local_path}")
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
            "ffmpeg", "-y", "-i", video_path, "-vn",
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
        return float(duration_str) if duration_str else None
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
    Если модель 'general' – используется динамический интервал ожидания,
    если 'deferred-general' – фиксированный интервал опроса с максимальным временем ожидания 24 часа.

    Ограничения:
      - Запросов на распознавание в час: 500 (POST-запросы, их обычно мало)
      - Запросов на проверку статуса операции в час: 2500
      - Тарифицированных часов аудио в сутки: 10000 (отсчет с момента первого запроса)
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

        # Определяем интервал опроса и максимальное время ожидания в зависимости от модели
        if model == "general":
            # Динамический интервал: предполагается, что audio_duration/6 - ориентировочное время обработки
            expected_processing_time = audio_duration / 6.0  # например, 60 сек аудио -> ~10 сек обработки
            sleep_interval = max(10, expected_processing_time / 3.0)  # минимум 10 сек
            max_wait_time = expected_processing_time * 10  # допускаем, что обработка займёт не более 10х ожидаемого времени
        elif model == "deferred-general":
            # Фиксированный интервал опроса для отложенного режима
            sleep_interval = 60  # опрашиваем раз в 60 сек
            max_wait_time = 86400  # 24 часа в секундах
        else:
            # По умолчанию используем динамический алгоритм
            expected_processing_time = audio_duration / 6.0
            sleep_interval = max(10, expected_processing_time / 3.0)
            max_wait_time = expected_processing_time * 10

        logging.info(f"Модель распознавания: {model}. Интервал опроса: {sleep_interval:.1f} сек, "
                     f"максимальное время ожидания: {max_wait_time:.1f} сек")
        start_time = time.time()

        while True:
            # Если превышено максимальное время ожидания, завершаем попытки
            if time.time() - start_time > max_wait_time:
                logging.error("Превышено максимальное время ожидания распознавания.")
                return ""
            time.sleep(sleep_interval)
            op_response = requests.get(op_url, headers=headers)
            logging.debug(f"HTTP статус: {op_response.status_code}")
            logging.debug(f"Ответ статуса: {op_response.text}")
            if op_response.status_code != 200:
                logging.error(f"Ошибка получения статуса (HTTP {op_response.status_code}): {op_response.text}")
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
      - Скачивает видео,
      - Извлекает аудио и конвертирует его в OGG_OPUS,
      - Загружает аудио на Object Storage,
      - Сохраняет метаданные (публичная ссылка и длительность) в режиме deferred-general,
        либо сразу запускает распознавание в режиме general.
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
        logging.info(f"Загрузка видеофайла: {file_path}")
        if not download_file(download_url, local_video):
            logging.error(f"Не удалось скачать файл: {file_path}")
            return
        logging.info(f"Видеофайл успешно загружен: {file_path}")

        logging.info(f"Извлечение аудио из видео: {file_path}")
        if not extract_audio(local_video, local_audio):
            logging.error(f"Не удалось извлечь аудио из файла: {file_path}")
            return
        logging.info(f"Аудио успешно извлечено: {file_path}")

        audio_duration = get_audio_duration(local_audio)
        if not audio_duration:
            logging.error(f"Не удалось получить длительность аудио для файла: {file_path}")
            return
        logging.info(f"Длительность аудио: {audio_duration} секунд")

        object_name = os.path.basename(local_audio)
        public_url = upload_to_object_storage(local_audio, object_name)
        if not public_url:
            logging.error(f"Ошибка загрузки аудио в Yandex Object Storage: {file_path}")
            return
        logging.info(f"Аудио загружено, публичная ссылка: {public_url}")

        if RECOGNITION_MODEL == "deferred-general":
            # Сохраняем метаданные аудиофайла для последующего параллельного распознавания.
            metadata = {
                "file_path": file_path,
                "public_url": public_url,
                "audio_duration": audio_duration
            }
            audio_metadata_list.append(metadata)
        else:
            recognized_text = async_recognize_speech(public_url, audio_duration, model=RECOGNITION_MODEL)
            if recognized_text:
                logging.info(f"Распознавание успешно для файла: {file_path}")
            else:
                logging.error(f"Распознавание не вернуло текст для файла: {file_path}")

        processed_files[file_path] = True
        save_processed_files(processed_files)
        return ""
    except Exception as e:
        logging.error(f"Исключение при обработке файла {file_path}: {e}")
        return ""
    finally:
        for temp_file in [local_video, local_audio]:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception as e:
                    logging.error(f"Не удалось удалить временный файл {temp_file}: {e}")


def process_deferred_recognition(metadata_list):
    """
    Отправляет запросы асинхронного распознавания для всех аудиофайлов в режиме deferred-general параллельно.
    """
    recognized_texts = []

    def recognize(metadata):
        public_url = metadata["public_url"]
        audio_duration = metadata["audio_duration"]
        result = async_recognize_speech(public_url, audio_duration, model="deferred-general")
        return result

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(recognize, md) for md in metadata_list]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                recognized_texts.append(result)
    return recognized_texts


def process_all_videos():
    global audio_metadata_list
    audio_metadata_list = []  # Сброс списка метаданных
    video_files = list_video_files(DISK_FOLDER_PATH)
    logging.info(f"Найдено видеофайлов: {len(video_files)}")
    for file_item in video_files:
        process_video_file(file_item)
    if RECOGNITION_MODEL == "deferred-general":
        # Сохраняем метаданные аудиофайлов для аудита и контроля.
        save_audio_metadata(audio_metadata_list)
        # Отправляем запросы на распознавание параллельно.
        recognized_texts = process_deferred_recognition(audio_metadata_list)
        return "\n".join(recognized_texts)
    else:
        # В режиме general распознавание происходило сразу.
        return ""
