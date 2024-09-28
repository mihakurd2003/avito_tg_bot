import logging

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from avito_api import AvitoAPI
from database import get_session
from models import User, Token
from utils import create_xlsx_report

router = Router()


class Form(StatesGroup):
    waiting_for_token = State()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Добро пожаловать! Пожалуйста, отправьте ваш токен авторизации Avito.")
    await state.set_state(Form.waiting_for_token)


@router.message(Form.waiting_for_token)
async def process_token(message: Message, state: FSMContext):
    token = message.text.strip()
    if not token:
        return await message.answer("Токен не может быть пустым. Пожалуйста, отправьте корректный токен.")
    user_id = message.from_user.id

    async with get_session() as session:
        try:
            result = await session.execute(
                select(User).options(selectinload(User.tokens)).where(user_id == User.id)
            )
            user = result.scalars().first()
            if not user:
                user = User(id=user_id)
                session.add(user)
                await session.commit()
                await session.refresh(user)
            new_token = Token(token=token, user_id=user_id)
            session.add(new_token)
            await session.commit()
            await session.refresh(user, attribute_names=['tokens'])
            await message.answer(f"Токен успешно добавлен! У вас сейчас {len(user.tokens)} токен(ов).")

        except IntegrityError:
            await session.rollback()
            await message.answer("Этот токен уже добавлен ранее. Пожалуйста, отправьте другой токен.")
            return

    await state.clear()
    await send_parse_button(message)


async def send_parse_button(message: Message):
    kb_list = [
        [types.KeyboardButton(text="Показать статистику")],
        [types.KeyboardButton(text="Добавить токен")],
    ]
    keyboard = types.ReplyKeyboardMarkup(keyboard=kb_list, resize_keyboard=True)
    await message.answer("Вы можете нажать кнопку ниже, чтобы получить статистику.", reply_markup=keyboard)


@router.message(lambda message: message.text == "Показать статистику")
async def show_statistics(message: Message):
    user_id = message.from_user.id
    async with get_session() as session:
        result = await session.execute(select(User).where(user_id == User.id))
        user = result.scalars().first()
        if not user or not user.tokens:
            return await message.answer("У вас нет сохраненных токенов. Пожалуйста, отправьте ваш токен авторизации Avito.")

    await message.answer("Начинаю сбор статистики. Пожалуйста, ожидайте...")

    all_data = {}
    try:
        for token in user.tokens:
            avito = AvitoAPI(token)
            account = await avito.get_user_account()
            account_id = account['id']
            account_name = account.get('name', f"Account_{account_id}")
            items = await avito.get_items(account_id)
            stats = []
            for item in items:
                item_id = [item['id']]
                title = item['title']
                response = await avito.get_call_stats(account_id, item_id)
                call_stats = response.get('result', {}).get('items', {})[0]
                stats.append({
                    'title': title,
                    'answered': call_stats.get('answered', 0),
                    'calls': call_stats.get('calls', 0),
                    'new': call_stats.get('new', 0),
                    'newAnswered': call_stats.get('newAnswered', 0)
                })
            if account_name not in all_data:
                all_data[account_name] = []
            all_data[account_name].extend(stats)
            await avito.close()

        xlsx_file = await create_xlsx_report(all_data)
        await message.answer_document(types.BufferedInputFile(xlsx_file, filename="statistic.xlsx"))
        await message.answer("Статистика успешно сформирована и отправлена.")
    except Exception as e:
        logging.exception("Ошибка при сборе статистики:")
        await message.answer(f"Произошла ошибка при сборе статистики: {str(e)}")


@router.message(lambda message: message.text == "Добавить токен")
async def add_token_command(message: Message, state: FSMContext):
    await message.answer("Пожалуйста, отправьте новый токен авторизации Avito.")
    await state.set_state(Form.waiting_for_token)