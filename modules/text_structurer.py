import os
import re
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Путь к Obsidian Vault – скрипт запускается в корне Vault.
VAULT_ROOT = os.getcwd()


def read_file(filepath):
    """Читает содержимое файла с кодировкой UTF-8."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logging.error(f"Ошибка чтения файла {filepath}: {e}")
        return ""


def split_into_lessons(text):
    """
    Разбивает текст на блоки-уроки по маркеру '=== Файл:'.
    Возвращает список блоков (каждый блок – строка, содержащая заголовок и транскрипт).
    """
    lessons = re.split(r'\n=== Файл:', text)
    lessons = [lesson.strip() for lesson in lessons if lesson.strip()]
    logging.info(f"Найдено уроков: {len(lessons)}")
    return lessons


def extract_transcript(lesson_text):
    """
    Извлекает текст после маркера 'Распознанный текст:'.
    Если маркер не найден – возвращает пустую строку.
    """
    match = re.search(r'Распознанный текст:\s*(.*)', lesson_text, re.DOTALL)
    if match:
        transcript = match.group(1).strip()
        return transcript
    else:
        logging.warning("Маркер 'Распознанный текст:' не найден в блоке урока.")
        return ""


def remove_extension(filename):
    """Возвращает имя файла без расширения."""
    return os.path.splitext(filename)[0].strip()


def parse_file_path(header_line, source):
    """
    Извлекает информацию о курсе, модуле и уроке из заголовка блока.

    header_line – строка заголовка, например:
    "=== Файл: disk:/Настя Рыбка/Школа Насти Рыбки/Архив знаний/БДСМ/Модуль 1. Теория/Урок 1. Роль хозяина в отношениях/1 Структура доминирования  Роль хозяина.mp4 ==="

    source – "raw" или "recognized".

    Алгоритм:
    1. Удаляем начальные и конечные символы "===".
    2. Ищем маркер "Школа Насти Рыбки/" и берём всё, что следует после него.
       Если маркер не найден, используем всё содержимое после "Файл:".
    3. Разбиваем оставшуюся строку по символу "/".
    4. Для recognized_texts.txt, если первый элемент равен "Архив знаний", то:
         - Если длина списка равна 3, то: [ "Архив знаний", course, filename ]
         - Если длина равна 4, то: [ "Архив знаний", course, lesson_dir, filename ]
         - Если длина >= 5, то: [ "Архив знаний", course, module, lesson_dir, filename, ... ]
    5. Для raw_transcript.txt структура ожидается как:
         - Если длина списка равна 2: [ course, filename ]
         - Если равна 3: [ course, module, filename ]
         - Если >= 4: [ course, module, lesson_dir, ... ]
    """
    # Удаляем внешние символы "=" и пробелы
    header_line = header_line.strip(" =")
    # Найдём позицию маркера "Школа Насти Рыбки/"
    marker = "Школа Насти Рыбки/"
    if marker in header_line:
        index = header_line.find(marker) + len(marker)
        path_part = header_line[index:].strip()
    else:
        # Если маркер не найден, удаляем префикс "Файл:" если он есть
        path_part = header_line.replace("Файл:", "").strip()

    # Разбиваем путь по "/"
    parts = [p.strip() for p in path_part.split("/") if p.strip()]

    course = module = lesson = "Unknown"

    if source == "raw":
        # Пример структуры: ["1-я ступень", "Первая ступень Настя Рыбка.mov"]
        if len(parts) == 2:
            course = parts[0]
            lesson = remove_extension(parts[1])
            module = None
        elif len(parts) == 3:
            course = parts[0]
            module = parts[1]
            lesson = remove_extension(parts[2])
        elif len(parts) >= 4:
            course = parts[0]
            module = parts[1]
            # Если есть отдельная директория для урока – используем её
            lesson = parts[2]
        else:
            logging.warning("Непредвиденная структура пути для raw: " + str(parts))
    elif source == "recognized":
        # Ожидаем, что первый элемент равен "Архив знаний"
        if parts and parts[0] == "Архив знаний":
            if len(parts) == 3:
                # ["Архив знаний", course, filename]
                course = parts[1]
                module = None
                lesson = remove_extension(parts[2])
            elif len(parts) == 4:
                # ["Архив знаний", course, lesson_dir, filename]
                course = parts[1]
                module = None
                lesson = parts[2]
            elif len(parts) >= 5:
                # ["Архив знаний", course, module, lesson_dir, filename, ...]
                course = parts[1]
                module = parts[2]
                lesson = parts[3]
            else:
                logging.warning("Непредвиденная структура пути для recognized: " + str(parts))
        else:
            # Если структура не соответствует ожидаемой, применяем логику похожую на raw.
            if len(parts) == 2:
                course = parts[0]
                lesson = remove_extension(parts[1])
                module = None
            elif len(parts) == 3:
                course = parts[0]
                module = parts[1]
                lesson = remove_extension(parts[2])
            elif len(parts) >= 4:
                course = parts[0]
                module = parts[1]
                lesson = parts[2]
            else:
                logging.warning("Непредвиденная структура пути для recognized (fallback): " + str(parts))
    return course, module, lesson


def create_markdown_file(course, module, lesson, transcript, importance):
    """
    Создает .md файл с YAML front matter для Obsidian.
    Файл сохраняется по пути: VAULT_ROOT/course/[module/]<lesson>.md
    """
    # Формируем директорию для курса
    course_dir = os.path.join(VAULT_ROOT, course)
    os.makedirs(course_dir, exist_ok=True)

    # Если модуль задан – создаём поддиректорию
    if module:
        target_dir = os.path.join(course_dir, module)
    else:
        target_dir = course_dir
    os.makedirs(target_dir, exist_ok=True)

    # Имя файла – название урока с расширением .md
    filename = f"{lesson}.md"
    filepath = os.path.join(target_dir, filename)

    # Форматирование содержимого для Obsidian с YAML front matter
    md_content = f"""---
title: "{lesson}"
course: "{course}"
module: "{module if module else ''}"
importance: "{importance}"
---

{transcript}
"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        logging.info(f"Создан файл: {filepath}")
    except Exception as e:
        logging.error(f"Ошибка при создании файла {filepath}: {e}")


def process_file(input_filepath, source, importance):
    """
    Обрабатывает входной файл (raw_transcript.txt или recognized_texts.txt):
    - Читает содержимое.
    - Разбивает его на блоки-уроки.
    - Для каждого блока:
        * Извлекает заголовок (первая строка блока) как путь файла.
        * Парсит путь для определения course, module и lesson.
        * Извлекает транскрипт.
        * Создает markdown файл в соответствующей директории.
    """
    logging.info(f"Обработка файла {input_filepath} (source: {source}, importance: {importance})")
    content = read_file(input_filepath)
    if not content:
        logging.error(f"Файл {input_filepath} пуст или не прочитан.")
        return

    lessons = split_into_lessons(content)
    for lesson_block in lessons:
        lines = lesson_block.splitlines()
        if not lines:
            continue
        header_line = lines[0]
        transcript = extract_transcript(lesson_block)
        if not transcript:
            continue

        course, module, lesson = parse_file_path(header_line, source)
        # Если название урока не найдено, попробуем взять его из последнего сегмента заголовка
        if lesson == "Unknown" or not lesson:
            parts = header_line.split("/")
            if parts:
                lesson = remove_extension(parts[-1])
        create_markdown_file(course, module, lesson, transcript, importance)


def main():
    """
    Основная функция:
    - Обрабатывает файл raw_transcript.txt с актуальными данными (importance: high).
    - Обрабатывает файл recognized_texts.txt с архивными данными (importance: low).
    Все файлы создаются в текущей директории (корень Obsidian Vault).
    """
    raw_transcript_path = "raw_transcript.txt"
    recognized_texts_path = "recognized_texts.txt"

    process_file(raw_transcript_path, source="raw", importance="high")
    process_file(recognized_texts_path, source="recognized", importance="low")
    logging.info("Обработка всех файлов завершена.")


if __name__ == '__main__':
    main()
