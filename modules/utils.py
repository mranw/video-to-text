import os
from dotenv import load_dotenv

load_dotenv()


def load_config() -> dict:
    """
    Загружает конфигурацию из переменных окружения.
    """
    return {
        "YANDEX_DISK_OAUTH_TOKEN": os.environ.get("YANDEX_DISK_OAUTH_TOKEN"),
        "DISK_FOLDER_PATH": os.environ.get("DISK_FOLDER_PATH", "disk:/Настя Рыбка/Школа Насти Рыбки/1-я ступень"),
        "YANDEX_SPEECHKIT_API_KEY": os.environ.get("YANDEX_SPEECHKIT_API_KEY"),
        "RECOGNITION_MODEL": os.environ.get("RECOGNITION_MODEL", "general"),
        "YOBJECT_STORAGE_BUCKET": os.environ.get("YOBJECT_STORAGE_BUCKET", "video-to-text"),
        "YOBJECT_STORAGE_ACCESS_KEY": os.environ.get("YOBJECT_STORAGE_ACCESS_KEY"),
        "YOBJECT_STORAGE_SECRET_KEY": os.environ.get("YOBJECT_STORAGE_SECRET_KEY"),
        "YOBJECT_STORAGE_ENDPOINT": os.environ.get("YOBJECT_STORAGE_ENDPOINT", "https://storage.yandexcloud.net"),
        "SPEECHKIT_ASYNC_URL": os.environ.get("SPEECHKIT_ASYNC_URL", "https://transcribe.api.cloud.yandex.net/speech/stt/v2/longRunningRecognize"),
        "LANGUAGE": os.environ.get("LANGUAGE", "ru-RU")
    }
