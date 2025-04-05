import os
import logging
import tempfile
import ffmpeg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, InlineQueryHandler
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')

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
    query = update.inline_query.query
    
    # Если запрос пустой, показываем инструкцию
    if not query:
        results = [
            InlineQueryResultArticle(
                id='help',
                title='Как использовать бота',
                input_message_content=InputTextMessageContent(
                    "1. Ответьте на голосовое сообщение, вызвав меня через @имя_бота\n"
                    "2. Выберите эффект из списка"
                )
            )
        ]
        await update.inline_query.answer(results)
        return
    
    # Проверяем, является ли запрос реплаем на сообщение
    if query.startswith('reply_'):
        message_id = query.replace('reply_', '')
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
                            callback_data=f"{message_id}:{effect_id}"
                        )
                    ]])
                )
            )
        await update.inline_query.answer(results)
    else:
        # Если запрос не является реплаем
        await update.inline_query.answer([])

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
    
    # Разбираем callback_data
    message_id, effect_id = query.data.split(':')
    
    # Получаем сообщение по ID
    try:
        message = await context.bot.get_message(
            chat_id=update.effective_chat.id,
            message_id=int(message_id)
        )
        
        if not message.voice:
            await query.message.reply_text("Это не голосовое сообщение!")
            return
        
        # Отправляем сообщение о начале обработки
        processing_msg = await query.message.reply_text(
            f"Обработка голосового сообщения с эффектом: {EFFECTS[effect_id]}..."
        )
        
        # Получаем файл голосового сообщения
        voice_file = await context.bot.get_file(message.voice.file_id)
        
        # Обрабатываем голосовое сообщение
        processed_file = await process_voice(voice_file, effect_id)
        
        # Отправляем обработанное сообщение
        with open(processed_file, 'rb') as audio:
            await context.bot.send_voice(
                chat_id=update.effective_chat.id,
                voice=audio,
                reply_to_message_id=message.message_id,
                caption=f"Обработано с эффектом: {EFFECTS[effect_id]}"
            )
        
        # Удаляем временные файлы
        os.unlink(processed_file)
        
        # Удаляем сообщение о обработке
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Error processing voice message: {e}")
        await query.message.reply_text("Произошла ошибка при обработке голосового сообщения")

def main():
    """Запуск бота"""
    application = Application.builder().token(TOKEN).build()

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_handler(CallbackQueryHandler(handle_callback))

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main() 