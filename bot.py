import asyncio
import os
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("EXCHANGE_API_KEY")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

user_data = {}  # Foydalanuvchi holati
user_history = {}  # Avval ishlatilgan valyutalar

# 🔁 Valyuta tanlash uchun inline tugmalar
def currency_keyboard(user_id: int):
    builder = InlineKeyboardBuilder()
    history = user_history.get(user_id, [])
    for cur in history[-6:][::-1]:  # Oxirgi 6 ta valyuta
        builder.button(text=cur, callback_data=f"from_{cur}")
    builder.adjust(3)
    return builder.as_markup()

# /start komandasi
@dp.message(F.text == "/start")
async def start(message: Message):
    await message.answer(
        "💱 Valyuta konvertori botiga xush kelibsiz!\n"
        "🔻 Avvalgi ishlatilgan valyutalardan birini tanlang yoki yangi valyutani yozing (masalan: <code>usd</code>)",
        reply_markup=currency_keyboard(message.from_user.id)
    )

# Inline tugma orqali birinchi valyutani tanlash
@dp.callback_query(F.data.startswith("from_"))
async def select_from_currency(callback: types.CallbackQuery):
    from_currency = callback.data.split("_")[1].upper()
    user_data[callback.from_user.id] = {"from": from_currency}
    await callback.message.answer(f"✍️ Qaysi valyutaga o‘tkazmoqchisiz? (Masalan: <code>uzs</code>)")
    await callback.answer()

# Valyutani matn orqali kiritish
@dp.message(F.text.regexp(r"^[a-zA-Z]{3}$"))
async def handle_currency_input(message: Message):
    user_id = message.from_user.id
    currency = message.text.strip().upper()

    if user_id not in user_data or "from" not in user_data[user_id]:
        # birinchi valyutani belgilash
        user_data[user_id] = {"from": currency}
        await message.answer(f"🔁 Qaysi valyutaga o‘tkazmoqchisiz? (Masalan: <code>eur</code>)")
    else:
        # ikkinchi valyutani belgilash
        user_data[user_id]["to"] = currency
        await message.answer("✍️ Miqdorni kiriting (masalan: <code>100</code>):")

def currency_keyboard(user_id: int):
    builder = InlineKeyboardBuilder()
    history = user_history.get(user_id, [])
    for cur in history[-6:][::-1]:
        builder.button(text=f"{cur}", callback_data=f"from_{cur}")
        builder.button(text="❌", callback_data=f"del_{cur}")
    builder.adjust(2)  # har bir qatorda 2 ta: valyuta + delete
    return builder.as_markup()


@dp.callback_query(F.data.startswith("del_"))
async def delete_currency(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cur = callback.data.split("_")[1].upper()

    if user_id in user_history and cur in user_history[user_id]:
        user_history[user_id].remove(cur)

    await callback.message.edit_text(
        "🧹 Valyuta o‘chirildi. Qolganlar:",
        reply_markup=currency_keyboard(user_id)
    )
    await callback.answer(f"{cur} o‘chirildi")

# Miqdor kiritiladi va natija chiqadi
@dp.message(F.text.regexp(r"^\d+([.,]\d+)?$"))
async def convert_currency(message: Message):
    user_id = message.from_user.id
    if user_id not in user_data or "from" not in user_data[user_id] or "to" not in user_data[user_id]:
        await message.answer("❗ Iltimos, avval valyutalarni tanlang: /start")
        return

    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("❌ Noto‘g‘ri format. Faqat son kiriting.")
        return

    from_currency = user_data[user_id]["from"]
    to_currency = user_data[user_id]["to"]

    result = await get_exchange_rate(from_currency, to_currency, amount)
    if result:
        await message.answer(
            f"💸 <b>{amount} {from_currency} = {result:.2f} {to_currency}</b>")
    else:
        await message.answer("⚠️ Valyuta kursini olishda xatolik yuz berdi.")

    # Avval ishlatilgan valyutalarni saqlash
    history = user_history.get(user_id, [])
    for cur in [from_currency, to_currency]:
        if cur not in history:
            history.append(cur)
    user_history[user_id] = history[-10:]  # faqat oxirgi 10 ta

    user_data.pop(user_id, None)

    # Bosh menyuga qaytish
    await start(message)

# API orqali konvertatsiya
async def get_exchange_rate(from_currency: str, to_currency: str, amount: float) -> float | None:
    url = f"https://api.exchangeratesapi.io/v1/latest?access_key={API_KEY}&format=1"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                rates = data.get("rates", {})
                if from_currency not in rates or to_currency not in rates:
                    return None
                base_to_from = rates[from_currency]
                base_to_to = rates[to_currency]
                return amount / base_to_from * base_to_to
            return None

# Botni ishga tushirish
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
