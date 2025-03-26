import json
import logging

DATABASE_FILE = "knowledge_base.json"


def load_knowledge_base(filename: str = DATABASE_FILE) -> list:
    """
    Загружает базу знаний из JSON-файла.
    """
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        logging.info("База знаний успешно загружена.")
        return data
    except Exception as e:
        logging.error(f"Ошибка загрузки базы знаний: {e}")
        return []


def search_knowledge_base(query: str, data: list) -> list:
    """
    Ищет в базе знаний записи, содержащие запрос в вопросе или ответе.
    """
    results = []
    query_lower = query.lower()
    for entry in data:
        if query_lower in entry.get("question", "").lower() or query_lower in entry.get("answer", "").lower():
            results.append(entry)
    return results


def update_knowledge_base(new_data: list, filename: str = DATABASE_FILE) -> None:
    """
    Обновляет (перезаписывает) базу знаний новым набором данных.
    """
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=4)
        logging.info("База знаний успешно обновлена.")
    except Exception as e:
        logging.error(f"Ошибка обновления базы знаний: {e}")
