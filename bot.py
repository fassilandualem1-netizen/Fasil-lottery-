import logging
import asyncio
from aiogram import Bot, Dispatcher, types

# --- ውቅረት (Configuration) ---
# ቶከንህ እዚህ ገብቷል
API_TOKEN = '8663228906:AAFsTC0fKqAVEWMi7rk59iSdfVD-1vlJA0Y' 

# የሦስታችሁም ID እዚህ ዝርዝር ውስጥ ገብቷል
ADMIN_IDS = [8488592165, 5690096145, 7072611117]

# የቻናላችሁ ID
DRIVER_CHANNEL_ID = -1003962139457

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- የአድሚን/ሾፌር ሜኑ ---
def get_driver_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("አዳዲስ ትዕዛዞች 📦"))
    keyboard.add(types.KeyboardButton("እቃ ጨምር (Vendor) ➕"), types.KeyboardButton("ሪፖርት 📊"))
    return keyboard

# --- የገዢው ሜኑ ---
def get_customer_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("ሱቆችን ተመልከት 🏪"))
    return keyboard

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    # እዚህ ጋር 'in ADMIN_IDS' የሚለው ሦስታችሁንም ቼክ ያደርጋል
    if user_id in ADMIN_IDS:
        await message.answer(
            f"ሰላም ሾፌር {message.from_user.first_name}! የቢዝነሱ ባለቤት መሆንህ ተረጋግጧል። ስራ እንጀምር?",
            reply_markup=get_driver_keyboard()
        )
    else:
        await message.answer(
            "እንኳን ወደ Beu-Style Delivery በደህና መጡ! በቅርብ ቀን ሙሉ አገልግሎት እንጀምራለን።",
            reply_markup=get_customer_keyboard()
        )

@dp.message_handler(lambda message: message.text == "አዳዲስ ትዕዛዞች 📦")
async def check_orders(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        try:
            await bot.send_message(DRIVER_CHANNEL_ID, f"🔔 ማሳወቂያ፡ ሾፌር {message.from_user.first_name} ትዕዛዝ ለመቀበል ዝግጁ ነው።")
            await message.answer("ወደ ሾፌሮች ቻናል ማሳወቂያ ተልኳል! ✅")
        except Exception as e:
            await message.answer(f"ስህተት ተፈጥሯል፦ {e}\n(ቦቱ ቻናሉ ላይ Admin መሆኑን አረጋግጥ!)")

async def main():
    print("🚀 ቦቱ በ Termux ላይ ስራ ጀምሯል...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("ቦቱ ቆሟል!")

እሄንን በ phyton ከዛ github ላይ commit አድርጌ pc ላይ ደሞ በ ረንደር እጭነዋለሁ ምን ትላለህ