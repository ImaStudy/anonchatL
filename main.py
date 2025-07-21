from flask import Flask
from threading import Thread
import telebot
from telebot import types


TOKEN = "7694567532:AAF2ith3388eqkIwrfyCRLmzm7icLZsXDM0"
bot = telebot.TeleBot(TOKEN)
app = Flask('')



user_gender = {}
user_age = {}
waiting_for_gender_change = set()
users_waiting = []
active_chats = {}
shown_welcome = set()

@app.route('/')
def home():
   return "Бот работает!"

import os

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)


def run_bot():
    bot.set_my_commands([
        telebot.types.BotCommand("start", "Начать"),
        telebot.types.BotCommand("search", "Найти собеседника"),
        telebot.types.BotCommand("next", "Следующий собеседник"),
        telebot.types.BotCommand("stop", "Остановить диалог"),
        telebot.types.BotCommand("settings", "Поменять настройки"),
    ])
    bot.polling(none_stop=True)



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
       bot.send_message(chat_id,
                        "Вы в чате.\n\n/next — сменить собеседника\n/stop — закончить диалог.",
                        reply_markup=markup)
   elif chat_id in users_waiting:
       markup.add(types.KeyboardButton("⏹ Остановить поиск"))
       bot.send_message(chat_id, "🔎 Ищем собеседника...", reply_markup=markup)
   else:
       markup.add(types.KeyboardButton("🔍 Найти собеседника"))
       bot.send_message(chat_id,
                        "Нажми кнопку \"🔍 Найти собеседника\", чтобы начать поиск.",
                        reply_markup=markup)

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
           bot.send_message(chat_id,
                            "✅ Собеседник найден!\n\n/next — найти нового\n/stop — закончить диалог",
                            reply_markup=types.ReplyKeyboardRemove())
           bot.send_message(user,
                            "✅ Собеседник найден!\n\n/next — найти нового\n/stop — закончить диалог",
                            reply_markup=types.ReplyKeyboardRemove())
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

@bot.message_handler(func=lambda m: True)
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

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()
bot.polling(none_stop=True)


