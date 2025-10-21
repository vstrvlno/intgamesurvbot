import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiohttp import web
from story import story

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

players = {}  # user_id -> {"current": "intro", "role": "soldier", "inventory": set()}

# --- Хелпер для обрезки текста кнопок ---
def truncate_text(text: str, max_len: int = 50) -> str:
    """Обрезает текст кнопки до безопасной длины."""
    return text if len(text) <= max_len else text[:max_len - 1] + "…"

# --- Хелпер для вывода сцены ---
def get_scene_keyboard(scene_key: str, user_id: int) -> InlineKeyboardMarkup:
    scene = story.get(scene_key)
    buttons = [
        [InlineKeyboardButton(
            text=truncate_text(choice["text"]),
            callback_data=f"{scene_key}:{key}"
        )]
        for key, choice in scene["choices"].items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)



async def send_scene(user_id: int, scene_key: str):
    scene = story.get(scene_key)
    if not scene:
        await bot.send_message(user_id, "⚠️ Ошибка: сцена не найдена.")
        return
    players[user_id]["current"] = scene_key
    text = scene["text"]
    await bot.send_message(user_id, text, reply_markup=get_scene_keyboard(scene_key, user_id))

# --- Команда /start ---
@dp.message(Command("start"))
async def start_game(message: types.Message):
    user_id = message.from_user.id
    players[user_id] = {"current": "intro", "role": None, "inventory": set()}
    await send_scene(user_id, "intro")

# --- Обработка нажатия кнопок ---
@dp.callback_query()
async def on_choice(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    data = callback.data

    # если пользователь не начинал игру (например, после рестарта)
    if user_id not in players:
        players[user_id] = {"current": "intro", "role": None, "inventory": set()}
        await callback.answer("Игра перезапущена, начинаем заново 🔁")
        await send_scene(user_id, "intro")
        return

    if ":" not in data:
        await callback.answer("Неверный формат данных.")
        return

    current, choice_key = data.split(":", 1)
    scene = story.get(current)
    if not scene:
        await callback.answer("Ошибка сцены.")
        return

    choice = scene["choices"].get(choice_key)
    if not choice:
        await callback.answer("Ошибка выбора.")
        return

    # сохраняем роль, если есть
    if "role" in choice:
        players[user_id]["role"] = choice["role"]

    next_scene = choice["next"]
    await callback.message.delete()
    await send_scene(user_id, next_scene)


# --- Render web hook (health check) ---
async def health_check(request):
    return web.Response(text="Bot is running!")

def setup_webserver():
    app = web.Application()
    app.router.add_get("/", health_check)
    return app

async def main():
    app = setup_webserver()
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
