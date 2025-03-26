from modules.video_processor import process_all_videos
from modules.text_structurer import process_course_text


def main():
    # Получаем объединённый текст, распознанный из всех видео
    recognized_text = process_all_videos()

    if recognized_text:
        # Сохраняем "сырой" текст сразу после распознавания
        with open("raw_transcript.txt", "w", encoding="utf-8") as raw_file:
            raw_file.write(recognized_text)
        print("Сырой текст сохранен в raw_transcript.txt")

        # Обработка и структурирование текста (формирование базы знаний)
        formatted_text = process_course_text(recognized_text, output_filename="knowledge_base.json")

        # Сохраняем доработанный и отформатированный текст
        with open("formatted_transcript.txt", "w", encoding="utf-8") as formatted_file:
            formatted_file.write(formatted_text)
        print("Отформатированный текст сохранен в formatted_transcript.txt")
    else:
        print("Распознанного текста не получено")


if __name__ == "__main__":
    main()
