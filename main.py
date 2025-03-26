from modules.video_processor import process_all_videos
from modules.text_structurer import process_course_text


def main():
    # Обработка новых видео: получение "сырого" текста с текущего распознавания
    raw_transcript = process_all_videos()

    if raw_transcript:
        with open("raw_transcript.txt", "w", encoding="utf-8") as raw_file:
            raw_file.write(raw_transcript)
        print("Сырой текст текущих видео сохранен в raw_transcript.txt")

        # Обработка "сырого" текста с уровнем важности high
        formatted_high = process_course_text(raw_transcript, output_filename="knowledge_base_high.json",
                                             importance_override="high")
        with open("formatted_transcript_high.txt", "w", encoding="utf-8") as formatted_file:
            formatted_file.write(formatted_high)
        print("Отформатированный текст (high) сохранен в formatted_transcript_high.txt")
    else:
        print("Распознанного текста из текущих видео не получено")

    # Обработка архивного файла recognized_texts.txt
    try:
        with open("recognized_texts.txt", "r", encoding="utf-8") as archive_file:
            archive_text = archive_file.read()
        # Обработка архивного "сырого" текста с уровнем важности low
        formatted_low = process_course_text(archive_text, output_filename="knowledge_base_low.json",
                                            importance_override="low")
        with open("formatted_transcript_low.txt", "w", encoding="utf-8") as formatted_low_file:
            formatted_low_file.write(formatted_low)
        print("Отформатированный текст (low) сохранен в formatted_transcript_low.txt")
    except Exception as e:
        print("Файл recognized_texts.txt не найден или произошла ошибка при его обработке:", e)


if __name__ == "__main__":
    main()
