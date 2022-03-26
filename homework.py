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
    """Отправка сообщения ботом"""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logging.info(f'сообщение отправлено, текст: {message}')
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения, ошибка: {error}')


def get_api_answer(current_timestamp):
    """Получаем ответ от эндпоинта"""
    params = {'from_date': current_timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != 200:
        raise ConnectionError
    return response.json()


def check_response(response):
    """Проверка ответа от эндпоинта на корректность"""
    if type(response) != dict:
        raise TypeError
    homeworks = response.get('homeworks')
    print(response)
    if type(homeworks) != list:
        raise TypeError
    return homeworks


def parse_status(homework):
    """Извлечение статуса о конкретной домашней работе"""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        raise KeyError
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доспутности всех переменных окружения"""
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
            homework = check_response(response)
            message = parse_status(homework[0])
            send_message(bot, message)
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)

        except ConnectionError:
            logging.error('ошибка доступа к эндпоинту')

        except IndexError as error:
            logging.error(f'В ответе нет обновлений статуса: {error}')

        except ValueError as error:
            logging.error(f'Неивестный статус домашней работы: {error}')

        except TypeError as error:
            logging.error(f'Ошибка с типами: {error}')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
