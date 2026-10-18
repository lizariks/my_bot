import os
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
from zoneinfo import ZoneInfo

import telebot
from telebot import types


TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Не задано змінну середовища BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)

QUESTIONS_PER_TEST = 10

QUESTION_BANK = [
    ("Яка функція виводить текст на екран у Python 3?",
     "print()", ["echo()", "console.log()", "write()"]),
    ("Який тип даних є незмінним (immutable)?",
     "tuple", ["list", "dict", "set"]),
    ("Як називається спеціальний метод-конструктор класу в Python?",
     "__init__", ["__new_class__", "__start__", "constructor"]),
    ("Що означає параметр self у методі класу?",
     "Посилання на поточний екземпляр класу", ["Назва класу", "Глобальну змінну", "Батьківський клас"]),
    ("Яке ключове слово використовується для успадкування? (class B(...))",
     "Клас-батько вказується в дужках після назви класу", ["extends", "inherits", "implements"]),
    ("Який результат виразу 7 // 2 ?",
     "3", ["3.5", "4", "1"]),
    ("Яка бібліотека призначена для роботи з масивами та чисельними обчисленнями?",
     "NumPy", ["Flask", "Pygame", "BeautifulSoup"]),
    ("Яким ключовим словом оголошується функція?",
     "def", ["func", "function", "lambda_def"]),
    ("Що робить метод append() у списку?",
     "Додає елемент в кінець списку", ["Видаляє останній елемент", "Сортує список", "Копіює список"]),
    ("Як у Python зробити атрибут «приватним» за домовленістю (name mangling)?",
     "Почати ім'я з подвійного підкреслення __", ["Додати ключове слово private", "Написати його з великої літери", "Взяти у лапки"]),
    ("Який блок виконується завжди, незалежно від наявності винятку?",
     "finally", ["else", "except", "catch"]),
    ("Який декоратор перетворює метод на властивість (property)?",
     "@property", ["@attribute", "@staticmethod", "@field"]),
    ("Яка бібліотека використовується для роботи з HTTP-запитами?",
     "requests", ["math", "random", "turtle"]),
    ("Що повертає len([1, 2, 3])?",
     "3", ["2", "4", "Помилку"]),
    ("Як називається можливість різних класів мати метод з однаковою назвою, але різною поведінкою?",
     "Поліморфізм", ["Інкапсуляція", "Абстракція", "Ітерація"]),
    ("Який модуль містить функцію для генерації випадкових чисел?",
     "random", ["rand_lib", "numbers", "chance"]),
]

sessions = {}


def build_test():
    """Вибирає 10 випадкових питань і перемішує варіанти відповідей."""
    chosen = random.sample(QUESTION_BANK, QUESTIONS_PER_TEST)
    test = []
    for text, correct, wrong in chosen:
        options = [correct] + wrong
        random.shuffle(options)
        test.append({
            "text": text,
            "options": options,
            "correct_index": options.index(correct),
        })
    return test


def send_question(chat_id):
    s = sessions[chat_id]
    i = s["index"]
    q = s["test"][i]

    markup = types.InlineKeyboardMarkup(row_width=1)
    letters = ["A", "B", "C", "D"]
    for n, option in enumerate(q["options"]):
        markup.add(types.InlineKeyboardButton(
            f"{letters[n]}) {option}", callback_data=f"ans:{i}:{n}"))

    bot.send_message(
        chat_id,
        f"Питання {i + 1}/{QUESTIONS_PER_TEST}\n\n{q['text']}",
        reply_markup=markup,
    )


def format_duration(seconds):
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes} хв {secs} с"


def send_report(chat_id):
    s = sessions[chat_id]
    duration = time.time() - s["start_time"]
    now = datetime.now(ZoneInfo("Europe/Kyiv")).strftime("%d.%m.%Y %H:%M")

    report = (
        "Тест завершено!\n\n"
        f"Результат: {s['score']} з {QUESTIONS_PER_TEST} балів\n"
        f"Дата: {now}\n"
        f"Тривалість: {format_duration(duration)}\n\n"
        "Щоб пройти тест ще раз, надішліть /start"
    )
    bot.send_message(chat_id, report)
    del sessions[chat_id]


@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    sessions[chat_id] = {
        "test": build_test(),
        "index": 0,
        "score": 0,
        "start_time": time.time(),
    }
    bot.send_message(
        chat_id,
        "Привіт! Це тест з Python (ООП, бібліотеки, конструкції коду).\n"
        f"Тебе чекає {QUESTIONS_PER_TEST} питань, у кожному 4 варіанти відповіді.\nПоїхали!"
    )
    send_question(chat_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("ans:"))
def handle_answer(call):
    chat_id = call.message.chat.id
    s = sessions.get(chat_id)
    if not s:
        bot.answer_callback_query(call.id, "Тест не активний. Надішліть /start")
        return

    _, q_index, opt_index = call.data.split(":")
    q_index, opt_index = int(q_index), int(opt_index)

    if q_index != s["index"]:
        bot.answer_callback_query(call.id, "Ви вже відповіли на це питання")
        return

    q = s["test"][q_index]
    if opt_index == q["correct_index"]:
        s["score"] += 1
        result = "✅ Правильно!"
    else:
        result = f"❌ Неправильно. Правильна відповідь: {q['options'][q['correct_index']]}"

    bot.answer_callback_query(call.id)
    # Прибираємо кнопки та показуємо результат відповіді відразу
    bot.edit_message_text(
        f"Питання {q_index + 1}/{QUESTIONS_PER_TEST}\n\n{q['text']}\n\n"
        f"Ваша відповідь: {q['options'][opt_index]}\n{result}",
        chat_id,
        call.message.message_id,
    )

    s["index"] += 1
    if s["index"] < QUESTIONS_PER_TEST:
        send_question(chat_id)
    else:
        send_report(chat_id)


class HealthHandler(BaseHTTPRequestHandler):
    """Мінімальний веб-сервер: Render вимагає, щоб web-сервіс слухав порт."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("Bot is running".encode("utf-8"))

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass  # не засмічуємо логи


def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()


if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    print("Бот запущено...")
    bot.infinity_polling()