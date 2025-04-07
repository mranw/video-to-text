import os
import re
import json
import logging


# Функция очистки текста
def clean_text(text: str) -> str:
    """
    Очищает текст от лишних пробелов, спецсимволов и шумов.
    """
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^А-Яа-яA-Za-z0-9,.?! ]', '', text)
    return text.strip()


def split_raw_transcript(raw_text: str) -> list:
    """
    Разбивает сырой текст из raw_transcript.txt на отдельные блоки.
    Каждый блок начинается с маркера "=== Файл:".
    Возвращает список словарей с полями:
      - file_path: полный путь, указанный в заголовке,
      - text: распознанный текст.
    """
    blocks = []
    # Разбиваем по строкам
    lines = raw_text.splitlines()
    current_block = None
    for line in lines:
        line = line.strip()
        if line.startswith("=== Файл:"):
            # Начало нового блока
            if current_block:
                blocks.append(current_block)
            # Извлекаем путь: удаляем "===" и "Файл:" и пробелы
            file_path = line.strip("=").replace("Файл:", "").strip()
            current_block = {"file_path": file_path, "text": ""}
        elif current_block is not None:
            # Если строка не пустая, добавляем к тексту блока
            if line:  # можно добавить фильтрацию пустых строк
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
      - section: название раздела (если имеется, иначе None),
      - lesson: название урока.
    """
    parts = file_path.split('/')
    if len(parts) < 4:
        return {}
    # Предполагаем, что parts[0] = "disk:", parts[1] = "Настя Рыбка", parts[2] = "Школа Насти Рыбки", parts[3] = название курса
    course = parts[3].strip()
    result = {"course": course, "section": None, "lesson": None}
    remaining = parts[4:]
    if not remaining:
        return result
    if len(remaining) == 1:
        # Если файл лежит непосредственно в папке курса – считаем это уроком
        result["lesson"] = remaining[0].strip()
    elif len(remaining) == 2:
        # Если в папке курса лежит папка-урок без раздела
        result["lesson"] = remaining[0].strip()
    else:
        # Если структура более сложная: первый элемент - раздел, второй – базовое название урока.
        result["section"] = remaining[0].strip()
        base_lesson = remaining[1].strip()
        # Если есть вложенные папки (между именем урока и именем файла)
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
    Содержимое .md файла:
      - Заголовок с названием урока
      - Раздел с распознанным текстом
      - (Опционально) YAML‑front matter с метаданными
    """
    for item in structured_data:
        course = item.get("course", "Без курса")
        section = item.get("section")
        lesson = item.get("lesson", "Без названия")
        text = item.get("text", "")
        # Создаем путь для курса
        course_dir = os.path.join(vault_path, sanitize_filename(course))
        if not os.path.exists(course_dir):
            os.makedirs(course_dir)
        # Если раздел указан, создаем подпапку
        if section:
            section_dir = os.path.join(course_dir, sanitize_filename(section))
            if not os.path.exists(section_dir):
                os.makedirs(section_dir)
            target_dir = section_dir
        else:
            target_dir = course_dir
        # Формируем имя файла для урока
        filename = sanitize_filename(lesson) + ".md"
        file_path = os.path.join(target_dir, filename)
        # Форматирование содержимого Markdown
        md_content = f"# {lesson}\n\n{text.strip()}\n"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            logging.info(f"Урок '{lesson}' сохранён в {file_path}")
        except Exception as e:
            logging.error(f"Ошибка сохранения файла {file_path}: {e}")


def sanitize_filename(name: str) -> str:
    """
    Удаляет или заменяет символы, недопустимые в именах файлов.
    """
    # Заменяем все символы, кроме букв, цифр, пробелов, дефисов и подчеркиваний на _
    name = re.sub(r'[^\w\s-]', '_', name)
    # Заменяем пробелы на _
    name = re.sub(r'\s+', '_', name)
    return name.strip("_")


def structure_and_export(raw_text: str, vault_path: str, output_json: str = "knowledge_base.json",
                         importance_override: str = None) -> str:
    """
    Полный pipeline:
      1. Очистка сырого текста.
      2. Разбиение на секции.
      3. Структурирование и добавление метаданных (course, section, lesson).
      4. Экспорт структурированных данных в JSON.
      5. Экспорт в виде файлов Markdown в Obsidian Vault.
    Возвращает отформатированный текст для справки.
    """
    cleaned = clean_text(raw_text)
    blocks = split_raw_transcript(cleaned)
    structured = []
    # Для каждого блока извлекаем структуру и объединяем с текстом
    for block in blocks:
        file_path = block.get("file_path", "")
        text = block.get("text", "").strip()
        # Используем parse_video_file_path для получения курса, раздела и урока
        meta = parse_video_file_path(file_path)
        # Добавляем сам текст из блока
        meta["text"] = text
        # Если importance_override задан, переопределяем уровень важности
        if importance_override:
            meta["importance"] = importance_override
        else:
            # Можно оставить значение по умолчанию, если в тексте есть "актуально"
            meta["importance"] = "high" if "актуально" in text.lower() else "low"
        structured.append(meta)

    # Экспорт в JSON
    export_to_json(structured, output_json)
    # Экспорт в файлы Markdown для Obsidian
    export_to_obsidian(structured, vault_path)

    # Формирование отформатированного текста для справки
    formatted_text = "\n\n".join(
        [
            f"Курс: {item.get('course')}\nРаздел: {item.get('section')}\nУрок: {item.get('lesson')}\nВажность: {item.get('importance')}\nТекст: {item.get('text')}"
            for item in structured]
    )
    return formatted_text


if __name__ == "__main__":
    # Читаем сырой текст из файла raw_transcript.txt
    try:
        with open("raw_transcript.txt", "r", encoding="utf-8") as f:
            raw_text = f.read()
    except Exception as e:
        print(f"Ошибка чтения файла raw_transcript.txt: {e}")
        exit(1)

    # Путь к Obsidian Vault (предполагается, что вы запускаете скрипт в корне вашего Vault)
    vault_path = os.getcwd()

    # Запускаем pipeline: структурируем текст и экспортируем как JSON и как файлы Markdown
    formatted_text = structure_and_export(raw_text, vault_path, output_json="knowledge_base.json",
                                          importance_override=None)

    # Сохраняем отформатированный текст для справки в файл formatted_transcript.txt
    try:
        with open("formatted_transcript.txt", "w", encoding="utf-8") as f:
            f.write(formatted_text)
    except Exception as e:
        print(f"Ошибка сохранения файла formatted_transcript.txt: {e}")
