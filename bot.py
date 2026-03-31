import asyncio
import os
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime, timedelta

TOKEN = os.getenv("TOKEN")

ADMIN_IDS = [6416994625, 532148285]

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
        [KeyboardButton(text="Ресницы"), KeyboardButton(text="Брови")],
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
    times = []
    now = datetime.now()

    for hour in range(10, 19):
        if hour == 14:
            continue

        time_str = f"{hour}:00"

        selected = datetime.strptime(date, "%d.%m")
        selected = selected.replace(year=now.year, hour=hour)

        if selected < now:
            continue

        if date in appointments and time_str in appointments[date]:
            continue

        times.append(KeyboardButton(text=time_str))

    row = []
    for i, btn in enumerate(times, 1):
        row.append(btn)
        if i % 3 == 0:
            kb.append(row)
            row = []
    if row:
        kb.append(row)

    kb.append([KeyboardButton(text="Назад")])
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

    if message.text == "/start":
        await message.answer("Привет 💅", reply_markup=main_kb)

    # ===== АДМИН =====
    elif message.text == "/admin" and user_id in ADMIN_IDS:
        cursor.execute("SELECT name, phone, procedure, date, time FROM appointments")
        rows = cursor.fetchall()

        if not rows:
            await message.answer("Нет записей")
            return

        text = "📋 Все записи:\n\n"
        for name, phone, procedure, date, time in rows:
            text += f"{name} ({phone}) — {procedure} — {date} {time}\n"

        await message.answer(text)

    # ===== ЗАКАЗ ЗВОНКА =====
    elif message.text == "Заказать звонок":
        user_data[user_id] = {"callback": True}
        await message.answer("Как тебя зовут?", reply_markup=back_kb)

    elif user_id in user_data and user_data[user_id].get("callback") and "name" not in user_data[user_id]:
        user_data[user_id]["name"] = message.text
        await message.answer("Введи номер телефона 📱", reply_markup=back_kb)

    elif user_id in user_data and user_data[user_id].get("callback") and "phone" not in user_data[user_id]:
        name = user_data[user_id]["name"]
        phone = message.text

        for admin in ADMIN_IDS:
            await bot.send_message(
                admin,
                f"📞 Заявка на звонок!\n\nИмя: {name}\nТелефон: {phone}"
            )

        await message.answer("Спасибо! Мы скоро с тобой свяжемся 💛", reply_markup=main_kb)
        del user_data[user_id]

    # ===== ЗАПИСЬ =====
    elif message.text == "Записаться":

        if user_id in user_appointments:
            await message.answer("У тебя уже есть запись 🙃")
            return

        user_data[user_id] = {}
        await message.answer("Выбери процедуру ✨", reply_markup=procedure_kb)

    # ===== НАЗАД =====
    elif message.text == "Назад" and user_id in user_data:
        step = user_data[user_id]

        if step.get("callback"):
            if "phone" in step:
                del step["phone"]
                await message.answer("Как тебя зовут?", reply_markup=back_kb)
            elif "name" in step:
                del user_data[user_id]
                await message.answer("Главное меню", reply_markup=main_kb)
            return

        if "time" in step:
            del step["time"]
            await message.answer("Выбери дату 📅", reply_markup=get_dates_keyboard())

        elif "date" in step:
            del step["date"]
            await message.answer("Введи номер телефона 📱", reply_markup=back_kb)

        elif "phone" in step:
            del step["phone"]
            await message.answer("Как тебя зовут?", reply_markup=back_kb)

        elif "name" in step:
            del step["name"]
            await message.answer("Выбери процедуру ✨", reply_markup=procedure_kb)

        elif "procedure" in step:
            del user_data[user_id]
            await message.answer("Главное меню", reply_markup=main_kb)

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
        date = user_data[user_id]["date"]
        time = message.text

        now = datetime.now()
        selected = datetime.strptime(date, "%d.%m")
        selected = selected.replace(year=now.year, hour=int(time.split(":")[0]))

        if selected < now:
            await message.answer("❌ Это время прошло")
            return

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

        # 🔔 УВЕДОМЛЕНИЕ АДМИНАМ (НОВАЯ ЗАПИСЬ)
        for admin in ADMIN_IDS:
            await bot.send_message(
                admin,
                f"🆕 Новая запись!\n\nИмя: {name}\nТелефон: {phone}\nПроцедура: {procedure}\nДата: {date}\nВремя: {time}"
            )

        await message.answer(
            f"Готово 💅\n{name}, ты записана на {procedure}\n📅 {date} в {time}",
            reply_markup=main_kb
        )

        del user_data[user_id]

    # ===== МОЯ ЗАПИСЬ =====
    elif message.text == "Моя запись":
        if user_id in user_appointments:
            date, time, name, phone, procedure = user_appointments[user_id]
            await message.answer(
                f"{procedure}\n📅 {date} в {time}\n📱 {phone}",
                reply_markup=main_kb
            )
        else:
            await message.answer("У тебя нет записи", reply_markup=main_kb)

    # ===== ОТМЕНА =====
    elif message.text == "Отменить запись":
        if user_id in user_appointments:
            date, time, name, phone, procedure = user_appointments[user_id]

            if date in appointments and time in appointments[date]:
                appointments[date].remove(time)

            del user_appointments[user_id]

            cursor.execute("DELETE FROM appointments WHERE user_id = ?", (user_id,))
            conn.commit()

            # 🔔 УВЕДОМЛЕНИЕ АДМИНАМ (ОТМЕНА)
            for admin in ADMIN_IDS:
                await bot.send_message(
                    admin,
                    f"❌ Отмена записи!\n\nИмя: {name}\nТелефон: {phone}\nПроцедура: {procedure}\nДата: {date}\nВремя: {time}"
                )

            await message.answer("❌ Запись отменена", reply_markup=main_kb)
        else:
            await message.answer("У тебя нет записи", reply_markup=main_kb)

    else:
        await message.answer("Выбери действие", reply_markup=main_kb)

# ===== ЗАПУСК =====
async def main():
    load_data()
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
