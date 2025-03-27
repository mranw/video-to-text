# Video-to-Text Processor & Knowledge Base Builder

Данный проект представляет собой комплексное решение для автоматизированной обработки видеофайлов с Яндекс.Диска с последующим созданием базы знаний на основе расшифрованных курсов. Конечная цель проекта – интеграция с LLaMA для создания AI-ассистента, который сможет отвечать клиенткам на вопросы на основе извлечённой информации из материалов школы.

На текущем этапе реализованы следующие задачи:
- Рекурсивный обход папок на Яндекс.Диске и поиск видеофайлов, с фильтрацией по имени папки (например, игнорирование исходных видео) и ограничением размера (файлы свыше 45 ГБ не обрабатываются).
- Скачивание видеофайлов для временной обработки.
- Извлечение аудиодорожки из видео с использованием **ffmpeg** (конвертация в **OGG Opus** с принудительным преобразованием в моно, 48000 Гц, 64k битрейт).
- Определение длительности аудиофайла с помощью **ffprobe**.
- Загрузка аудиофайла в **Yandex Object Storage**.
- Асинхронное распознавание аудио через [Yandex SpeechKit](https://cloud.yandex.ru/services/speechkit):
  - Режим **general** – с динамическим интервалом опроса.
  - Режим **deferred-general** – с фиксированным интервалом (60 сек) и максимальным временем ожидания (24 часа), что позволяет параллельно обрабатывать аудиофайлы.
- Сохранение полученных «сырого» расшифрованного текста:
  - **raw_transcript.txt** – текст, полученный текущим запуском скрипта (уровень важности **high**).
  - **recognized_texts.txt** – архивный текст, ранее расшифрованный (уровень важности **low**).
- Обработка полученного текста:
  - Очистка от лишних пробелов, спецсимволов и «шумов».
  - Разбиение на логические фрагменты (по курсам, разделам и урокам) с использованием информации, извлекаемой из путей видеофайлов (функция `parse_video_file_path`).
  - Структурирование информации в формат «question-answer» с указанием уровня важности (переопределяемым параметром `importance_override`).
- Экспорт обработанных данных в базы знаний:
  - `knowledge_base_high.json` – для актуальной (high) информации.
  - `knowledge_base_low.json` – для архивной (low) информации.
- Формирование отформатированных текстовых файлов:
  - **formatted_transcript_high.txt** – отформатированный текст для текущих видео.
  - **formatted_transcript_low.txt** – отформатированный текст для архивных уроков.
- Демонический режим работы: периодический запуск (сканирование каждые 12 часов), логирование событий и обработка ошибок.

## Структура проекта

Проект разделён на несколько модулей для повышения читаемости и масштабируемости:

```
project/
└── app/
    ├── main.py               # Точка входа: объединяет работу всех модулей и обрабатывает оба источника текста
    ├── .env                  # Файл с переменными окружения (YANDEX_DISK_OAUTH_TOKEN, YANDEX_SPEECHKIT_API_KEY и пр.)
    ├── requirements.txt      # Зависимости проекта
    └── modules/              # Пакет с основными модулями проекта
        ├── __init__.py       # Инициализация пакета, агрегирующая основные функции
        ├── video_processor.py# Обработка видео: скачивание, извлечение аудио, распознавание, формирование аудио-метаданных с информацией о курсе
        ├── text_structurer.py# Очистка и структурирование расшифрованного текста в базу знаний с использованием importance_override
        ├── database.py       # Функции для работы с базой знаний (сохранение, обновление, поиск)
        └── utils.py          # Вспомогательные функции и конфигурация проекта
```

## Требования

- **Python 3.x**
- Пакеты Python: `requests`, `boto3`, `python-dotenv` и другие, перечисленные в `requirements.txt`
- **ffmpeg** и **ffprobe** (должны быть установлены в системе)
- OAuth-токен для Яндекс.Диска
- API-ключ для Yandex SpeechKit или IAM-токен сервисного аккаунта для SpeechKit
- Доступ к **Yandex Object Storage**

## Установка и настройка

### 1. Клонирование репозитория

```bash
git clone https://github.com/yourusername/video-to-text.git
cd video-to-text
```

### 2. Создание виртуального окружения

Рекомендуется создать виртуальное окружение (например, в каталоге `/opt`):

```bash
sudo mkdir -p /opt/video-to-text
sudo chown $USER:$USER /opt/video-to-text
cd /opt/video-to-text
python3 -m venv venv
source venv/bin/activate
```

### 3. Установка зависимостей

Находясь в активированном виртуальном окружении, выполните:

```bash
pip install --upgrade pip
pip install -r app/requirements.txt
```

> **Примечание:** Замените `app/requirements.txt` на фактический путь к файлу, если структура отличается.

### 4. Создание и настройка файла `.env`

Перейдите в основную директорию скрипта и создайте там файл `.env` со следующим содержимым:

```ini
DISK_FOLDER_PATH=disk:/Папка
RECOGNITION_MODEL=general
LANGUAGE=ru-RU

YANDEX_DISK_OAUTH_TOKEN=your_yandex_disk_token
YANDEX_SPEECHKIT_API_KEY=your_speechkit_api_key
# Если используется IAM-токен для SpeechKit, укажите его:
YANDEX_SPEECHKIT_IAM_TOKEN=your_service_account_iam_token
YOBJECT_STORAGE_ACCESS_KEY=your_yandex_object_storage_access_key
YOBJECT_STORAGE_SECRET_KEY=your_yandex_object_storage_secret_key
YOBJECT_STORAGE_ENDPOINT=https://storage.yandexcloud.net
SPEECHKIT_ASYNC_URL=https://transcribe.api.cloud.yandex.net/speech/stt/v2/longRunningRecognize
```

### 5. Настройка сервиса systemd для автозапуска

Создайте файл сервиса, например, `/etc/systemd/system/video_to_text.service`, со следующим содержимым:

```ini
[Unit]
Description=Video-to-Text Processor & Knowledge Base Builder
After=network.target

[Service]
ExecStart=/opt/video-to-text/venv/bin/python /opt/video-to-text/main.py
WorkingDirectory=/opt/video-to-text
Restart=always
User=mr_anw
EnvironmentFile=/opt/video-to-text/.env

[Install]
WantedBy=multi-user.target
```

### 6. Запуск и проверка сервиса

После настройки выполните следующие команды:

```bash
sudo systemctl daemon-reload
sudo systemctl enable video_to_text.service
sudo systemctl start video_to_text.service
sudo systemctl status video_to_text.service
```

Если сервис запущен, вы увидите статус **Active: active (running)**. Логи работы сервиса будут записываться в файл `video_processor.log`.

## Работа проекта

- **Видео-процессор:**  
  Модуль `video_processor.py` осуществляет автоматический обход папок на Яндекс.Диске, скачивание видео, извлечение аудио, загрузку аудио в Object Storage и асинхронное распознавание (с учетом режима `general` или `deferred-general`). Также функция `parse_video_file_path` извлекает информацию о курсе, разделах и уроках из путей видеофайлов и формирует аудио-метаданные.

- **Обработка текста:**  
  Модуль `text_structurer.py` очищает расшифрованный текст, разбивает его на логические секции (по курсам, разделам и урокам) и структурирует данные в формате «question-answer». С использованием параметра `importance_override` база знаний делится на две части:
  - Актуальная информация (уровень **high**) – данные из нового распознавания (файл **raw_transcript.txt**).
  - Архивная информация (уровень **low**) – данные из ранее расшифрованного архива (файл **recognized_texts.txt**).

- **База знаний:**  
  Результаты обработки сохраняются в JSON-файлах:
  - `knowledge_base_high.json` – для актуальной информации.
  - `knowledge_base_low.json` – для архивной информации.
  Отформатированные тексты сохраняются в файлах:
  - **formatted_transcript_high.txt**
  - **formatted_transcript_low.txt**

- **Интеграция с LLaMA (будущая доработка):**  
  Планируется интеграция с LLaMA (например, с использованием llama.cpp или llama.cpp-python). При использовании метода Retrieval-Augmented Generation (RAG) модель сначала ищет релевантную информацию по уровню важности (сначала **high**, затем **low**), а затем генерирует ответ для клиента.

- **Логирование и устойчивость:**  
  Все операции, ошибки и события логируются в файл `video_processor.log`. Сервис работает в демоническом режиме с периодическим сканированием (каждые 12 часов) и предотвращением повторной обработки уже обработанных видеофайлов.

## Лицензия

Этот проект распространяется под лицензией **MIT License**.

## Контрибьюция

Если вы хотите внести вклад или у вас есть предложения по улучшению проекта, пожалуйста, создайте issue или pull request в репозитории.