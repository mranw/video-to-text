import os
import re
import json
import logging

def clean_text(text: str) -> str:
    """
    Очищает текст от лишних пробелов, спецсимволов и шумов.
    """
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^А-Яа-яA-Za-z0-9,.?! ]', '', text)
    return text.strip()

def split_raw_transcript(raw_text: str) -> list:
    """
    Разбивает сырой текст из файла на отдельные блоки.
    Каждый блок начинается с маркера "=== Файл:".
    Возвращает список словарей с полями:
      - file_path: полный путь из заголовка,
      - text: распознанный текст.
    """
    blocks = []
    lines = raw_text.splitlines()
    current_block = None
    for line in lines:
        line = line.strip()
        if line.startswith("=== Файл:"):
            if current_block:
                blocks.append(current_block)
            file_path = line.strip("=").replace("Файл:", "").strip()
            current_block = {"file_path": file_path, "text": ""}
        elif current_block is not None:
            if line:
                current_block["text"] += line + " "
    if current_block:
        blocks.append(current_block)
    return blocks

def parse_video_file_path(file_path: str) -> dict:
    """
    Извлекает информацию о курсе, разделе и уроке из полного пути видеофайла.
    Пример пути:
      disk:/Настя Рыбка/Школа Насти Рыбки/Курс А/Раздел 1/Урок 2/Video.mp4
    Возвращает словарь с ключами:
      - course: название курса,
      - section: название раздела (если есть, иначе None),
      - lesson: название урока.
    """
    parts = file_path.split('/')
    if len(parts) < 4:
        return {}
    # Предполагаем структуру: disk:/Настя Рыбка/Школа Насти Рыбки/<Курс>/...
    course = parts[3].strip()
    result = {"course": course, "section": None, "lesson": None}
    remaining = parts[4:]
    if not remaining:
        return result
    if len(remaining) == 1:
        result["lesson"] = remaining[0].strip()
    elif len(remaining) == 2:
        result["lesson"] = remaining[0].strip()
    else:
        result["section"] = remaining[0].strip()
        base_lesson = remaining[1].strip()
        nested = remaining[2:-1]
        if nested:
            suffix = " ".join(f"({i + 1})" for i in range(len(nested)))
            result["lesson"] = f"{base_lesson} {suffix}"
        else:
            result["lesson"] = base_lesson
    return result

def export_to_json(data: list, filename: str = "knowledge_base.json") -> None:
    """
    Сохраняет структурированные данные в JSON-файл.
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logging.info(f"База знаний успешно сохранена в {filename}")
    except Exception as e:
        logging.error(f"Ошибка сохранения базы знаний: {e}")

def sanitize_filename(name: str) -> str:
    """
    Удаляет или заменяет символы, недопустимые в именах файлов.
    """
    name = re.sub(r'[^\w\s-]', '_', name)
    name = re.sub(r'\s+', '_', name)
    return name.strip("_")

def export_to_obsidian(structured_data: list, vault_path: str) -> None:
    """
    Экспортирует структурированные данные в виде файлов Markdown для Obsidian.
    Структура:
      vault_path/
        <Course>/
          (если есть разделы)
            <Section>/
              <Lesson>.md
          (если разделов нет)
            <Lesson>.md
    Каждый файл содержит YAML‑front matter с метаданными:
      course, section, lesson, data_type, importance.
    Затем следует заголовок и основной текст.
    """
    for item in structured_data:
        course = item.get("course", "Без курса")
        section = item.get("section")
        lesson = item.get("lesson", "Без названия")
        text = item.get("text", "").strip()
        data_type = item.get("data_type", "не указано")
        importance = item.get("importance", "low")
        # Создаем директорию курса
        course_dir = os.path.join(vault_path, sanitize_filename(course))
        if not os.path.exists(course_dir):
            os.makedirs(course_dir)
        # Если есть раздел, создаем папку раздела
        if section:
            section_dir = os.path.join(course_dir, sanitize_filename(section))
            if not os.path.exists(section_dir):
                os.makedirs(section_dir)
            target_dir = section_dir
        else:
            target_dir = course_dir
        filename = sanitize_filename(lesson) + ".md"
        file_path = os.path.join(target_dir, filename)
        # Формируем содержимое Markdown с YAML front matter
        md_content = (
            f"---\n"
            f"course: {course}\n"
            f"section: {section if section else 'none'}\n"
            f"lesson: {lesson}\n"
            f"data_type: {data_type}\n"
            f"importance: {importance}\n"
            f"---\n\n"
            f"# {lesson}\n\n{text}\n"
        )
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            logging.info(f"Урок '{lesson}' сохранён в {file_path}")
        except Exception as e:
            logging.error(f"Ошибка сохранения файла {file_path}: {e}")

def structure_and_export(raw_text: str, vault_path: str, output_json: str = "knowledge_base.json",
                           importance_override: str = None, data_type: str = "актуальные") -> str:
    """
    Полный pipeline обработки:
      1. Очистка сырого текста.
      2. Разбиение на блоки (по записям, где каждая запись содержит заголовок с путем и текст).
      3. Для каждого блока извлекается мета-информация (course, section, lesson) и добавляется содержимое.
      4. Добавляется тип данных (data_type) для каждого урока.
      5. Экспортируется база знаний в JSON.
      6. Экспортируется структура в виде файлов Markdown для Obsidian.
    Возвращает отформатированный текст для справки.
    """
    cleaned = clean_text(raw_text)
    blocks = split_raw_transcript(cleaned)
    structured = []
    for block in blocks:
        file_path = block.get("file_path", "")
        text = block.get("text", "").strip()
        meta = parse_video_file_path(file_path)
        meta["text"] = text
        meta["data_type"] = data_type  # Устанавливаем тип данных, переданный как параметр
        if importance_override:
            meta["importance"] = importance_override
        else:
            meta["importance"] = "high" if "актуально" in text.lower() else "low"
        structured.append(meta)
    export_to_json(structured, output_json)
    export_to_obsidian(structured, vault_path)
    formatted_text = "\n\n".join(
        [f"Курс: {item.get('course')}\nРаздел: {item.get('section')}\nУрок: {item.get('lesson')}\n"
         f"Data Type: {item.get('data_type')}\nВажность: {item.get('importance')}\nТекст: {item.get('text')}"
         for item in structured]
    )
    return formatted_text

if __name__ == "__main__":
    # Чтение сырого текста для актуальных данных
    try:
        with open("raw_transcript.txt", "r", encoding="utf-8") as f:
            raw_text_actual = f.read()
    except Exception as e:
        print(f"Ошибка чтения файла raw_transcript.txt: {e}")
        exit(1)

    # Чтение сырого текста для архивных данных
    try:
        with open("recognized_texts.txt", "r", encoding="utf-8") as f:
            raw_text_archive = f.read()
    except Exception as e:
        print(f"Ошибка чтения файла recognized_texts.txt: {e}")
        exit(1)

    # Путь к Obsidian Vault (скрипт запускается в корневой папке Vault)
    vault_path = os.getcwd()

    # Обработка актуальных данных
    formatted_actual = structure_and_export(raw_text_actual, vault_path,
                                              output_json="knowledge_base_actual.json",
                                              importance_override=None,
                                              data_type="актуальные")
    try:
        with open("formatted_transcript_actual.txt", "w", encoding="utf-8") as f:
            f.write(formatted_actual)
    except Exception as e:
        print(f"Ошибка сохранения файла formatted_transcript_actual.txt: {e}")

    # Обработка архивных данных
    formatted_archive = structure_and_export(raw_text_archive, vault_path,
                                               output_json="knowledge_base_archive.json",
                                               importance_override=None,
                                               data_type="архивные")
    try:
        with open("formatted_transcript_archive.txt", "w", encoding="utf-8") as f:
            f.write(formatted_archive)
    except Exception as e:
        print(f"Ошибка сохранения файла formatted_transcript_archive.txt: {e}")
