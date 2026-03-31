import asyncio
import sqlite3
import os
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

TOKEN = os.getenv("TOKEN")
ADMIN_IDS = [6416994625]

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ===== БД =====
conn = sqlite3.connect("db.db")
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

# ===== FSM =====
class Booking(StatesGroup):
    procedure = State()
    name = State()
    phone = State()
    date = State()
    time = State()

class Callback(StatesGroup):
    name = State()
    phone = State()

class AdminSchedule(StatesGroup):
    date = State()
    time = State()

# ===== КНОПКИ =====
def main_kb():
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

def dates_kb():
    kb = []
    today = datetime.now()
    for i in range(7):
        d = today + timedelta(days=i)
        kb.append([KeyboardButton(text=d.strftime("%d.%m"))])

    kb.append([KeyboardButton(text="Назад"), KeyboardButton(text="Главное меню")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def time_kb(date):
    kb = []
    now = datetime.now()

    cursor.execute("SELECT time FROM work_schedule WHERE date=?", (date,))
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

    for t in times:
        hour = int(t.split(":")[0])
        dt = datetime.strptime(date, "%d.%m").replace(year=now.year, hour=hour)

        if dt < now:
            continue

        available.append(t)

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

def week_kb():
    kb = []
    today = datetime.now()
    for i in range(7):
        d = today + timedelta(days=i)
        kb.append([KeyboardButton(text=d.strftime("%d.%m"))])

    kb.append([KeyboardButton(text="Назад"), KeyboardButton(text="Главное меню")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def hours_kb(selected):
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
    kb.append([KeyboardButton(text="Назад"), KeyboardButton(text="Главное меню")])

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# ===== ОБЩЕЕ =====
@dp.message(F.text == "Главное меню")
async def menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню", reply_markup=main_kb())

# ===== CALLBACK =====
@dp.message(F.text == "Заказать звонок")
async def cb_start(message: Message, state: FSMContext):
    await state.set_state(Callback.name)
    await message.answer("Как тебя зовут?", reply_markup=back_kb())

@dp.message(Callback.name)
async def cb_name(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        return await message.answer("Меню", reply_markup=main_kb())

    await state.update_data(name=message.text)
    await state.set_state(Callback.phone)
    await message.answer("Телефон?", reply_markup=back_kb())

@dp.message(Callback.phone)
async def cb_phone(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.set_state(Callback.name)
        return await message.answer("Имя?", reply_markup=back_kb())

    data = await state.get_data()

    for admin in ADMIN_IDS:
        await bot.send_message(admin, f"📞 {data['name']} {message.text}")

    await state.clear()
    await message.answer("Спасибо!", reply_markup=main_kb())

# ===== ЗАПИСЬ =====
@dp.message(F.text == "Записаться")
async def start_booking(message: Message, state: FSMContext):
    await state.set_state(Booking.procedure)
    await message.answer("Выбери процедуру", reply_markup=procedure_kb())

@dp.message(Booking.procedure)
async def b_proc(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        return await message.answer("Меню", reply_markup=main_kb())

    await state.update_data(procedure=message.text)
    await state.set_state(Booking.name)
    await message.answer("Имя?", reply_markup=back_kb())

@dp.message(Booking.name)
async def b_name(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.set_state(Booking.procedure)
        return await message.answer("Процедура?", reply_markup=procedure_kb())

    await state.update_data(name=message.text)
    await state.set_state(Booking.phone)
    await message.answer("Телефон?", reply_markup=back_kb())

@dp.message(Booking.phone)
async def b_phone(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.set_state(Booking.name)
        return await message.answer("Имя?", reply_markup=back_kb())

    await state.update_data(phone=message.text)
    await state.set_state(Booking.date)
    await message.answer("Дата?", reply_markup=dates_kb())

@dp.message(Booking.date)
async def b_date(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.set_state(Booking.phone)
        return await message.answer("Телефон?", reply_markup=back_kb())

    await state.update_data(date=message.text)
    await state.set_state(Booking.time)
    await message.answer("Время?", reply_markup=time_kb(message.text))

@dp.message(Booking.time)
async def b_time(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.set_state(Booking.date)
        return await message.answer("Дата?", reply_markup=dates_kb())

    data = await state.get_data()

    cursor.execute(
        "INSERT INTO appointments VALUES (?, ?, ?, ?, ?, ?, 0)",
        (message.from_user.id, data["name"], data["phone"], data["procedure"], data["date"], message.text)
    )
    conn.commit()

    for admin in ADMIN_IDS:
        await bot.send_message(admin, f"🆕 {data['name']} {data['phone']} {data['procedure']} {data['date']} {message.text}")

    await state.clear()
    await message.answer("Запись создана ✅", reply_markup=main_kb())

# ===== ADMIN =====
@dp.message(F.text == "/week")
async def week(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    await state.set_state(AdminSchedule.date)
    await message.answer("Выбери день", reply_markup=week_kb())

@dp.message(AdminSchedule.date)
async def admin_date(message: Message, state: FSMContext):
    if message.text == "Назад":
        await state.clear()
        return await message.answer("Меню", reply_markup=main_kb())

    await state.update_data(date=message.text)

    cursor.execute("SELECT time FROM work_schedule WHERE date=?", (message.text,))
    rows = cursor.fetchall()

    await state.update_data(times=[r[0] for r in rows])
    await state.set_state(AdminSchedule.time)

    data = await state.get_data()
    await message.answer("Выбери часы", reply_markup=hours_kb(data["times"]))

@dp.message(AdminSchedule.time)
async def admin_time(message: Message, state: FSMContext):
    data = await state.get_data()

    if message.text == "Назад":
        await state.set_state(AdminSchedule.date)
        return await message.answer("День", reply_markup=week_kb())

    if message.text == "Сохранить изменения":
        cursor.execute("DELETE FROM work_schedule WHERE date=?", (data["date"],))
        for t in data["times"]:
            cursor.execute("INSERT INTO work_schedule VALUES (?, ?)", (data["date"], t))
        conn.commit()

        await state.set_state(AdminSchedule.date)
        return await message.answer("Сохранено", reply_markup=week_kb())

    t = message.text.replace("✅ ", "").replace("❌ ", "")

    if t in data["times"]:
        data["times"].remove(t)
    else:
        data["times"].append(t)

    await state.update_data(times=data["times"])
    await message.answer("Часы", reply_markup=hours_kb(data["times"]))

@dp.message(F.text == "/graph")
async def graph(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    cursor.execute("SELECT date, time FROM work_schedule ORDER BY date, time")
    rows = cursor.fetchall()

    if not rows:
        return await message.answer("График пуст")

    result = {}
    for d, t in rows:
        result.setdefault(d, []).append(t)

    text = "📅 График:\n\n"
    for d in result:
        text += f"{d}: {', '.join(result[d])}\n"

    await message.answer(text)

# ===== RUN =====
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
