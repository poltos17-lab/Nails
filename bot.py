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

# 🔥 ТЕПЕРЬ ВРЕМЯ ТОЛЬКО ИЗ ГРАФИКА
def get_time_keyboard(date):
    kb = []
    now = datetime.now()

    cursor.execute("SELECT time FROM work_schedule WHERE date=?", (date,))
    rows = cursor.fetchall()

    if not rows:
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Нет доступного времени")],
                      [KeyboardButton(text="Назад")]],
            resize_keyboard=True
        )

    times = [r[0] for r in rows]
    buttons = []

    for t in times:
        hour = int(t.split(":")[0])

        selected = datetime.strptime(date, "%d.%m")
        selected = selected.replace(year=now.year, hour=hour)

        if selected < now:
            continue

        if date in appointments and t in appointments[date]:
            continue

        buttons.append(KeyboardButton(text=t))

    row = []
    for i, btn in enumerate(buttons, 1):
        row.append(btn)
        if i % 3 == 0:
            kb.append(row)
            row = []
    if row:
        kb.append(row)

    kb.append([KeyboardButton(text="Назад")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ====== АДМИН ГРАФИК ======
def get_week_keyboard():
    kb = []
    today = datetime.now()

    for i in range(7):
        d = today + timedelta(days=i)
        kb.append([KeyboardButton(text=d.strftime("%d.%m"))])

    kb.append([KeyboardButton(text="Назад")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_hours_keyboard(selected):
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

    kb.append([KeyboardButton(text="Сохранить изменения")])
    kb.append([KeyboardButton(text="Назад")])

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ====== КОМАНДЫ ======
@dp.message(lambda m: m.text == "/start")
async def start_cmd(message: types.Message):
    user_data.pop(message.from_user.id, None)
    await message.answer("Привет 💅", reply_markup=main_kb)

@dp.message(lambda m: m.text == "/week")
async def week_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    user_data[message.from_user.id] = {"admin_week": True}
    await message.answer("Выбери день", reply_markup=get_week_keyboard())

@dp.message(lambda m: m.text == "/graph")
async def graph_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    cursor.execute("SELECT date, time FROM work_schedule ORDER BY date, time")
    rows = cursor.fetchall()

    if not rows:
        await message.answer("График пуст")
        return

    result = {}
    for d, t in rows:
        result.setdefault(d, []).append(t)

    text = "📅 График:\n\n"
    for d in result:
        text += f"{d}: {', '.join(result[d])}\n"

    await message.answer(text)

# ====== ОСНОВНОЙ ХЕНДЛЕР ======
@dp.message()
async def handler(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    # ===== АДМИН ГРАФИК =====
    if user_id in user_data and user_data[user_id].get("admin_week"):

        if text == "Назад":
            del user_data[user_id]
            return await message.answer("Главное меню", reply_markup=main_kb)

        if "date" not in user_data[user_id]:
            user_data[user_id]["date"] = text

            cursor.execute("SELECT time FROM work_schedule WHERE date=?", (text,))
            rows = cursor.fetchall()

            user_data[user_id]["times"] = [r[0] for r in rows]

            return await message.answer("Выбери часы",
                reply_markup=get_hours_keyboard(user_data[user_id]["times"])
            )

        if text == "Сохранить изменения":
            date = user_data[user_id]["date"]

            cursor.execute("DELETE FROM work_schedule WHERE date=?", (date,))
            for t in user_data[user_id]["times"]:
                cursor.execute("INSERT INTO work_schedule VALUES (?, ?)", (date, t))
            conn.commit()

            del user_data[user_id]["date"]
            del user_data[user_id]["times"]

            return await message.answer("Сохранено", reply_markup=get_week_keyboard())

        t = text.replace("✅ ", "").replace("❌ ", "")
        times = user_data[user_id]["times"]

        if t in times:
            times.remove(t)
        else:
            times.append(t)

        return await message.answer("Обновлено", reply_markup=get_hours_keyboard(times))

    # ===== ВСЕ ОСТАЛЬНОЕ (ТВОЕ) =====
    if text == "Заказать звонок":
        user_data[user_id] = {"callback": True}
        return await message.answer("Как тебя зовут?", reply_markup=back_kb)

    elif user_id in user_data and user_data[user_id].get("callback") and "name" not in user_data[user_id]:
        user_data[user_id]["name"] = text
        return await message.answer("Введи номер телефона 📱", reply_markup=back_kb)

    elif user_id in user_data and user_data[user_id].get("callback") and "phone" not in user_data[user_id]:
        name = user_data[user_id]["name"]
        phone = text

        for admin in ADMIN_IDS:
            await bot.send_message(admin, f"📞 Заявка на звонок!\n\nИмя: {name}\nТелефон: {phone}")

        del user_data[user_id]
        return await message.answer("Спасибо! Мы скоро свяжемся 💛", reply_markup=main_kb)

    elif text == "Записаться":

        if user_id in user_appointments:
            return await message.answer("У тебя уже есть запись 🙃")

        user_data[user_id] = {}
        return await message.answer("Выбери процедуру ✨", reply_markup=procedure_kb)

    elif text == "Назад" and user_id in user_data:
        user_data.pop(user_id, None)
        return await message.answer("Главное меню", reply_markup=main_kb)

    else:
        await message.answer("Выбери действие", reply_markup=main_kb)

# ===== ЗАПУСК =====
async def main():
    load_data()
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
