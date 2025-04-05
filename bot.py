import os
import logging
import tempfile
import ffmpeg
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, InlineQueryHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получение токена из переменных окружения
TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TOKEN:
    logger.error("TELEGRAM_TOKEN not found in environment variables")
    raise ValueError("TELEGRAM_TOKEN not found in environment variables")

logger.info("Token loaded successfully")

# Эффекты для голосовых сообщений
EFFECTS = {
    'robot': 'Робот',
    'echo': 'Эхо',
    'slow': 'Замедление',
    'fast': 'Ускорение',
    'reverse': 'Обратное воспроизведение',
    'autotune': 'Автотюн'
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "Привет! Я бот для обработки голосовых сообщений.\n"
        "Вызовите меня через @имя_бота в любой переписке, "
        "и я помогу обработать голосовое сообщение."
    )

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик инлайн-запросов"""
    logger.info(f"Inline query from user {update.inline_query.from_user.id}")
    try:
        # Получаем информацию о сообщении, на которое отвечаем
        reply_to_message = update.inline_query.reply_to_message
        
        if not reply_to_message:
            logger.info("No reply message found")
            # Если нет ответа на сообщение, показываем инструкцию
            results = [
                InlineQueryResultArticle(
                    id='help',
                    title='Как использовать бота',
                    input_message_content=InputTextMessageContent(
                        "1. Ответьте на голосовое сообщение\n"
                        "2. Вызовите бота через @имя_бота\n"
                        "3. Выберите эффект из списка"
                    )
                )
            ]
            await update.inline_query.answer(results)
            return
        
        # Проверяем, является ли сообщение голосовым
        if not reply_to_message.voice:
            logger.info("Reply message is not a voice message")
            results = [
                InlineQueryResultArticle(
                    id='error',
                    title='Ошибка',
                    input_message_content=InputTextMessageContent(
                        "Пожалуйста, ответьте на голосовое сообщение"
                    )
                )
            ]
            await update.inline_query.answer(results)
            return
        
        logger.info(f"Voice message found, showing effects for message {reply_to_message.message_id}")
        # Создаем результаты с эффектами
        results = []
        for effect_id, effect_name in EFFECTS.items():
            results.append(
                InlineQueryResultArticle(
                    id=effect_id,
                    title=effect_name,
                    input_message_content=InputTextMessageContent(
                        f"Обработка голосового сообщения с эффектом: {effect_name}"
                    ),
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton(
                            "Обработать",
                            callback_data=f"{reply_to_message.message_id}:{effect_id}"
                        )
                    ]])
                )
            )
        await update.inline_query.answer(results)
        
    except Exception as e:
        logger.error(f"Error in inline query: {e}", exc_info=True)
        results = [
            InlineQueryResultArticle(
                id='error',
                title='Ошибка',
                input_message_content=InputTextMessageContent(
                    "Произошла ошибка. Пожалуйста, попробуйте еще раз."
                )
            )
        ]
        await update.inline_query.answer(results)

async def process_voice(voice_file, effect_id):
    """Обработка голосового сообщения с выбранным эффектом"""
    # Создаем временные файлы
    with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as input_file, \
         tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as output_file:
        
        # Скачиваем файл
        await voice_file.download_to_drive(input_file.name)
        
        # Применяем эффект через ffmpeg
        if effect_id == 'robot':
            # Эффект робота
            stream = ffmpeg.input(input_file.name)
            stream = ffmpeg.filter(stream, 'asetrate', 44100*0.8)
            stream = ffmpeg.filter(stream, 'atempo', 1/0.8)
            stream = ffmpeg.filter(stream, 'vibrato', f=20, d=0.5)
        elif effect_id == 'echo':
            # Эффект эха
            stream = ffmpeg.input(input_file.name)
            stream = ffmpeg.filter(stream, 'aecho', 0.8, 0.9, 1000, 0.3)
        elif effect_id == 'slow':
            # Замедление
            stream = ffmpeg.input(input_file.name)
            stream = ffmpeg.filter(stream, 'atempo', 0.5)
        elif effect_id == 'fast':
            # Ускорение
            stream = ffmpeg.input(input_file.name)
            stream = ffmpeg.filter(stream, 'atempo', 2.0)
        elif effect_id == 'reverse':
            # Обратное воспроизведение
            stream = ffmpeg.input(input_file.name)
            stream = ffmpeg.filter(stream, 'areverse')
        elif effect_id == 'autotune':
            # Эффект автотюна
            stream = ffmpeg.input(input_file.name)
            # Изменяем высоту тона
            stream = ffmpeg.filter(stream, 'asetrate', 44100*1.2)
            stream = ffmpeg.filter(stream, 'atempo', 1/1.2)
            # Добавляем легкое вибрато для характерного звучания
            stream = ffmpeg.filter(stream, 'vibrato', f=5, d=0.8)
            # Добавляем легкую реверберацию
            stream = ffmpeg.filter(stream, 'aecho', 0.6, 0.3, 500, 0.2)
        
        # Сохраняем результат
        stream = ffmpeg.output(stream, output_file.name)
        ffmpeg.run(stream, overwrite_output=True)
        
        return output_file.name

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки с эффектами"""
    query = update.callback_query
    await query.answer()
    
    logger.info(f"Callback query from user {query.from_user.id}")
    
    # Разбираем callback_data
    message_id, effect_id = query.data.split(':')
    logger.info(f"Processing voice message {message_id} with effect {effect_id}")
    
    try:
        # Получаем сообщение по ID
        message = await context.bot.get_message(
            chat_id=update.effective_chat.id,
            message_id=int(message_id)
        )
        
        if not message.voice:
            logger.warning(f"Message {message_id} is not a voice message")
            await query.message.reply_text("Это не голосовое сообщение!")
            return
        
        # Отправляем сообщение о начале обработки
        processing_msg = await query.message.reply_text(
            f"Обработка голосового сообщения с эффектом: {EFFECTS[effect_id]}..."
        )
        
        # Получаем файл голосового сообщения
        voice_file = await context.bot.get_file(message.voice.file_id)
        logger.info(f"Downloading voice file {voice_file.file_id}")
        
        # Обрабатываем голосовое сообщение
        processed_file = await process_voice(voice_file, effect_id)
        logger.info(f"Voice file processed and saved to {processed_file}")
        
        # Отправляем обработанное сообщение
        with open(processed_file, 'rb') as audio:
            await context.bot.send_voice(
                chat_id=update.effective_chat.id,
                voice=audio,
                reply_to_message_id=message.message_id,
                caption=f"Обработано с эффектом: {EFFECTS[effect_id]}"
            )
        logger.info(f"Processed voice message sent to chat {update.effective_chat.id}")
        
        # Удаляем временные файлы
        os.unlink(processed_file)
        logger.info("Temporary files cleaned up")
        
        # Удаляем сообщение о обработке
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Error processing voice message: {e}", exc_info=True)
        await query.message.reply_text("Произошла ошибка при обработке голосового сообщения")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Update {update} caused error {context.error}", exc_info=True)
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже."
        )

def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Регистрация обработчика ошибок
    application.add_error_handler(error_handler)
    
    # Запуск бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 