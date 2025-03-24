# Video-to-Text Processor

Данный проект представляет собой автоматизированное решение для обработки видеофайлов с Яндекс.Диска. Скрипт выполняет следующие задачи:

- Рекурсивный обход папок на Яндекс.Диске и поиск видеофайлов.
- Скачивание видеофайлов для временной обработки.
- Извлечение аудиодорожки из видео с использованием **ffmpeg** с принудительным преобразованием в **OGG Opus** (моно, 48000 Гц, 64k битрейт).
- Определение длительности аудиофайла с помощью **ffprobe**.
- Загрузка аудиофайла в **Yandex Object Storage**.
- Асинхронное распознавание аудио через [Yandex SpeechKit](https://cloud.yandex.ru/services/speechkit) с использованием IAM-токена (или API-ключа).
- Динамическое определение интервала ожидания обработки в зависимости от длительности аудиофайла (но не менее 10 секунд).
- Сохранение распознанного текста в единый файл с добавлением новой информации, без перезаписи уже существующих данных.
- Отметка обработанных видеофайлов для предотвращения повторного распознавания.
- Демонический режим работы с логированием и обработкой ошибок, позволяющий работать в непрерывном режиме.
- Интервал сканирования папок на Яндекс.Диске установлен на **12 часов**.

## Требования

- **Python 3.x**
- Пакеты Python: `requests`, `boto3`, `python-dotenv` (dotenv), а также стандартные модули `logging`, `subprocess`, `json`, `time`, `os`
- **ffmpeg** и **ffprobe** (должны быть установлены в системе)
- OAuth-токен для Яндекс.Диска
- API-ключ для Yandex SpeechKit или IAM-токен сервисного аккаунта для SpeechKit
- Доступ к **Yandex Object Storage**

## Установка и настройка

### 1. Клонирование репозитория

```bash
git clone https://github.com/mr_anw/video-to-text.git
cd video-to-text
```

### 2. Создание виртуального окружения в /opt

На сервере принято запускать демоны в изолированном окружении. Например, создайте каталог для приложения в `/opt` и настройте виртуальное окружение:

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
pip install -r /path/to/video-to-text/requirements.txt
```

> **Примечание:** Замените `/path/to/video-to-text/` на фактический путь к клонированному репозиторию.

### 4. Создание и настройка файла `.env`

В корневой директории проекта (например, `/path/to/video-to-text`) создайте файл `.env` со следующим содержимым:

```ini
YANDEX_DISK_OAUTH_TOKEN=your_yandex_disk_token
YANDEX_SPEECHKIT_API_KEY=your_speechkit_api_key
# Если используется IAM-токен для SpeechKit, можно указать его:
YANDEX_SPEECHKIT_IAM_TOKEN=your_service_account_iam_token
YOBJECT_STORAGE_ACCESS_KEY=your_yandex_object_storage_access_key
YOBJECT_STORAGE_SECRET_KEY=your_yandex_object_storage_secret_key
```

### 5. Настройка сервиса systemd для автозапуска

Создайте файл сервиса, например, `/etc/systemd/system/video_to_text.service`:

```ini
[Unit]
Description=Video to Text Processor
After=network.target

[Service]
# Указываем полный путь к Python внутри виртуального окружения
ExecStart=/opt/video-to-text/venv/bin/python /path/to/video-to-text/video_processor.py
WorkingDirectory=/path/to/video-to-text
Restart=always
User=your_user
EnvironmentFile=/path/to/video-to-text/.env

[Install]
WantedBy=multi-user.target
```

> **Примечание:**  
> - Замените `/path/to/video-to-text` на фактический путь к вашему проекту.  
> - Замените `your_user` на имя пользователя, под которым должен запускаться сервис.

### 6. Запуск и проверка сервиса

После настройки сервиса выполните:

```bash
sudo systemctl daemon-reload
sudo systemctl enable video_to_text.service
sudo systemctl start video_to_text.service
sudo systemctl status video_to_text.service
```

Теперь скрипт будет автоматически запускаться при загрузке системы и работать в фоновом режиме в рамках виртуального окружения.

## Работа скрипта

- **Автоматический запуск:**  
  Скрипт запускается демоном (через systemd) и сканирует указанную папку на Яндекс.Диске каждые **12 часов**.

- **Обработка файлов:**  
  Скрипт обрабатывает только новые видеофайлы, которые ранее не были распознаны. После распознавания, текст добавляется в файл `recognized_texts.txt`, а обработанные файлы отмечаются в `processed_files.json`.

- **Логирование:**  
  Все действия, ошибки и события логируются в файл `video_processor.log`.

## Лицензия

Этот проект распространяется под лицензией **MIT License**.

## Контрибьюция

Если вы хотите внести вклад или у вас есть предложения по улучшению проекта, пожалуйста, создайте issue или pull request в репозитории.
