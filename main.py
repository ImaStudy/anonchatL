from flask import Flask
from threading import Thread
import telebot
from telebot import types
import time
import logging
import requests
import socket
from multiprocessing import Process 
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO)

TOKEN = "7694567532:AAF2ith3388eqkIwrfyCRLmzm7icLZsXDM0"

bot = telebot.TeleBot(TOKEN)

# === здесь убрал ===
app = Flask(__name__)

# === Глобальные переменные ===
user_gender = {}
user_age = {}
waiting_for_gender_change = set()
users_waiting = []
active_chats = {}
shown_welcome = set()

# === Flask-маршрут для UptimeRobot ===
@app.route('/')
def index():
    return "✅ Бот работает и не спит!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# === Функция пинга Telegram, чтобы Render не засыпал ===
def keep_alive_ping():
    while True:
        try:
            logging.info("🌐 Локальный пинг Flask-сервера")
            response = requests.get(
                "http://127.0.0.1:8080",  # Локальный адрес вместо внешнего
                timeout=5,
                headers={
                    "User-Agent": "keep-alive-checker/1.0",
                    "Connection": "close"
                }
            )
            logging.info(f"✅ Ответ сервера: {response.status_code}")
        except Exception as e:
            logging.warning(f"❌ Ошибка пинга: {type(e).__name__}: {e}")
        time.sleep(180)


# === Бот-обработчики ===
@bot.message_handler(func=lambda msg: msg.text and msg.chat.id not in shown_welcome)
def send_welcome(msg):
    shown_welcome.add(msg.chat.id)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🚀 Начать", callback_data="start"))
    bot.send_message(msg.chat.id, "Привет! Нажми кнопку \"Начать\", чтобы запустить анонимный чат.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "start")
def handle_inline_start(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)
    bot.clear_step_handler_by_chat_id(chat_id)
    handle_start(call.message)

@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    if chat_id in user_gender and chat_id in user_age:
        send_search_button(chat_id)
        return

    bot.send_message(chat_id, "Привет! Это анонимный чат-бот 🤖")
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("Парень"), types.KeyboardButton("Девушка"))
    bot.send_message(chat_id, "Выбери свой пол:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ["Парень", "Девушка"])
def handle_gender(message):
    chat_id = message.chat.id
    user_gender[chat_id] = message.text
    bot.send_message(chat_id, f"Пол установлен: {message.text}", reply_markup=types.ReplyKeyboardRemove())
    bot.send_message(chat_id, "Теперь введи свой возраст (от 18 до 99):")
    bot.register_next_step_handler(message, handle_age)

def handle_age(message):
    chat_id = message.chat.id
    try:
        age = int(message.text)
        if 18 <= age <= 99:
            user_age[chat_id] = age
            bot.send_message(chat_id, f"Возраст установлен: {age}", reply_markup=types.ReplyKeyboardRemove())
            send_search_button(chat_id)
        else:
            bot.send_message(chat_id, "Возраст должен быть от 18 до 99. Попробуй снова:")
            bot.register_next_step_handler(message, handle_age)
    except ValueError:
        bot.send_message(chat_id, "Пожалуйста, введи число. Попробуй снова:")
        bot.register_next_step_handler(message, handle_age)

def send_search_button(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if chat_id in active_chats:
        markup.add(types.KeyboardButton("/next"), types.KeyboardButton("/stop"))
        bot.send_message(chat_id, "Вы в чате.\n\n/next — сменить собеседника\n/stop — закончить диалог.", reply_markup=markup)
    elif chat_id in users_waiting:
        markup.add(types.KeyboardButton("⏹ Остановить поиск"))
        bot.send_message(chat_id, "🔎 Ищем собеседника...", reply_markup=markup)
    else:
        markup.add(types.KeyboardButton("🔍 Найти собеседника"))
        bot.send_message(chat_id, "Нажми кнопку \"🔍 Найти собеседника\", чтобы начать поиск.", reply_markup=markup)

@bot.message_handler(commands=['settings'])
def change_settings(message):
    chat_id = message.chat.id
    waiting_for_gender_change.add(chat_id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("Парень"), types.KeyboardButton("Девушка"))
    bot.send_message(chat_id, "Выбери новый пол:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🔍 Найти собеседника")
@bot.message_handler(commands=['search'])
def handle_search(message):
    chat_id = message.chat.id
    if chat_id in active_chats:
        bot.send_message(chat_id, "Вы уже в чате.")
        return
    if chat_id in users_waiting:
        bot.send_message(chat_id, "Вы уже ищете собеседника...")
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("⏹ Остановить поиск"))
    bot.send_message(chat_id, "🔎 Ищем собеседника...", reply_markup=markup)

    for user in users_waiting:
        if user != chat_id:
            active_chats[chat_id] = user
            active_chats[user] = chat_id
            users_waiting.remove(user)
            bot.send_message(chat_id, "✅ Собеседник найден!\n\n/next — найти нового\n/stop — закончить диалог", reply_markup=types.ReplyKeyboardRemove())
            bot.send_message(user, "✅ Собеседник найден!\n\n/next — найти нового\n/stop — закончить диалог", reply_markup=types.ReplyKeyboardRemove())
            return
    users_waiting.append(chat_id)

@bot.message_handler(func=lambda m: m.text == "⏹ Остановить поиск")
def stop_search(message):
    chat_id = message.chat.id
    if chat_id in users_waiting:
        users_waiting.remove(chat_id)
        bot.send_message(chat_id, "Поиск собеседника остановлен.", reply_markup=types.ReplyKeyboardRemove())
        send_search_button(chat_id)
    else:
        bot.send_message(chat_id, "Вы сейчас не ищете собеседника.")
        send_search_button(chat_id)

@bot.message_handler(commands=['stop'])
def stop_chat(message):
    end_chat(message.chat.id, notify=True)

@bot.message_handler(commands=['next'])
def next_chat(message):
    chat_id = message.chat.id
    if chat_id in users_waiting:
        bot.send_message(chat_id, "Вы уже ищете собеседника.")
        return
    end_chat(chat_id, notify=True)
    handle_search(message)

def end_chat(chat_id, notify=False):
    partner = active_chats.pop(chat_id, None)
    if partner:
        active_chats.pop(partner, None)
        if notify:
            bot.send_message(partner, "❌ Собеседник вышел из чата")
            bot.send_message(chat_id, "🚫 Вы покинули чат")
            send_search_button(partner)
            send_search_button(chat_id)
    elif chat_id in users_waiting:
        users_waiting.remove(chat_id)
        if notify:
            bot.send_message(chat_id, "🚫 Вы покинули очередь")
            send_search_button(chat_id)

# === Пересылка фото ===
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    partner_id = active_chats.get(chat_id)
    if partner_id:
        try:
            # Берём фото с максимальным разрешением
            file_id = message.photo[-1].file_id
            bot.send_photo(partner_id, file_id, caption=message.caption or "")
        except:
            bot.send_message(chat_id, "❌ Не удалось доставить фото")
    else:
        bot.send_message(chat_id, "Нет активного собеседника")

# === Пересылка видео ===
@bot.message_handler(content_types=['video'])
def handle_video(message):
    chat_id = message.chat.id
    partner_id = active_chats.get(chat_id)
    if partner_id:
        try:
            bot.send_video(partner_id, message.video.file_id, caption=message.caption or "")
        except:
            bot.send_message(chat_id, "❌ Не удалось доставить видео")
    else:
        bot.send_message(chat_id, "Нет активного собеседника")

# === Пересылка кружков (video note) ===
@bot.message_handler(content_types=['video_note'])
def handle_video_note(message):
    chat_id = message.chat.id
    partner_id = active_chats.get(chat_id)
    if partner_id:
        try:
            bot.send_video_note(partner_id, message.video_note.file_id)
        except:
            bot.send_message(chat_id, "❌ Не удалось доставить кружок")
    else:
        bot.send_message(chat_id, "Нет активного собеседника")

# === Пересылка документов (если нужно) ===
@bot.message_handler(content_types=['document'])
def handle_document(message):
    chat_id = message.chat.id
    partner_id = active_chats.get(chat_id)
    if partner_id:
        try:
            bot.send_document(partner_id, message.document.file_id, caption=message.caption or "")
        except:
            bot.send_message(chat_id, "❌ Не удалось доставить файл")
    else:
        bot.send_message(chat_id, "Нет активного собеседника")

# === Обычные текстовые сообщения ===
@bot.message_handler(func=lambda m: m.content_type == 'text')
def handle_chat(message):
    chat_id = message.chat.id
    partner_id = active_chats.get(chat_id)
    if partner_id:
        try:
            bot.send_message(partner_id, message.text)
        except:
            bot.send_message(chat_id, "❌ Не удалось доставить сообщение")
    elif chat_id not in shown_welcome:
        send_welcome(message)


# === Запуск бота с обработкой ошибок и пингом Telegram ===
def start_bot():
    logging.info("Запуск бота с polling")
    bot.remove_webhook()
    while True:
        try:
            bot.infinity_polling(timeout=90, long_polling_timeout=60)
        except (requests.exceptions.ConnectionError, ConnectionResetError) as e:
            logging.warning(f"🔁 Потеря соединения: {e}. Повтор через 15 секунд...")
            time.sleep(15)
        except Exception as e:
            logging.error(f"❌ Другая ошибка polling: {e}", exc_info=True)
            time.sleep(15)

if __name__ == '__main__':
    Thread(target=run_flask).start()
    Thread(target=keep_alive_ping).start()
    start_bot()
