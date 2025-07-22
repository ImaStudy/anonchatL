from flask import Flask, request
import telebot
from telebot import types
import os

# === Основные настройки ===
TOKEN = "7694567532:AAF2ith3388eqkIwrfyCRLmzm7icLZsXDM0"
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
WEBHOOK_HOST = 'https://anonchatbot-jbh9.onrender.com'
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# === Глобальные переменные ===
user_gender = {}
user_age = {}
waiting_for_gender_change = set()
users_waiting = []
active_chats = {}
shown_welcome = set()

# === Flask маршруты ===
@app.route('/', methods=['GET'])
def index():
    return "✅ Бот запущен и работает!"

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return '', 200

# === Обработчики команд ===
@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    if chat_id in user_gender and chat_id in user_age:
        return send_search_button(chat_id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Парень", "Девушка")
    bot.send_message(chat_id, "Привет! Это анонимный чат 🤖\nВыбери свой пол:", reply_markup=markup)

@bot.message_handler(commands=['search'])
@bot.message_handler(func=lambda m: m.text == "🔍 Найти собеседника")
def handle_search(message):
    chat_id = message.chat.id
    if chat_id in active_chats or chat_id in users_waiting:
        bot.send_message(chat_id, "Вы уже ищете собеседника или находитесь в чате.")
        return
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("⏹ Остановить поиск")
    bot.send_message(chat_id, "🔎 Ищем собеседника...", reply_markup=markup)

    for user in users_waiting:
        if user != chat_id:
            users_waiting.remove(user)
            active_chats[chat_id] = user
            active_chats[user] = chat_id
            msg = "✅ Собеседник найден!\n/next — следующий\n/stop — выйти"
            bot.send_message(chat_id, msg, reply_markup=types.ReplyKeyboardRemove())
            bot.send_message(user, msg, reply_markup=types.ReplyKeyboardRemove())
            return

    users_waiting.append(chat_id)

@bot.message_handler(func=lambda m: m.text in ["Парень", "Девушка"])
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
            bot.send_message(chat_id, f"Возраст установлен: {age}")
            send_search_button(chat_id)
        else:
            raise ValueError
    except:
        bot.send_message(chat_id, "Пожалуйста, введи корректный возраст от 18 до 99:")
        bot.register_next_step_handler(message, handle_age)

@bot.message_handler(func=lambda m: m.text == "⏹ Остановить поиск")
def stop_search(message):
    chat_id = message.chat.id
    if chat_id in users_waiting:
        users_waiting.remove(chat_id)
        bot.send_message(chat_id, "Поиск остановлен.", reply_markup=types.ReplyKeyboardRemove())
    send_search_button(chat_id)

@bot.message_handler(commands=['stop'])
def stop_chat(message):
    end_chat(message.chat.id, notify=True)

@bot.message_handler(commands=['next'])
def next_chat(message):
    end_chat(message.chat.id, notify=True)
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

def send_search_button(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    if chat_id in active_chats:
        markup.add("/next", "/stop")
    elif chat_id in users_waiting:
        markup.add("⏹ Остановить поиск")
    else:
        markup.add("🔍 Найти собеседника")
    bot.send_message(chat_id, "Что вы хотите сделать?", reply_markup=markup)

# === Общий обработчик сообщений ===
@bot.message_handler(func=lambda msg: True)
def forward_messages(msg):
    chat_id = msg.chat.id
    partner = active_chats.get(chat_id)
    if partner:
        try:
            bot.send_message(partner, msg.text)
        except:
            bot.send_message(chat_id, "❌ Не удалось доставить сообщение.")
    else:
        if chat_id not in shown_welcome:
            shown_welcome.add(chat_id)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🚀 Начать", callback_data="start"))
            bot.send_message(chat_id, "Привет! Нажми \"Начать\", чтобы начать анонимный чат", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "start")
def inline_start(call):
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    handle_start(call.message)

# === Запуск ===
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
