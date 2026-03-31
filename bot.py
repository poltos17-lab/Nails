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

        if date not in appointments:
            appointments[date] = []

        appointments[date].append(time)

# ====== КНОПКИ ======
def main_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Записаться")],
            [KeyboardButton(text="Заказать звонок")],
            [KeyboardButton(text="Моя запись"), KeyboardButton(text="Отменить запись")]
        ],
        resize_keyboard=True
    )

def back_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Назад")],
            [KeyboardButton(text="Главное меню")]
        ],
        resize_keyboard=True
    )

def procedure_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Маникюр"), KeyboardButton(text="Брови")],
            [KeyboardButton(text="Назад"), KeyboardButton(text="Главное меню")]
        ],
        resize_keyboard=True
    )

def get_dates_keyboard():
    kb = []
    today = datetime.now()

    for i in range(7):
        day = today + timedelta(days=i)
        kb.append([KeyboardButton(text=day.strftime("%d.%m"))])

    kb.append([KeyboardButton(text="Назад"), KeyboardButton(text="Главное меню")])
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
                [KeyboardButton(text="Назад"), KeyboardButton(text="Главное меню")]
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

    kb.append([KeyboardButton(text="Назад"), KeyboardButton(text="Главное меню")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ====== ADMIN ======
def get_week_kb():
    kb = []
    today = datetime.now()

    for i in range(7):
        day = today + timedelta(days=i)
        kb.append([KeyboardButton(text=day.strftime("%d.%m"))])

    kb.append([KeyboardButton(text="Назад"), KeyboardButton(text="Главное меню")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_hours_kb(selected):
    kb = []
    row = []

    for i in range(10, 20):
        t = f"{i}:00"

        label = f"✅ {t}" if t in selected else f"❌ {t}"
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
    kb.append([KeyboardButton(text="Главное меню")])

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ====== НАПОМИНАНИЯ ======
async def reminder_loop():
    while True:
        now = datetime.now()

        cursor.execute("SELECT user_id, name, procedure, date, time, reminded FROM appointments")
        rows = cursor.fetchall()

        for user_id, name, procedure, date, time, reminded in rows:
            if reminded:
                continue

            appointment_time = datetime.strptime(date, "%d.%m")
            hour = int(time.split(":")[0])
            appointment_time = appointment_time.replace(year=now.year, hour=hour)

            diff = appointment_time - now

            if timedelta(hours=23, minutes=50) < diff < timedelta(hours=24, minutes=10):
                try:
                    await bot.send_message(
                        user_id,
                        f"⏰ Напоминание!\nЗавтра у тебя {procedure} в {time}"
                    )

                    cursor.execute(
                        "UPDATE appointments SET reminded = 1 WHERE user_id = ?",
                        (user_id,)
                    )
                    conn.commit()
                except:
                    pass

        await asyncio.sleep(60)

# ====== ХЕНДЛЕР ======
@dp.message()
async def handler(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    # ===== ОБЩЕЕ =====
    if text == "Главное меню":
        user_data.pop(user_id, None)
        admin_data.pop(user_id, None)
        await message.answer("Главное меню", reply_markup=main_menu_kb())
        return

    # ===== ADMIN /week =====
    if text == "/week" and user_id in ADMIN_IDS:
        admin_data[user_id] = {"step": "choose_date"}
        await message.answer("Выбери день 📅", reply_markup=get_week_kb())
        return

    if user_id in admin_data:
        step = admin_data[user_id].get("step")

        if text == "Назад":
            if step == "choose_time":
                admin_data[user_id]["step"] = "choose_date"
                await message.answer("Выбери день 📅", reply_markup=get_week_kb())
            else:
                admin_data.pop(user_id)
                await message.answer("Главное меню", reply_markup=main_menu_kb())
            return

        if step == "choose_date":
            admin_data[user_id]["date"] = text
            admin_data[user_id]["step"] = "choose_time"

            cursor.execute("SELECT time FROM work_schedule WHERE date = ?", (text,))
            rows = cursor.fetchall()
            admin_data[user_id]["times"] = [r[0] for r in rows]

            await message.answer("Выбери часы", reply_markup=get_hours_kb(admin_data[user_id]["times"]))
            return

        if step == "choose_time":
            if text == "Сохранить изменения":
                date = admin_data[user_id]["date"]
                times = admin_data[user_id]["times"]

                cursor.execute("DELETE FROM work_schedule WHERE date = ?", (date,))
                for t in times:
                    cursor.execute("INSERT INTO work_schedule VALUES (?, ?)", (date, t))
                conn.commit()

                admin_data[user_id]["step"] = "choose_date"

                await message.answer("✅ Сохранено\nВыбери день", reply_markup=get_week_kb())
                return

            t = text.replace("✅ ", "").replace("❌ ", "")

            if t in admin_data[user_id]["times"]:
                admin_data[user_id]["times"].remove(t)
            else:
                admin_data[user_id]["times"].append(t)

            await message.answer("Выбери часы", reply_markup=get_hours_kb(admin_data[user_id]["times"]))
            return

    # ===== ОСТАЛЬНОЕ =====
    if text == "/start":
        await message.answer("Привет 💅", reply_markup=main_menu_kb())

    elif text == "Записаться":
        if user_id in user_appointments:
            await message.answer("У тебя уже есть запись 🙃")
            return

        user_data[user_id] = {"step": "procedure"}
        await message.answer("Выбери процедуру", reply_markup=procedure_kb())

    elif user_id in user_data:
        step = user_data[user_id].get("step")

        if text == "Назад":
            if step == "name":
                user_data[user_id]["step"] = "procedure"
                await message.answer("Выбери процедуру", reply_markup=procedure_kb())
            elif step == "phone":
                user_data[user_id]["step"] = "name"
                await message.answer("Как тебя зовут?", reply_markup=back_kb())
            elif step == "date":
                user_data[user_id]["step"] = "phone"
                await message.answer("Введи телефон", reply_markup=back_kb())
            elif step == "time":
                user_data[user_id]["step"] = "date"
                await message.answer("Выбери дату", reply_markup=get_dates_keyboard())
            return

        if step == "procedure":
            user_data[user_id]["procedure"] = text
            user_data[user_id]["step"] = "name"
            await message.answer("Как тебя зовут?", reply_markup=back_kb())

        elif step == "name":
            user_data[user_id]["name"] = text
            user_data[user_id]["step"] = "phone"
            await message.answer("Телефон?", reply_markup=back_kb())

        elif step == "phone":
            user_data[user_id]["phone"] = text
            user_data[user_id]["step"] = "date"
            await message.answer("Выбери дату", reply_markup=get_dates_keyboard())

        elif step == "date":
            user_data[user_id]["date"] = text
            user_data[user_id]["step"] = "time"
            await message.answer("Выбери время", reply_markup=get_time_keyboard(text))

        elif step == "time":
            date = user_data[user_id]["date"]
            time = text

            name = user_data[user_id]["name"]
            phone = user_data[user_id]["phone"]
            procedure = user_data[user_id]["procedure"]

            cursor.execute(
                "INSERT INTO appointments (user_id, name, phone, procedure, date, time) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, name, phone, procedure, date, time)
            )
            conn.commit()

            user_appointments[user_id] = (date, time, name, phone, procedure)

            for admin in ADMIN_IDS:
                await bot.send_message(admin, f"🆕 {name} {phone} {procedure} {date} {time}")

            await message.answer("Запись создана ✅", reply_markup=main_menu_kb())
            user_data.pop(user_id)

async def main():
    load_data()
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
