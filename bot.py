import asyncio
import os
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime, timedelta

TOKEN = os.getenv("TOKEN")

ADMIN_IDS = [6416994625]

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_data = {}
appointments = {}
user_appointments = {}
admin_data = {}

# ====== БАЗА ======
conn = sqlite3.connect("appointments.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS appointments (
    user_id INTEGER,
    name TEXT,
    phone TEXT,
    procedure TEXT,
    date TEXT,
    time TEXT,
    reminded INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS work_schedule (
    date TEXT,
    time TEXT
)
""")

conn.commit()

def load_data():
    cursor.execute("SELECT user_id, name, phone, procedure, date, time FROM appointments")
    rows = cursor.fetchall()

    for user_id, name, phone, procedure, date, time in rows:
        user_appointments[user_id] = (date, time, name, phone, procedure)

        appointments.setdefault(date, []).append(time)

# ====== КЛАВИАТУРЫ ======
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Записаться")],
        [KeyboardButton(text="Заказать звонок")],
        [KeyboardButton(text="Моя запись"), KeyboardButton(text="Отменить запись")]
    ],
    resize_keyboard=True
)

back_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Назад")]],
    resize_keyboard=True
)

procedure_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Маникюр"), KeyboardButton(text="Брови")],
        [KeyboardButton(text="Назад")]
    ],
    resize_keyboard=True
)

def get_dates_keyboard():
    kb = []
    today = datetime.now()

    for i in range(7):
        day = today + timedelta(days=i)
        kb.append([KeyboardButton(text=day.strftime("%d.%m"))])

    kb.append([KeyboardButton(text="Назад")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_time_keyboard(date):
    kb = []
    now = datetime.now()

    cursor.execute("SELECT time FROM work_schedule WHERE date = ?", (date,))
    rows = cursor.fetchall()

    if not rows:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Нет доступного времени")],
                [KeyboardButton(text="Назад")]
            ],
            resize_keyboard=True
        )

    times = [r[0] for r in rows]
    available = []

    for time_str in times:
        hour = int(time_str.split(":")[0])

        selected = datetime.strptime(date, "%d.%m")
        selected = selected.replace(year=now.year, hour=hour)

        if selected < now:
            continue

        if date in appointments and time_str in appointments[date]:
            continue

        available.append(time_str)

    row = []
    for i, t in enumerate(available, 1):
        row.append(KeyboardButton(text=t))
        if i % 3 == 0:
            kb.append(row)
            row = []
    if row:
        kb.append(row)

    kb.append([KeyboardButton(text="Назад")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ====== ADMIN ======
def get_week_kb():
    kb = []
    today = datetime.now()

    for i in range(7):
        day = today + timedelta(days=i)
        kb.append([KeyboardButton(text=day.strftime("%d.%m"))])

    kb.append([KeyboardButton(text="Назад")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_hours_kb(selected):
    kb = []
    row = []

    for i in range(10, 20):
        t = f"{i}:00"

        if t in selected:
            label = f"✅ {t}"
        else:
            label = f"❌ {t}"

        row.append(KeyboardButton(text=label))

        if len(row) == 3:
            kb.append(row)
            row = []

    if row:
        kb.append(row)

    kb.append([
        KeyboardButton(text="Сохранить изменения"),
        KeyboardButton(text="Назад")
    ])

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ====== ХЕНДЛЕР ======
@dp.message()
async def handler(message: types.Message):
    user_id = message.from_user.id

    # ===== WEEK =====
    if message.text == "/week" and user_id in ADMIN_IDS:
        admin_data[user_id] = {}
        await message.answer("Выбери день 📅", reply_markup=get_week_kb())

    elif user_id in admin_data and "date" not in admin_data[user_id]:
        if message.text == "Назад":
            del admin_data[user_id]
            await message.answer("Главное меню", reply_markup=main_kb)
            return

        admin_data[user_id]["date"] = message.text
        admin_data[user_id]["times"] = []

        await message.answer(
            f"Выбери часы для {message.text}",
            reply_markup=get_hours_kb([])
        )

    elif user_id in admin_data:
        if message.text == "Назад":
            del admin_data[user_id]
            await message.answer("Выбери день 📅", reply_markup=get_week_kb())
            return

        if message.text == "Сохранить изменения":
            date = admin_data[user_id]["date"]
            times = admin_data[user_id]["times"]

            cursor.execute("DELETE FROM work_schedule WHERE date = ?", (date,))
            for t in times:
                cursor.execute("INSERT INTO work_schedule (date, time) VALUES (?, ?)", (date, t))
            conn.commit()

            del admin_data[user_id]

            # 👇 ВОЗВРАТ К ВЫБОРУ ДАТЫ
            await message.answer("✅ Сохранено\nВыбери следующий день", reply_markup=get_week_kb())
            return

        t = message.text.replace("✅ ", "").replace("❌ ", "")

        if t not in admin_data[user_id]["times"]:
            admin_data[user_id]["times"].append(t)
        else:
            admin_data[user_id]["times"].remove(t)

        await message.answer(
            "Выбирай часы",
            reply_markup=get_hours_kb(admin_data[user_id]["times"])
        )

    # ===== START =====
    elif message.text == "/start":
        await message.answer("Привет 💅", reply_markup=main_kb)

    # ===== ЗАПИСЬ =====
    elif message.text == "Записаться":
        if user_id in user_appointments:
            await message.answer("У тебя уже есть запись 🙃")
            return

        user_data[user_id] = {}
        await message.answer("Выбери процедуру ✨", reply_markup=procedure_kb)

    elif user_id in user_data and "procedure" not in user_data[user_id]:
        user_data[user_id]["procedure"] = message.text
        await message.answer("Как тебя зовут?", reply_markup=back_kb)

    elif user_id in user_data and "name" not in user_data[user_id]:
        user_data[user_id]["name"] = message.text
        await message.answer("Введи номер телефона 📱", reply_markup=back_kb)

    elif user_id in user_data and "phone" not in user_data[user_id]:
        user_data[user_id]["phone"] = message.text
        await message.answer("Выбери дату 📅", reply_markup=get_dates_keyboard())

    elif user_id in user_data and "date" not in user_data[user_id]:
        user_data[user_id]["date"] = message.text
        await message.answer("Выбери время ⏰", reply_markup=get_time_keyboard(message.text))

    elif user_id in user_data and "time" not in user_data[user_id]:
        if message.text == "Нет доступного времени":
            await message.answer("Выбери другую дату", reply_markup=get_dates_keyboard())
            return

        date = user_data[user_id]["date"]
        time = message.text

        if date in appointments and time in appointments[date]:
            await message.answer("❌ Уже занято")
            return

        name = user_data[user_id]["name"]
        phone = user_data[user_id]["phone"]
        procedure = user_data[user_id]["procedure"]

        appointments.setdefault(date, []).append(time)
        user_appointments[user_id] = (date, time, name, phone, procedure)

        cursor.execute(
            "INSERT INTO appointments (user_id, name, phone, procedure, date, time) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, name, phone, procedure, date, time)
        )
        conn.commit()

        await message.answer(
            f"Готово 💅\n{name}, ты записана на {procedure}\n📅 {date} в {time}",
            reply_markup=main_kb
        )

        del user_data[user_id]

# ===== ЗАПУСК =====
async def main():
    load_data()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
