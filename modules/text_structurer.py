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


def split_into_sections(text: str) -> list:
    """
    Разбивает текст на логические фрагменты с использованием маркеров "Раздел:" и "Урок:".
    """
    sections = re.split(r'Раздел:|Урок:', text)
    return [sec.strip() for sec in sections if sec.strip()]


def structure_text(sections: list) -> list:
    """
    Структурирует текст в список словарей с ключами:
      - question: формируется как первое предложение фрагмента;
      - answer: оставшаяся часть текста;
      - importance: уровень значимости ("high" или "low").

    По умолчанию определяется на основе наличия слова "актуально", но при override это значение заменяется.
    """
    structured_data = []
    for sec in sections:
        importance = "high" if "актуально" in sec.lower() else "low"
        sentences = sec.split('. ')
        question = sentences[0] if sentences else ""
        answer = '. '.join(sentences[1:]).strip() if len(sentences) > 1 else ""
        structured_data.append({
            "question": question,
            "answer": answer,
            "importance": importance
        })
    return structured_data


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


def process_course_text(raw_text: str, output_filename: str = "knowledge_base.json",
                        importance_override: str = None) -> str:
    """
    Полный pipeline обработки текста курса:
      1. Очистка текста,
      2. Разбиение на секции,
      3. Структурирование,
      4. Экспорт в JSON.

    Если задан параметр importance_override, то для каждого структурированного элемента уровень важности заменяется на это значение.
    Возвращает отформатированный текст для дальнейшего использования или сохранения.
    """
    cleaned = clean_text(raw_text)
    sections = split_into_sections(cleaned)
    structured = structure_text(sections)

    if importance_override is not None:
        for item in structured:
            item['importance'] = importance_override

    export_to_json(structured, output_filename)

    formatted_text = "\n\n".join(
        [f"Вопрос: {item['question']}\nОтвет: {item['answer']}\nВажность: {item['importance']}"
         for item in structured]
    )
    return formatted_text

if __name__ == "__main__":
    # Читаем сырой текст из файла, например, raw_transcript.txt
    try:
        with open("raw_transcript.txt", "r", encoding="utf-8") as f:
            raw_text = f.read()
    except Exception as e:
        print(f"Ошибка чтения файла raw_transcript.txt: {e}")
        exit(1)

    # Обрабатываем текст: очищаем, разбиваем на секции, структурируем и экспортируем базу знаний
    formatted_text = process_course_text(raw_text, output_filename="knowledge_base.json")

    # Сохраняем отформатированный текст в файл для дальнейшего использования
    try:
        with open("formatted_transcript.txt", "w", encoding="utf-8") as f:
            f.write(formatted_text)
    except Exception as e:
        print(f"Ошибка сохранения файла formatted_transcript.txt: {e}")