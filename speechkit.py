import requests
import logging
from config import LOGS
from creds import get_creds  # модуль для получения токенов

iam_token, folder_id = get_creds()  # получаем iam_token и folder_id из файлов

# настраиваем запись логов в файл
logging.basicConfig(filename=LOGS, level=logging.ERROR,
                    format="%(asctime)s FILE: %(filename)s IN: %(funcName)s MESSAGE: %(message)s", filemode="w")


def speech_to_text(data: bytes):
    # Указываем параметры запроса
    params = "&".join([
        "topic=general",
        f"folderId={folder_id}",
        "lang=ru-RU"
    ])

    # Аутентификация через IAM-токен
    headers = {
        'Authorization': f'Bearer {iam_token}',
    }

    response = requests.post(
        f"https://stt.api.cloud.yandex.net/speech/v1/stt:recognize?{params}",
        headers=headers,
        data=data
    )
    # Читаем json в словарь
    decoded_data = response.json()

    if not decoded_data.get("result"):
        return False, "Я не услышал речь. Пожалуйста, отправьте ещё раз."

    # Проверяем, не произошла ли ошибка при запросе
    if decoded_data.get("error_code") is None:
        return True, decoded_data.get("result")
    else:
        return False, f"При запросе в SpeechKit возникла ошибка: {decoded_data["error_message"]}"
