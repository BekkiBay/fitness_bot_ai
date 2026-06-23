from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.filters import StateFilter
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bukafit.ai.memory import build_memory
from bukafit.ai.provider import ModelProvider
from bukafit.core.models import User

router = Router()


@router.message(StateFilter(None), F.text & ~F.text.startswith("/"))
async def on_text(
    message: Message, session: AsyncSession, user: User, provider: ModelProvider
):
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    memory = await build_memory(session, user.id)
    answer = await provider.answer_question(message.text, memory)
    await message.answer(answer)
