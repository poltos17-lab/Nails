import asyncio
import os
import python-dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TOKEN=os.getenv("token")

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_data = {}

# Хранилища
appointments = {}  # { "25.03": ["10:00"] }
user_appointments = {}  # user_id: (date, time, name)

# Главное меню
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Записаться")],
        [KeyboardButton(text="Моя запись"), KeyboardButton(text="Отменить запись")]
    ],
    resize_keyboard=True
)

# Даты
def get_dates_keyboard():
    kb = []
    today = datetime.now()

    for i in range(7):
        day = today + timedelta(days=i)
        date_str = day.strftime("%d.%m")
        kb.append([KeyboardButton(text=date_str)])

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# Время
def get_time_keyboard(date):
    kb = []
    times = []

    for hour in range(10, 19):
        time_str = f"{hour}:00"

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

    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

@dp.message()
async def handler(message: types.Message):
    user_id = message.from_user.id

    if message.text == "/start":
        await message.answer("Привет 💅", reply_markup=main_kb)

    # ЗАПИСЬ
    elif message.text == "Записаться":
        user_data[user_id] = {}
        await message.answer("Как тебя зовут?")

    elif user_id in user_data and "name" not in user_data[user_id]:
        user_data[user_id]["name"] = message.text
        await message.answer("Выбери дату 📅", reply_markup=get_dates_keyboard())

    elif user_id in user_data and "date" not in user_data[user_id]:
        user_data[user_id]["date"] = message.text
        await message.answer("Выбери время ⏰", reply_markup=get_time_keyboard(message.text))

    elif user_id in user_data and "time" not in user_data[user_id]:
        date = user_data[user_id]["date"]
        time = message.text

        if date in appointments and time in appointments[date]:
            await message.answer("❌ Уже занято")
            return

        name = user_data[user_id]["name"]

        appointments.setdefault(date, []).append(time)
        user_appointments[user_id] = (date, time, name)

        await message.answer(
            f"Готово 💅\n{name}, ты записана на {date} в {time}",
            reply_markup=main_kb
        )

        with open("appointments.txt", "a", encoding="utf-8") as f:
            f.write(f"{name} - {date} {time}\n")

        del user_data[user_id]

    # МОЯ ЗАПИСЬ
    elif message.text == "Моя запись":
        if user_id in user_appointments:
            date, time, name = user_appointments[user_id]
            await message.answer(
                f"📅 Твоя запись:\n{date} в {time}",
                reply_markup=main_kb
            )
        else:
            await message.answer("У тебя нет записи", reply_markup=main_kb)

    # ОТМЕНА
    elif message.text == "Отменить запись":
        if user_id in user_appointments:
            date, time, name = user_appointments[user_id]

            if date in appointments and time in appointments[date]:
                appointments[date].remove(time)

            del user_appointments[user_id]

            await message.answer("❌ Запись отменена", reply_markup=main_kb)
        else:
            await message.answer("У тебя нет записи", reply_markup=main_kb)

    else:
        await message.answer("Выбери действие из меню", reply_markup=main_kb)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
