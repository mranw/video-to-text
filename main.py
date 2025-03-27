import threading
import time
from queue import Queue
import logging
from modules.video_processor import (
    list_video_files,
    process_video_file,
    DISK_FOLDER_PATH,
    async_recognize_speech,
    load_audio_queue,
    save_audio_queue
)

from concurrent.futures import ThreadPoolExecutor

# Создаём потокобезопасную очередь для метаданных аудиофайлов
audio_queue = Queue()

# Загружаем элементы из persistent файла и добавляем их в очередь
persistent_items = load_audio_queue()
for item in persistent_items:
    audio_queue.put(item)

# Интервал сканирования (каждые 12 часов; для тестирования можно установить меньше)
SCAN_INTERVAL = 43200  # 12 часов


def video_processing_thread():
    """
    Поток для последовательной обработки видео:
      - Сканирует папки на наличие новых видео
      - Обрабатывает видео и добавляет аудио-метаданные в очередь.
    """
    while True:
        logging.info("Начало сканирования видеофайлов")
        video_files = list_video_files(DISK_FOLDER_PATH)
        logging.info(f"Найдено видеофайлов: {len(video_files)}")
        for file_item in video_files:
            process_video_file(file_item, audio_queue)
        logging.info("Сканирование завершено. Ожидание следующего цикла.")
        time.sleep(SCAN_INTERVAL)


def process_transcription(metadata):
    """
    Отправляет запрос асинхронного распознавания для одного аудиофайла и
    после успешного получения результата удаляет элемент из persistent-хранилища.
    """
    public_url = metadata.get("public_url")
    audio_duration = metadata.get("audio_duration")
    file_path = metadata.get("file_path")
    recognized_text = async_recognize_speech(public_url, audio_duration, model="deferred-general")
    if recognized_text:
        logging.info(f"Распознавание для файла {file_path} завершено. Результат: {recognized_text}")
        # После успешного распознавания удаляем элемент из persistent-хранилища
        current_items = load_audio_queue()
        updated_items = [item for item in current_items if item.get("file_path") != file_path]
        save_audio_queue(updated_items)
        # TODO Здесь можно сохранить результат в файл или базу данных
    else:
        logging.error(f"Распознавание для файла {file_path} не дало результата.")
    return recognized_text


def transcription_processing_thread():
    """
    Поток, который постоянно проверяет очередь audio_queue и параллельно отправляет
    запросы на расшифровку для каждого найденного аудиофайла.
    """
    with ThreadPoolExecutor(max_workers=5) as executor:
        while True:
            if not audio_queue.empty():
                metadata = audio_queue.get()
                executor.submit(process_transcription, metadata).add_done_callback(
                    lambda future: logging.error(f"Ошибка: {future.exception()}") if future.exception() else None
                )
            else:
                time.sleep(10)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("main.log", encoding='utf-8'),
            logging.StreamHandler()  # Опционально: вывод в консоль
        ]
    )

    # Запуск потоков обработки видео и расшифровки аудио
    video_thread = threading.Thread(target=video_processing_thread, daemon=True)
    transcription_thread = threading.Thread(target=transcription_processing_thread, daemon=True)

    video_thread.start()
    transcription_thread.start()

    # Основной поток остаётся активным
    while True:
        time.sleep(60)
