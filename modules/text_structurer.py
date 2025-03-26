# project/modules/text_structurer.py
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
      - importance: уровень значимости (high, если присутствует слово "актуально", иначе low).
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


def process_course_text(raw_text: str, output_filename: str = "knowledge_base.json") -> str:
    """
    Полный pipeline обработки текста курса:
      1. Очистка текста,
      2. Разбиение на секции,
      3. Структурирование,
      4. Экспорт в JSON.

    Возвращает отформатированный текст для дальнейшего использования или сохранения.
    """
    cleaned = clean_text(raw_text)
    sections = split_into_sections(cleaned)
    structured = structure_text(sections)
    export_to_json(structured, output_filename)

    # Формирование отформатированного текста для сохранения
    formatted_text = "\n\n".join(
        [f"Вопрос: {item['question']}\nОтвет: {item['answer']}\nВажность: {item['importance']}"
         for item in structured]
    )
    return formatted_text
