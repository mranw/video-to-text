import log_config  # Выполняет настройку логирования (не используется напрямую) # noqa: F401

import threading
import time
from queue import Queue
import logging
from concurrent.futures import ThreadPoolExecutor

from modules.video_processor import (
    list_video_files,
    process_video_file,
    load_upload_errors,
    save_upload_errors,
    DISK_FOLDER_PATH,
    async_recognize_speech,
    load_audio_queue,
    save_audio_queue
)

# Создаём потокобезопасную очередь для метаданных аудиофайлов
audio_queue = Queue()

# Загружаем элементы из persistent файла и добавляем их в очередь
persistent_items = load_audio_queue()
for item in persistent_items:
    audio_queue.put(item)

# Интервал сканирования (каждые 12 часов; для тестирования можно установить меньше)
SCAN_INTERVAL = 43200  # 12 часов


def reprocess_upload_errors(audio_queue):
    errors = load_upload_errors()
    if errors:
        logging.info(f"Найдено {len(errors)} файлов с ошибками загрузки. Попытка повторной загрузки.")
        remaining_errors = []
        for error_item in errors:
            # Здесь error_item содержит file_path, local_audio, audio_duration, а также данные, полученные из parse_video_file_path
            # Попытаемся повторно загрузить аудио для этого файла
            file_item = {"path": error_item["file_path"]}
            process_video_file(file_item, audio_queue)
            # Если после повторной обработки файл все ещё не загрузился, можно сохранить его для следующей попытки
            # (например, можно загрузить список из persistent ошибок заново)
            # Здесь для простоты оставляем повторную обработку без явного сохранения оставшихся ошибок.
        # После обработки можно очистить файл ошибок, если все успешно обработаны
        save_upload_errors([])


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
    Сохраняет полученный сырой текст в файл raw_transcript.txt.
    """
    public_url = metadata.get("public_url")
    audio_duration = metadata.get("audio_duration")
    file_path = metadata.get("file_path")
    recognized_text = async_recognize_speech(public_url, audio_duration, model="deferred-general")
    if recognized_text:
        logging.info(f"Распознавание для файла {file_path} завершено. Результат: {recognized_text}")

        # Сохраняем сырой текст в файл raw_transcript.txt (в режиме append)
        try:
            with open("raw_transcript.txt", "a", encoding="utf-8") as f:
                f.write(f"=== Файл: {file_path} ===\n")
                f.write("Распознанный текст:\n")
                f.write(recognized_text + "\n\n")
        except Exception as e:
            logging.error(f"Ошибка сохранения raw транскрипта для файла {file_path}: {e}")

        # После успешного распознавания удаляем элемент из persistent-хранилища
        current_items = load_audio_queue()
        updated_items = [item for item in current_items if item.get("file_path") != file_path]
        save_audio_queue(updated_items)
    else:
        logging.error(f"Распознавание для файла {file_path} не дало результата.")
    return recognized_text


def transcription_processing_thread():
    """
    Поток, который постоянно проверяет очередь audio_queue и параллельно отправляет
    запросы на расшифровку для каждого найденного аудиофайла.
    """
    with ThreadPoolExecutor(max_workers=30) as executor:
        while True:
            if not audio_queue.empty():
                metadata = audio_queue.get()
                future = executor.submit(process_transcription, metadata)
                future.add_done_callback(
                    lambda f: logging.error(
                        f"Ошибка в процессе расшифровки: {f.exception()}") if f.exception() else None
                )
            else:
                time.sleep(10)


if __name__ == "__main__":
    # Повторная обработка файлов с ошибками загрузки (из upload_errors.json)
    reprocess_upload_errors(audio_queue)

    # Запуск потоков обработки видео и расшифровки аудио
    video_thread = threading.Thread(target=video_processing_thread, daemon=True)
    transcription_thread = threading.Thread(target=transcription_processing_thread, daemon=True)

    video_thread.start()
    transcription_thread.start()

    # Основной поток остаётся активным
    while True:
        time.sleep(60)
