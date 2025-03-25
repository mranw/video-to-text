from modules.video_processor import process_all_videos
from modules.text_structurer import process_course_text


def main():
    # Запуск обработки видео: собираем весь распознанный текст из видеофайлов
    recognized_text = process_all_videos()

    if recognized_text:
        # Обработка полученного текста: очистка, разбиение и экспорт в базу знаний (JSON)
        process_course_text(recognized_text, output_filename="knowledge_base.json")
        print("База знаний успешно сформирована.")
    else:
        print("Распознанного текста не получено.")


if __name__ == "__main__":
    main()
