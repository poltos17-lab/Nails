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
work_schedule = {}

# ===== БАЗА =====
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
    cursor.execute("SELECT * FROM appointments")
    for user_id, name, phone, procedure, date, time, _ in cursor.fetchall():
        user_appointments[user_id] = (date, time, name, phone, procedure)
        appointments.setdefault(date, []).append(time)

    cursor.execute("SELECT * FROM schedule")
    for date, time in cursor.fetchall():
        work_schedule.setdefault(date, []).append(time)


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
            [KeyboardButton(text="Ресницы"), KeyboardButton(text="Брови")],
            [KeyboardButton(text="Назад")],
            [KeyboardButton(text="Главное меню")]
        ],
        resize_keyboard=True
    )


# ===== ДАТЫ ДЛЯ КЛИЕНТА =====
def client_dates():
    kb = []
    today = datetime.now()

    for i in range(7):
        d = (today + timedelta(days=i)).strftime("%d.%m")
        if d in work_schedule and work_schedule[d]:
            kb.append([KeyboardButton(text=d)])

    kb.append([KeyboardButton(text="Назад")])
    kb.append([KeyboardButton(text="Главное меню")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# ===== ВРЕМЯ ДЛЯ КЛИЕНТА =====
def client_times(date):
    kb = []
    row = []

    for time in sorted(work_schedule.get(date, [])):
        if date in appointments and time in appointments[date]:
            continue

        row.append(KeyboardButton(text=time))
        if len(row) == 3:
            kb.append(row)
            row = []

    if row:
        kb.append(row)

    kb.append([KeyboardButton(text="Назад")])
    kb.append([KeyboardButton(text="Главное меню")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# ===== АДМИН =====
def admin_dates():
    kb = []
    today = datetime.now()

    for i in range(7):
        kb.append([KeyboardButton(text=(today + timedelta(days=i)).strftime("%d.%m"))])

    kb.append([KeyboardButton(text="Назад")])
    kb.append([KeyboardButton(text="Главное меню")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def admin_times(date, temp):
    kb = []

    for hour in range(10, 20):
        t = f"{hour}:00"
        mark = "✅" if t in temp else "❌"
        kb.append([KeyboardButton(text=f"{mark} {t}")])

    kb.append([KeyboardButton(text="Сохранить изменения")])
    kb.append([KeyboardButton(text="Назад")])
    kb.append([KeyboardButton(text="Главное меню")])

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


# ===== НАПОМИНАНИЯ =====
async def reminder_loop():
    while True:
        now = datetime.now()

        cursor.execute("SELECT user_id, procedure, date, time, reminded FROM appointments")
        for user_id, procedure, date, time, reminded in cursor.fetchall():

            if reminded:
                continue

            dt = datetime.strptime(date, "%d.%m").replace(
                year=now.year, hour=int(time.split(":")[0])
            )

            if timedelta(hours=23, minutes=50) < dt - now < timedelta(hours=24, minutes=10):
                try:
                    await bot.send_message(user_id, f"⏰ Напоминание!\n{procedure} завтра в {time}")
                    cursor.execute("UPDATE appointments SET reminded=1 WHERE user_id=?", (user_id,))
                    conn.commit()
                except:
                    pass

        await asyncio.sleep(60)


# ===== ХЕНДЛЕР =====
@dp.message()
async def handler(message: types.Message):
    user_id = message.from_user.id
    text = message.text

    # ГЛАВНОЕ МЕНЮ
    if text == "Главное меню":
        user_data.pop(user_id, None)
        await message.answer("Главное меню", reply_markup=main_kb())
        return

    # START
    if text == "/start":
        await message.answer("Привет 💅", reply_markup=main_kb())

    # ===== АДМИН =====
    elif text == "/week" and user_id in ADMIN_IDS:
        user_data[user_id] = {"admin": True}
        await message.answer("Выбери день", reply_markup=admin_dates())

    elif text == "/graph" and user_id in ADMIN_IDS:
        if not work_schedule:
            await message.answer("График пуст")
            return

        txt = "📅 График:\n\n"
        for d, t in work_schedule.items():
            txt += f"{d}: {', '.join(sorted(t))}\n"

        await message.answer(txt)

    elif text == "/admin" and user_id in ADMIN_IDS:
        cursor.execute("SELECT name, phone, procedure, date, time FROM appointments")
        rows = cursor.fetchall()

        if not rows:
            await message.answer("Нет записей")
            return

        txt = "📋 Записи:\n\n"
        for n, p, pr, d, t in rows:
            txt += f"{n} ({p}) — {pr} — {d} {t}\n"

        await message.answer(txt)

    # ===== АДМИН ЛОГИКА =====
    elif user_id in user_data and user_data[user_id].get("admin"):
        step = user_data[user_id]

        if text == "Назад":
            if "date" in step:
                step.pop("date")
                await message.answer("Выбери день", reply_markup=admin_dates())
            else:
                user_data.pop(user_id)
                await message.answer("Главное меню", reply_markup=main_kb())
            return

        if "date" not in step:
            step["date"] = text
            step["temp"] = work_schedule.get(text, []).copy()
            await message.answer("Настрой время", reply_markup=admin_times(text, step["temp"]))
            return

        if text == "Сохранить изменения":
            d = step["date"]

            work_schedule[d] = step["temp"]

            cursor.execute("DELETE FROM schedule WHERE date=?", (d,))
            for t in step["temp"]:
                cursor.execute("INSERT INTO schedule VALUES (?,?)", (d, t))
            conn.commit()

            step.pop("date")
            await message.answer("Сохранено ✅", reply_markup=admin_dates())
            return

        # переключение
        t = text.replace("✅ ", "").replace("❌ ", "")
        if t in step["temp"]:
            step["temp"].remove(t)
        else:
            step["temp"].append(t)

        await message.answer("Обновлено", reply_markup=admin_times(step["date"], step["temp"]))
        return

    # ===== ЗАКАЗ ЗВОНКА =====
    elif text == "Заказать звонок":
        user_data[user_id] = {"callback": True}
        await message.answer("Имя?", reply_markup=back_kb())

    elif user_id in user_data and user_data[user_id].get("callback"):
        step = user_data[user_id]

        if "name" not in step:
            step["name"] = text
            await message.answer("Телефон?", reply_markup=back_kb())
        else:
            for admin in ADMIN_IDS:
                await bot.send_message(admin, f"📞 Звонок\n{step['name']} {text}")

            await message.answer("Спасибо!", reply_markup=main_kb())
            user_data.pop(user_id)

    # ===== ЗАПИСЬ =====
    elif text == "Записаться":
        if user_id in user_appointments:
            await message.answer("У тебя уже есть запись")
            return

        user_data[user_id] = {}
        await message.answer("Выбери услугу", reply_markup=procedure_kb())

    elif text == "Назад" and user_id in user_data:
        user_data.pop(user_id)
        await message.answer("Главное меню", reply_markup=main_kb())

    elif user_id in user_data:
        step = user_data[user_id]

        if "procedure" not in step:
            step["procedure"] = text
            await message.answer("Имя?", reply_markup=back_kb())

        elif "name" not in step:
            step["name"] = text
            await message.answer("Телефон?", reply_markup=back_kb())

        elif "phone" not in step:
            step["phone"] = text
            await message.answer("Дата", reply_markup=client_dates())

        elif "date" not in step:
            step["date"] = text
            await message.answer("Время", reply_markup=client_times(text))

        elif "time" not in step:
            d, t = step["date"], text

            if t not in work_schedule.get(d, []):
                await message.answer("Недоступно")
                return

            if d in appointments and t in appointments[d]:
                await message.answer("Занято")
                return

            appointments.setdefault(d, []).append(t)
            user_appointments[user_id] = (d, t, step["name"], step["phone"], step["procedure"])

            cursor.execute("INSERT INTO appointments VALUES (?,?,?,?,?,?,0)",
                           (user_id, step["name"], step["phone"], step["procedure"], d, t))
            conn.commit()

            for admin in ADMIN_IDS:
                await bot.send_message(admin, f"🆕 {step['name']} {d} {t}")

            await message.answer("Записано ✅", reply_markup=main_kb())
            user_data.pop(user_id)

    # ===== МОЯ ЗАПИСЬ =====
    elif text == "Моя запись":
        if user_id in user_appointments:
            d, t, n, p, pr = user_appointments[user_id]
            await message.answer(f"{pr}\n{d} {t}")
        else:
            await message.answer("Нет записи")

    # ===== ОТМЕНА =====
    elif text == "Отменить запись":
        if user_id in user_appointments:
            d, t, n, p, pr = user_appointments[user_id]

            appointments[d].remove(t)
            del user_appointments[user_id]

            cursor.execute("DELETE FROM appointments WHERE user_id=?", (user_id,))
            conn.commit()

            for admin in ADMIN_IDS:
                await bot.send_message(admin, f"❌ Отмена {n} {d} {t}")

            await message.answer("Отменено", reply_markup=main_kb())
        else:
            await message.answer("Нет записи")

    else:
        await message.answer("Выбери действие", reply_markup=main_kb())


# ===== СТАРТ =====
async def main():
    load_data()
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
