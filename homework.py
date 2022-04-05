import logging
import os
import sys
import time

from dotenv import load_dotenv
import requests
import telegram

from exceptions import ResponseStausCodeError

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
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

VERDICT_MESSAGE = 'Изменился статус проверки работы "{name}". {verdict}'


def send_message(bot, message):
    """Отправка сообщения ботом."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logger.info(f'сообщение отправлено, текст: {message}')
        return True
    except Exception as error:
        logger.exception(f'Сбой при отправке сообщения, ошибка: {error}')


def get_api_answer(current_timestamp):
    """Получаем ответ от эндпоинта."""
    try:
        params = {'from_date': current_timestamp}
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != 200:
            raise ResponseStausCodeError(
                f'Код возврата отличен от "200": {response.status_code}. '
                f'Параметры запроса к серверу: эндпоинт {ENDPOINT}, '
                f'хедеры {HEADERS}, параметры {params}'
            )
        return response.json()
    except requests.exceptions.JSONDecodeError as error:
        raise Exception(f'Сбой обработки Json: {error}')
    except requests.exceptions.RequestException as error:
        raise Exception(f'Произошел сбой сети: {error}')


def check_response(response):
    """Проверка ответа от эндпоинта на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Тип ответа от эндпоинта не словарь')
    if 'homeworks' not in response:
        raise KeyError(
            'В ответе от эндпоинта не найдено ключа "homeworks"'
        )
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Тип информации о домашних работах не список')
    return homeworks


def parse_status(homework):
    """Извлечение статуса о конкретной домашней работе."""
    if 'homework_name' not in homework:
        raise KeyError(
            'Нет ожидаемого ключа для имени домашней работы'
        )
    name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неожиданный статус домашней работы: {status}')
    return VERDICT_MESSAGE.format(
        name=name, verdict=HOMEWORK_VERDICTS.get(status)
    )


def check_tokens():
    """Проверка доспутности всех переменных окружения."""
    TOKEN_NAMES = ('TELEGRAM_CHAT_ID', 'TELEGRAM_TOKEN', 'PRACTICUM_TOKEN')
    for name in TOKEN_NAMES:
        if globals()[name] is not None:
            return True
        logger.critical(
            f'Отсутсвует обязательная(-ые) переменная(-ые) окружения:{name}'
        )
        return False


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
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)

        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
