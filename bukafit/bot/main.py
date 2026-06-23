import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from bukafit.ai.factory import get_provider
from bukafit.bot.handlers import chat, common, onboarding, training
from bukafit.bot.middleware import DBMiddleware
from bukafit.config import settings


def build_dispatcher() -> Dispatcher:
    storage = RedisStorage.from_url(settings.redis_url)
    dp = Dispatcher(storage=storage)

    dp.update.outer_middleware(DBMiddleware())
    dp["provider"] = get_provider()

    # порядок важен: chat — последний (catch-all по тексту)
    dp.include_router(common.router)
    dp.include_router(onboarding.router)
    dp.include_router(training.router)
    dp.include_router(chat.router)
    return dp


async def run_polling() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher()

    from bukafit.reminders.scheduler import start_scheduler
    start_scheduler(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


def main() -> None:
    asyncio.run(run_polling())


if __name__ == "__main__":
    main()
