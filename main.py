from flask import Flask
from threading import Thread
import threading
import telebot
from telebot import types
import time
import logging
import requests

logging.basicConfig(level=logging.INFO)

TOKEN = "7694567532:AAF2ith3388eqkIwrfyCRLmzm7icLZsXDM0"
bot = telebot.TeleBot(TOKEN)

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

def keep_alive_ping():
    while True:
        try:
            logging.info("🌐 Локальный пинг Flask-сервера")
            response = requests.get("http://127.0.0.1:8080", timeout=5)
            logging.info(f"✅ Ответ сервера: {response.status_code}")
        except Exception as e:
            logging.warning(f"❌ Ошибка пинга: {type(e).__name__}: {e}")
        time.sleep(180)

# === Декоратор для запуска хендлера в отдельном потоке ===
def threaded(fn):
    def wrapper(message):
        threading.Thread(target=fn, args=(message,)).start()
    return wrapper

# === Обработчик команды /start ===
@bot.message_handler(commands=['start'])
@threaded
def handle_start(message):
    chat_id = message.chat.id
    if chat_id in user_gender and chat_id in user_age:
        bot.send_message(chat_id, "Вы уже зарегистрированы.")
        send_search_button(chat_id)
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("Парень"), types.KeyboardButton("Девушка"))
    bot.send_message(chat_id, "Привет! Это анонимный чат-бот 🤖\nВыбери свой пол:", reply_markup=markup)

# === Обработчик выбора пола ===
@bot.message_handler(func=lambda message: message.text in ["Парень", "Девушка"])
@threaded
def handle_gender(message):
    chat_id = message.chat.id
    user_gender[chat_id] = message.text
    bot.send_message(chat_id, f"Пол установлен: {message.text}", reply_markup=types.ReplyKeyboardRemove())
    bot.send_message(chat_id, "Теперь введи свой возраст (от 18 до 99):")
    bot.register_next_step_handler(message, handle_age)

# === Обработчик ввода возраста ===
def handle_age(message):
    chat_id = message.chat.id
    try:
        age = int(message.text)
        if 18 <= age <= 99:
            user_age[chat_id] = age
            bot.send_message(chat_id, f"Возраст установлен: {age}", reply_markup=types.ReplyKeyboardRemove())
            send_search_button(chat_id)
        else:
            msg = bot.send_message(chat_id, "Возраст должен быть от 18 до 99. Попробуй снова:")
            bot.register_next_step_handler(msg, handle_age)
    except ValueError:
        msg = bot.send_message(chat_id, "Пожалуйста, введи число. Попробуй снова:")
        bot.register_next_step_handler(msg, handle_age)

# === Функция показа кнопки поиска и статуса ===
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

# === Обработчик кнопки поиска собеседника ===
@bot.message_handler(func=lambda m: m.text == "🔍 Найти собеседника")
@bot.message_handler(commands=['search'])
@threaded
def handle_search(message):
    chat_id = message.chat.id
    if chat_id not in user_gender or chat_id not in user_age:
        bot.send_message(chat_id, "Сначала используй /start, чтобы зарегистрироваться.")
        return
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

# === Остановка поиска ===
@bot.message_handler(func=lambda m: m.text == "⏹ Остановить поиск")
@threaded
def stop_search(message):
    chat_id = message.chat.id
    if chat_id in users_waiting:
        users_waiting.remove(chat_id)
        bot.send_message(chat_id, "Поиск собеседника остановлен.", reply_markup=types.ReplyKeyboardRemove())
        send_search_button(chat_id)
    else:
        bot.send_message(chat_id, "Вы сейчас не ищете собеседника.")
        send_search_button(chat_id)

# === Команда /stop для выхода из чата ===
@bot.message_handler(commands=['stop'])
@threaded
def stop_chat(message):
    end_chat(message.chat.id, notify=True)

# === Команда /next для смены собеседника ===
@bot.message_handler(commands=['next'])
@threaded
def next_chat(message):
    chat_id = message.chat.id
    if chat_id in users_waiting:
        bot.send_message(chat_id, "Вы уже ищете собеседника.")
        return
    end_chat(chat_id, notify=True)
    handle_search(message)

# === Завершение чата и очистка данных ===
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

# === Пересылка медиа (фото, видео, документы) ===
@bot.message_handler(content_types=['photo'])
@threaded
def handle_photo(message):
    partner_id = active_chats.get(message.chat.id)
    if partner_id:
        try:
            file_id = message.photo[-1].file_id
            bot.send_photo(partner_id, file_id, caption=message.caption or "")
        except:
            bot.send_message(message.chat.id, "❌ Не удалось доставить фото")
    else:
        bot.send_message(message.chat.id, "Нет активного собеседника")

@bot.message_handler(content_types=['video'])
@threaded
def handle_video(message):
    partner_id = active_chats.get(message.chat.id)
    if partner_id:
        try:
            bot.send_video(partner_id, message.video.file_id, caption=message.caption or "")
        except:
            bot.send_message(message.chat.id, "❌ Не удалось доставить видео")
    else:
        bot.send_message(message.chat.id, "Нет активного собеседника")

@bot.message_handler(content_types=['video_note'])
@threaded
def handle_video_note(message):
    partner_id = active_chats.get(message.chat.id)
    if partner_id:
        try:
            bot.send_video_note(partner_id, message.video_note.file_id)
        except:
            bot.send_message(message.chat.id, "❌ Не удалось доставить кружок")
    else:
        bot.send_message(message.chat.id, "Нет активного собеседника")

@bot.message_handler(content_types=['document'])
@threaded
def handle_document(message):
    partner_id = active_chats.get(message.chat.id)
    if partner_id:
        try:
            bot.send_document(partner_id, message.document.file_id, caption=message.caption or "")
        except:
            bot.send_message(message.chat.id, "❌ Не удалось доставить файл")
    else:
        bot.send_message(message.chat.id, "Нет активного собеседника")

# === Пересылка текстовых сообщений между собеседниками ===
@bot.message_handler(func=lambda m: m.content_type == 'text')
@threaded
def handle_chat(message):
    chat_id = message.chat.id
    partner_id = active_chats.get(chat_id)
    if partner_id:
        try:
            bot.send_message(partner_id, message.text)
        except:
            bot.send_message(chat_id, "❌ Не удалось доставить сообщение")

# === Запуск ===
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
