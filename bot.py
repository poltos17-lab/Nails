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
work_schedule = {}  # НОВОЕ: график работы

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
CREATE TABLE IF NOT EXISTS schedule (
    date TEXT,
    time TEXT
)
""")

conn.commit()


def load_data():
    # записи
    cursor.execute("SELECT user_id, name, phone, procedure, date, time FROM appointments")
    for user_id, name, phone, procedure, date, time in cursor.fetchall():
        user_appointments[user_id] = (date, time, name, phone, procedure)
        appointments.setdefault(date, []).append(time)

    # график
    cursor.execute("SELECT date, time FROM schedule")
    for date, time in cursor.fetchall():
        work_schedule.setdefault(date, []).append(time)


# ====== КНОПКИ ======
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Записаться")],
            [KeyboardButton(text="Заказать звонок")],
            [KeyboardButton(text="Моя запись"), KeyboardButton(text="Отменить запись")]
        ],
        resize_keyboard=True
    )


def back_menu():
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
            [KeyboardButton(text="Назад")],
            [KeyboardButton(text="Главное меню")]
        ],
        resize_keyboard=True
    )


# ====== ДАТЫ ======
def get_dates_keyboard():
    kb = []
    today = datetime.now()

    for i in range(7):
        day = today + timedelta(days=i)
        date_str = day.strftime("%d.%m")

        # показываем только если есть рабочие часы
        if date_str in work_schedule and work_schedule[date_str]:
            kb.append([KeyboardButton(text=date_str)])

    kb.append([KeyboardButton(text="Назад")])
    kb.append([KeyboardButton(text="Главное меню")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# ====== ВРЕМЯ ДЛЯ КЛИЕНТА ======
def get_time_keyboard(date):
    kb = []
    times = []

    for time in sorted(work_schedule.get(date, [])):
        if date in appointments and time in appointments[date]:
            continue
        times.append(KeyboardButton(text=time))

    row = []
    for i, btn in enumerate(times, 1):
        row.append(btn)
        if i % 3 == 0:
            kb.append(row)
            row = []
    if row:
        kb.append(row)

    kb.append([KeyboardButton(text="Назад")])
    kb.append([KeyboardButton(text="Главное меню")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# ====== АДМИН ДАТЫ ======
def get_admin_dates():
    kb = []
    today = datetime.now()

    for i in range(7):
        day = today + timedelta(days=i)
        kb.append([KeyboardButton(text=day.strftime("%d.%m"))])

    kb.append([KeyboardButton(text="Назад")])
    kb.append([KeyboardButton(text="Главное меню")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# ====== АДМИН ВРЕМЯ ======
def get_admin_time_kb(date):
    kb = []
    selected = work_schedule.get(date, [])

    for hour in range(10, 20):
        time_str = f"{hour}:00"

        if time_str in selected:
            text = f"✅ {time_str}"
        else:
            text = f"❌ {time_str}"

        kb.append([KeyboardButton(text=text)])

    kb.append([KeyboardButton(text="Сохранить изменения")])
    kb.append([KeyboardButton(text="Назад")])
    kb.append([KeyboardButton(text="Главное меню")])

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# ====== НАПОМИНАНИЯ ======
async def reminder_loop():
    while True:
        now = datetime.now()

        cursor.execute("SELECT user_id, procedure, date, time, reminded FROM appointments")
        for user_id, procedure, date, time, reminded in cursor.fetchall():

            if reminded:
                continue

            appointment_time = datetime.strptime(date, "%d.%m").replace(
                year=now.year, hour=int(time.split(":")[0])
            )

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

    # ===== ГЛАВНОЕ МЕНЮ =====
    if text == "Главное меню":
        user_data.pop(user_id, None)
        await message.answer("Главное меню", reply_markup=main_menu())
        return

    # ===== START =====
    if text == "/start":
        await message.answer("Привет 💅", reply_markup=main_menu())

    # ===== АДМИН ГРАФИК =====
    elif text == "/week" and user_id in ADMIN_IDS:
        user_data[user_id] = {"admin": True}
        await message.answer("Выбери день", reply_markup=get_admin_dates())

    elif text == "/graph" and user_id in ADMIN_IDS:
        if not work_schedule:
            await message.answer("График пуст")
            return

        txt = "📅 График:\n\n"
        for d, times in work_schedule.items():
            txt += f"{d}: {', '.join(times)}\n"

        await message.answer(txt)

    elif user_id in user_data and user_data[user_id].get("admin"):
        step = user_data[user_id]

        if "date" not in step:
            step["date"] = text
            step["temp_times"] = work_schedule.get(text, []).copy()
            await message.answer("Выбери время", reply_markup=get_admin_time_kb(text))
            return

        if text == "Назад":
            if "date" in step:
                step.pop("date")
                await message.answer("Выбери день", reply_markup=get_admin_dates())
            return

        if text == "Сохранить изменения":
            date = step["date"]

            work_schedule[date] = step["temp_times"]

            cursor.execute("DELETE FROM schedule WHERE date = ?", (date,))
            for t in step["temp_times"]:
                cursor.execute("INSERT INTO schedule VALUES (?, ?)", (date, t))
            conn.commit()

            step.pop("date")
            await message.answer("Сохранено ✅", reply_markup=get_admin_dates())
            return

        # переключение времени
        time = text.replace("✅ ", "").replace("❌ ", "")

        if time in step["temp_times"]:
            step["temp_times"].remove(time)
        else:
            step["temp_times"].append(time)

        await message.answer("Обновлено", reply_markup=get_admin_time_kb(step["date"]))
        return

    # ===== ДАЛЕЕ ЛОГИКА КОДА 1 (без изменений, но с новым графиком) =====

    elif text == "Записаться":
        if user_id in user_appointments:
            await message.answer("У тебя уже есть запись 🙃")
            return

        user_data[user_id] = {}
        await message.answer("Выбери процедуру ✨", reply_markup=procedure_kb())

    elif text == "Назад" and user_id in user_data:
        user_data.pop(user_id)
        await message.answer("Главное меню", reply_markup=main_menu())

    elif user_id in user_data and "procedure" not in user_data[user_id]:
        user_data[user_id]["procedure"] = text
        await message.answer("Как тебя зовут?", reply_markup=back_menu())

    elif user_id in user_data and "name" not in user_data[user_id]:
        user_data[user_id]["name"] = text
        await message.answer("Введи номер телефона 📱", reply_markup=back_menu())

    elif user_id in user_data and "phone" not in user_data[user_id]:
        user_data[user_id]["phone"] = text
        await message.answer("Выбери дату 📅", reply_markup=get_dates_keyboard())

    elif user_id in user_data and "date" not in user_data[user_id]:
        user_data[user_id]["date"] = text
        await message.answer("Выбери время ⏰", reply_markup=get_time_keyboard(text))

    elif user_id in user_data and "time" not in user_data[user_id]:
        date = user_data[user_id]["date"]
        time = text

        if date not in work_schedule or time not in work_schedule[date]:
            await message.answer("❌ Недоступно")
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
            "INSERT INTO appointments VALUES (?, ?, ?, ?, ?, ?, 0)",
            (user_id, name, phone, procedure, date, time)
        )
        conn.commit()

        await message.answer(
            f"Готово 💅\n{name}, ты записана на {procedure}\n📅 {date} {time}",
            reply_markup=main_menu()
        )

        user_data.pop(user_id)

    elif text == "Моя запись":
        if user_id in user_appointments:
            d, t, n, p, pr = user_appointments[user_id]
            await message.answer(f"{pr}\n📅 {d} {t}")
        else:
            await message.answer("Нет записи")

    elif text == "Отменить запись":
        if user_id in user_appointments:
            d, t, *_ = user_appointments[user_id]

            if d in appointments and t in appointments[d]:
                appointments[d].remove(t)

            del user_appointments[user_id]

            cursor.execute("DELETE FROM appointments WHERE user_id = ?", (user_id,))
            conn.commit()

            await message.answer("Запись отменена", reply_markup=main_menu())
        else:
            await message.answer("Нет записи")

    else:
        await message.answer("Выбери действие", reply_markup=main_menu())


# ===== ЗАПУСК =====
async def main():
    load_data()
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
