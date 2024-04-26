import sqlite3
from config import DB_NAME, LOGS, DB_TABLE_NAME
import logging

logging.basicConfig(filename=LOGS, level=logging.ERROR,
                    format="%(asctime)s FILE: %(filename)s IN: %(funcName)s MESSAGE: %(message)s", filemode="w")


# Функция для подключения к базе данных или создания новой, если её ещё нет
def create_db(database_name=DB_NAME):
    db_path = f'{database_name}'
    connection = sqlite3.connect(db_path)
    connection.close()


# Функция для выполнения любого sql-запроса для изменения данных
def execute_query(sql_query, data=None, db_path=f'{DB_NAME}'):
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()
    if data:
        cursor.execute(sql_query, data)
    else:
        cursor.execute(sql_query)

    connection.commit()
    connection.close()


# Функция для выполнения любого sql-запроса для получения данных (возвращает значение)
def execute_selection_query(sql_query, data=None, db_path=f'{DB_NAME}'):
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

    if data:
        cursor.execute(sql_query, data)
    else:
        cursor.execute(sql_query)
    rows = cursor.fetchall()
    connection.close()
    return rows


# Функция для создания новой таблицы (если такой ещё нет)
def create_table(table_name):
    sql_query = f'CREATE TABLE IF NOT EXISTS {table_name} ' \
                f'(id INTEGER PRIMARY KEY, ' \
                f'user_id INTEGER, ' \
                f'message TEXT, ' \
                f'role TEXT, ' \
                f'total_gpt_tokens INTEGER, ' \
                f'tts_symbols INTEGER, ' \
                f'stt_blocks INTEGER);'
    execute_query(sql_query)


# Функиця для удаления всех записей из таблицы
def clean_table(table_name):
    execute_query(f"DELETE FROM {table_name}")


# Функция для вставки новой строки в таблицу
def insert_row(values):
    try:
        columns = "(user_id, message, role, total_gpt_tokens, tts_symbols, stt_blocks)"
        sq1_query = f"INSERT INTO {DB_TABLE_NAME} {columns} VALUES (?, ?, ?, ?, ?, ?);"
        execute_query(sq1_query, values)
        logging.info(f"DATABASE: INSERT INTO {DB_TABLE_NAME} VALUES ({values})")
        return True
    except Exception as e:
        logging.error(e)
    return False


def is_value_in_table(table_name, column_name, value):
    try:
        sq1_query = f"SELECT {column_name} FROM {table_name} WHERE {column_name} = ?;"
        raw = execute_selection_query(sq1_query, [value])
        return raw
    except Exception as e:
        logging.error(e)  # если ошибка - записываем её в логи
        return None


def select_n_last_messages(user_id, n_last_messages=4):
    messages = []  # список с сообщениями
    total_spent_tokens = 0  # количество потраченных токенов за всё время общения
    try:
        sq1_query = (f"SELECT message, role, total_gpt_tokens FROM {DB_TABLE_NAME} WHERE user_id=? ORDER BY id DESC "
                     f"LIMIT ?;")
        raw = execute_selection_query(sq1_query, [user_id, n_last_messages])
        if raw and raw[0]:
            # формируем список сообщений
            for message in reversed(raw):
                messages.append({'text': message[0], 'role': message[1]})
                total_spent_tokens = max(total_spent_tokens, message[2])
            return messages, total_spent_tokens
    except Exception as e:
        logging.error(e)  # если ошибка - записываем её в логи
        return messages, total_spent_tokens


def count_all_limits(user_id, limit_type):
    try:
        sq1_query = f"SELECT SUM({limit_type}) FROM {DB_TABLE_NAME} WHERE user_id=?",
        raw = execute_selection_query(sq1_query, user_id)
        if raw and raw[0]:
            logging.info(f"DATABASE: У user_id={user_id} использовано {raw[0]} {limit_type}")
            return raw[0]  # возвращаем это число - сумму всех потраченных <limit_type>
        else:
            return 0  # возвращаем 0
    except Exception as e:
        logging.error(e)  # если ошибка - записываем её в логи
        return 0


# считаем количество уникальных пользователей помимо самого пользователя
def count_users(user_id):
    try:
        sq1_query = f"SELECT COUNT(DISTINCT user_id) FROM {DB_TABLE_NAME} WHERE user_id <> ?;"
        raw = execute_selection_query(sq1_query, [user_id])[0]
        return raw[0]
    except Exception as e:
        logging.error(e)
        return None


# Функция для подготовки базы данных
def prepare_db(clean_if_exists=False):
    create_db()
    create_table(DB_TABLE_NAME)
    if clean_if_exists:
        clean_table(DB_TABLE_NAME)
