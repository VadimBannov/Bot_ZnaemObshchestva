import telebot
from config import LOGS, DB_TABLE_NAME, COUNT_LAST_MSG
from creds import get_bot_token
import logging
from database import (
    prepare_db,
    insert_row,
    is_value_in_table,
    select_n_last_messages
)
from validators import (
    check_number_of_users,
    is_gpt_token_limit,
    is_tts_symbol_limit,
    is_stt_block_limit
)
from yandex_gpt import ask_gpt
from speechkit import speech_to_text


bot = telebot.TeleBot(get_bot_token())

prepare_db()

logging.basicConfig(filename=LOGS, level=logging.ERROR,
                    format="%(asctime)s FILE: %(filename)s IN: %(funcName)s MESSAGE: %(message)s",
                    filemode="w")


@bot.message_handler(commands=["start"])
def start_command(message):
    user_name, user_id = message.from_user.first_name, message.from_user.id

    if (not is_value_in_table(DB_TABLE_NAME, "user_id", user_id)
            and insert_row([user_id, None, None, 0, 0, 0]) is False):
        bot.send_message(message.chat.id,
                         "Произошла ошибка при записи в базе данных. Попробуйте снова вызвать /start ")
        return

    bot.send_photo(message.chat.id, open('pictures/1.jpg', 'rb'),
                   f'Приветствую вас {user_name}! Отправь мне голосовое сообщение или текст, и я тебе отвечу!')


@bot.message_handler(commands=["help"])
def help_command(message):
    bot.send_message(message.chat.id, "📚Инструкция по использованию бота:\n\n"
                                      "Команды:\n"
                                      "/help: Получить инструкцию\n"
                                      "/about: Узнать о боте\n\n"
                                      "Общение:\n"
                                      "Отправьте голосовое или текстовое сообщение. Бот обработает ваш запрос с "
                                      "помощью API Yandex для распознавания речи для генерации ответа. "
                                      "Полученный ответ будет отправлен вам в виде текстового сообщения.\n\n"
                                      "Ограничения:\n"
                                      "Бот применяет ограничения по количеству использованию токенов. В случае "
                                      "достижения лимита, вы можете получить соответствующее уведомление.")


@bot.message_handler(commands=["about"])
def help_command(message):
    bot.send_message(message.chat.id, "🤖Описание бота:\n\n"
                                      "Бот распознает речь с помощью API Yandex и генерирует ответы с помощью "
                                      "модели YaGPT. Ответы отправляются пользователю в виде аудиофайлов или "
                                      "текстовых сообщений.")


@bot.message_handler(commands=['debug'])
def debug(message):
    with open("logs.txt", "rb") as f:
        bot.send_document(message.chat.id, f)


@bot.message_handler(content_types=['voice'])
def handle_voice(message: telebot.types.Message):
    try:
        user_id = message.from_user.id

        # Проверка на максимальное количество пользователей
        status_check_users, error_message = check_number_of_users(user_id)
        if not status_check_users:
            bot.send_message(user_id, error_message)
            return

        # Проверка на доступность аудиоблоков
        stt_blocks, error_message = is_stt_block_limit(user_id, message.voice.duration)
        if error_message:
            bot.send_message(user_id, error_message)
            return

        # Обработка голосового сообщения
        file_id = message.voice.file_id
        file_info = bot.get_file(file_id)
        file = bot.download_file(file_info.file_path)
        status_stt, stt_text = speech_to_text(file)
        if not status_stt:
            bot.send_message(user_id, stt_text)
            return

        # Запись в БД
        insert_row(
            [
                user_id,
                stt_text,
                'user',
                0,
                0,
                stt_blocks
            ]
        )

        # Проверка на доступность GPT-токенов
        last_messages, total_spent_tokens = select_n_last_messages(user_id, COUNT_LAST_MSG)
        total_gpt_tokens, error_message = is_gpt_token_limit(last_messages, total_spent_tokens)
        if error_message:
            bot.send_message(user_id, error_message)
            return

        # Запрос к GPT и обработка ответа
        status_gpt, answer_gpt, tokens_in_answer = ask_gpt(last_messages)
        if not status_gpt:
            bot.send_message(user_id, answer_gpt)
            return
        total_gpt_tokens += tokens_in_answer

        # Проверка на лимит символов для SpeechKit
        tts_symbols, error_message = is_tts_symbol_limit(user_id, answer_gpt)

        # Запись ответа GPT в БД
        insert_row(
            [
                user_id,
                answer_gpt,
                'assistant',
                total_gpt_tokens,
                tts_symbols,
                0
            ]
        )

        if error_message:
            bot.send_message(user_id, error_message)
            return

        # Преобразование ответа в аудио и отправка
        status_tts, voice_response = speech_to_text(answer_gpt)
        if status_tts:
            bot.send_voice(user_id, voice_response, reply_to_message_id=message.id)
        else:
            bot.send_message(user_id, answer_gpt, reply_to_message_id=message.id)

    except Exception as e:
        logging.error(e)
        bot.send_message(message.chat.id, "Не получилось ответить. Попробуй записать другое сообщение")


# обрабатываем текстовые сообщения
@bot.message_handler(content_types=['text'])
def handle_text(message):
    try:
        user_id = message.from_user.id

        status_check_users, error_message = check_number_of_users(user_id)
        if not status_check_users:
            bot.send_message(user_id, error_message)
            return

        insert_row(
            [
                user_id,
                message.text,
                "user",
                0,
                0,
                0
            ]
        )

        last_messages, total_spent_tokens = select_n_last_messages(user_id, COUNT_LAST_MSG)
        total_gpt_tokens, error_message = is_gpt_token_limit(last_messages, total_spent_tokens)
        if error_message:
            bot.send_message(user_id, error_message)
            return

        status_gpt, answer_gpt, tokens_in_answer = ask_gpt(last_messages)
        if not status_gpt:
            bot.send_message(user_id, answer_gpt)
            return

        insert_row(
            [
                user_id,
                answer_gpt,
                "assistant",
                total_gpt_tokens,
                0,
                0
            ]
        )

        bot.send_message(user_id, answer_gpt, reply_to_message_id=message.id)

    except Exception as e:
        logging.error(e)  # если ошибка - записываем её в логи
        bot.send_message(message.from_user.id, "Не получилось ответить. Попробуй написать другое сообщение")


# обрабатываем все остальные типы сообщений
@bot.message_handler(func=lambda: True)
def handler(message):
    bot.send_message(message.chat.id, "Отправь мне голосовое или текстовое сообщение, и я тебе отвечу")


bot.polling()
