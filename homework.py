from json import JSONDecodeError
import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv
import telegram


load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logging.info(f'сообщение отправлено, текст: {message}')
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения, ошибка: {error}')


def get_api_answer(current_timestamp):
    try:
        params = {'from_date': current_timestamp}
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        return response.json()
    except JSONDecodeError:
        logging.error('ошибка доступа к эндпоинту')
    except Exception as error:
        logging.error(
            f'Произошла ошибка при запросе к эндпоинту: {error}'
        )


def check_response(response):
    homeworks = response.get('homeworks')
    if type(homeworks) == list:
        return homeworks
    raise TypeError


def parse_status(homework):
    try:
        homework_name = homework[0].get('lesson_name')
        homework_status = homework[0].get('status')
        if homework_status not in HOMEWORK_STATUSES:
            raise ValueError
        verdict = HOMEWORK_STATUSES.get(homework_status)

        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except IndexError as error:
        logging.error(f'В ответе нет обновлений статуса: {error}')
    except ValueError as error:
        logging.error(f'Неивестный статус домашней работы: {error}')


def check_tokens():
    if (
        TELEGRAM_CHAT_ID is not None and TELEGRAM_TOKEN is not None
    ) and PRACTICUM_TOKEN is not None:
        return True
    else:
        logging.critical(
            'Отсутсвует обязательная(-ые) переменная(-ые) окружения'
        )
        return False


def main():
    """Основная логика работы бота."""

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    while check_tokens() is True:
        try:
            response = get_api_answer(current_timestamp)
            message = parse_status(check_response(response))
            send_message(bot, message)
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
