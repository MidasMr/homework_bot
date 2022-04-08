import logging
from logging.handlers import RotatingFileHandler
import os
import sys
import time

from dotenv import load_dotenv
import requests
import telegram

from exceptions import ResponseStatusCodeError, ResponseError

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(stream=sys.stdout)
handler_2 = RotatingFileHandler(
    'my_logger.log', maxBytes=50000000, backupCount=5
)
logger.addHandler(handler)
logger.addHandler(handler_2)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - функция: %(funcName)s '
    '- номер строки: %(lineno)d - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

TOKEN_NAMES = ('TELEGRAM_CHAT_ID', 'TELEGRAM_TOKEN', 'PRACTICUM_TOKEN')

VERDICT_MESSAGE = 'Изменился статус проверки работы "{name}". {verdict}'
SEND_INFO_MESSAGE = 'сообщение отправлено, текст: {message}'
SEND_EXCEPTION_MESSGAE = (
    'Сбой при отправке сообщения "{messgae}", ошибка: {error}'
)
STATUS_CODE_EXCEPTION_MESSGAE = (
    'Код возврата отличен от "200": {status_code}. '
    'Параметры запроса к серверу: эндпоинт {endpoint}, '
    'хедеры {headers}, параметры {params}'
)
NOT_A_DICT_MESSAGE = 'Тип ответа от эндпоинта не словарь, а {type}'
NOT_A_LIST_MESSAGE = 'Тип информации о домашних работах не список, а {type}'
UNEXPECTED_HOMEWORK_STATUS_MESSAGE = (
    'Неожиданный статус домашней работы: {status}'
)
RESPONSE_ERROR_MESSAGE = (
    'Найден ключ ошибки в json ответа от эндпоинта: {response}'
)
REQUEST_EXCEPTION_MESSAGE = (
    'Произошел сбой сети: {error}'
    'Параметры запроса к серверу: эндпоинт {endpoint}, '
    'хедеры {headers}, параметры {params}'
)
MAIN_ERROR_MESSAGE = 'Сбой в работе программы: {error}'
NO_TOKEN_MESSAGE = (
    'Отсутсвует обязательная(-ые) переменная(-ые) окружения:{name}'
)


def send_message(bot, message):
    """Отправка сообщения ботом."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logger.info(SEND_INFO_MESSAGE.format(message=message))
        return True
    except Exception as error:
        logger.exception(SEND_EXCEPTION_MESSGAE.format(
            messgae=message, error=error
        ))
        return False


def get_api_answer(current_timestamp):
    """Получаем ответ от эндпоинта."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)

    except requests.exceptions.RequestException as error:
        raise IOError(
            error=error,
            endpoint=ENDPOINT,
            headers=HEADERS,
            params=params
        )

    json_response = response.json()
    if 'code' in json_response or 'error' in json_response:
        raise ResponseError(
            RESPONSE_ERROR_MESSAGE.format(response=json_response)
        )
    if response.status_code != 200:
        raise ResponseStatusCodeError(
            STATUS_CODE_EXCEPTION_MESSGAE.format(
                status_code=response.status_code,
                endpoint=ENDPOINT,
                headers=HEADERS,
                params=params
            )
        )

    return json_response


def check_response(response):
    """Проверка ответа от эндпоинта на корректность."""
    if not isinstance(response, dict):
        raise TypeError(NOT_A_DICT_MESSAGE.format(type=type(response)))
    if 'homeworks' not in response:
        raise KeyError(
            'В ответе от эндпоинта не найдено ключа "homeworks"'
        )
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(NOT_A_LIST_MESSAGE.format(type=type(homeworks)))
    return homeworks


def parse_status(homework):
    """Извлечение статуса о конкретной домашней работе."""
    name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(
            UNEXPECTED_HOMEWORK_STATUS_MESSAGE.format(status=status)
        )
    return VERDICT_MESSAGE.format(
        name=name, verdict=HOMEWORK_VERDICTS.get(status)
    )


def check_tokens():
    """Проверка доспутности всех переменных окружения."""
    result = True
    for name in TOKEN_NAMES:
        if globals()[name] is None:
            result = False
            logger.critical(NO_TOKEN_MESSAGE.format(name=name))
    return result


def main():
    """Основная логика работы бота."""
    current_timestamp = int(time.time())

    while check_tokens() is True:
        try:
            bot = telegram.Bot(token=TELEGRAM_TOKEN)
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                if send_message(bot, message):
                    current_timestamp = response.get(
                        'current_date', current_timestamp
                    )

        except Exception as error:
            message = MAIN_ERROR_MESSAGE.format(error=error)
            logger.error(message)
            send_message(bot, message)

        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
