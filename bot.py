"""
Минимальный бот на aiogram 3.x. Его единственная задача — открыть Mini App
кнопкой. Вся логика — в WebApp (см. webapp/index.html).

Установка:
    pip install aiogram

Запуск:
    BOT_TOKEN=1234:abcd WEBAPP_URL=https://yourdomain.com/webapp/ python bot.py

BotFather: чтобы кнопка "Открыть приложение" работала из меню,
нажми у бота /setmenubutton и пропиши тот же WEBAPP_URL.
"""
import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
    MenuButtonWebApp,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBAPP_URL = os.environ["WEBAPP_URL"]   # обязательно HTTPS

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(msg: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🚀 Открыть тренажёр",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )
    ]])
    await msg.answer(
        "Привет! Это тренажёр первой части ЕГЭ по обществознанию.\n"
        "983 задания, 63 темы по кодификатору 2026.\n\n"
        "Нажми кнопку — и поехали 👇",
        reply_markup=kb,
    )


@dp.message(F.text)
async def fallback(msg: Message):
    await msg.answer("Нажми /start, чтобы открыть тренажёр.")


async def main():
    # Делаем Mini App кнопкой меню — чтобы открывалось одним тапом
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Тренажёр",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
