import os
import logging
import tempfile
import ffmpeg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, InlineQueryHandler, CallbackQueryHandler, ContextTypes
from flask import Flask, Response, request
import json
from datetime import datetime
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получение токена
TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not found in environment variables")

# Эффекты для голосовых сообщений
EFFECTS = {
    'robot': 'Робот',
    'echo': 'Эхо',
    'slow': 'Замедление',
    'fast': 'Ускорение',
    'reverse': 'Обратное воспроизведение',
    'autotune': 'Автотюн'
}

# Создаем Flask приложение для healthcheck и логов
app = Flask(__name__)

# Хранилище логов
logs = []

@app.route('/health')
def health_check():
    return Response("OK", status=200)

@app.route('/logs')
def get_logs():
    return Response(json.dumps(logs), mimetype='application/json')

def add_log(message):
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'message': message
    }
    logs.append(log_entry)
    # Держим только последние 100 записей
    if len(logs) > 100:
        logs.pop(0)
    logger.info(message)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    add_log(f"User {update.effective_user.id} started the bot")
    await update.message.reply_text(
        "Привет! Я бот для обработки голосовых сообщений.\n"
        "Ответьте на голосовое сообщение и вызовите меня через @имя_бота"
    )

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик инлайн-запросов"""
    add_log(f"Inline query from user {update.inline_query.from_user.id}")
    try:
        # Проверяем наличие reply_to_message
        if not update.inline_query.reply_to_message:
            add_log("No reply message found")
            await update.inline_query.answer([
                InlineQueryResultArticle(
                    id='help',
                    title='Как использовать бота',
                    input_message_content=InputTextMessageContent(
                        "1. Ответьте на голосовое сообщение\n"
                        "2. Вызовите бота через @имя_бота\n"
                        "3. Выберите эффект из списка"
                    )
                )
            ])
            return

        # Проверяем тип сообщения
        if not update.inline_query.reply_to_message.voice:
            add_log(f"Reply message is not a voice message. Type: {update.inline_query.reply_to_message.content_type}")
            await update.inline_query.answer([
                InlineQueryResultArticle(
                    id='error',
                    title='Ошибка',
                    input_message_content=InputTextMessageContent(
                        "Пожалуйста, ответьте на голосовое сообщение"
                    )
                )
            ])
            return

        # Создаем список эффектов
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
                            callback_data=f"{update.inline_query.reply_to_message.message_id}:{effect_id}"
                        )
                    ]])
                )
            )
        
        await update.inline_query.answer(results)
        add_log(f"Successfully sent {len(results)} effects")

    except Exception as e:
        add_log(f"Error in inline query: {str(e)}")
        await update.inline_query.answer([
            InlineQueryResultArticle(
                id='error',
                title='Ошибка',
                input_message_content=InputTextMessageContent(
                    "Произошла ошибка. Пожалуйста, попробуйте еще раз."
                )
            )
        ])

async def process_voice(voice_file, effect_id):
    """Обработка голосового сообщения"""
    with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as input_file, \
         tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as output_file:
        
        # Скачиваем файл
        await voice_file.download_to_drive(input_file.name)
        
        # Применяем эффект
        if effect_id == 'robot':
            stream = ffmpeg.input(input_file.name)
            stream = ffmpeg.filter(stream, 'asetrate', 44100*0.8)
            stream = ffmpeg.filter(stream, 'atempo', 1/0.8)
            stream = ffmpeg.filter(stream, 'vibrato', f=20, d=0.5)
        elif effect_id == 'echo':
            stream = ffmpeg.input(input_file.name)
            stream = ffmpeg.filter(stream, 'aecho', 0.8, 0.9, 1000, 0.3)
        elif effect_id == 'slow':
            stream = ffmpeg.input(input_file.name)
            stream = ffmpeg.filter(stream, 'atempo', 0.5)
        elif effect_id == 'fast':
            stream = ffmpeg.input(input_file.name)
            stream = ffmpeg.filter(stream, 'atempo', 2.0)
        elif effect_id == 'reverse':
            stream = ffmpeg.input(input_file.name)
            stream = ffmpeg.filter(stream, 'areverse')
        elif effect_id == 'autotune':
            stream = ffmpeg.input(input_file.name)
            stream = ffmpeg.filter(stream, 'asetrate', 44100*1.2)
            stream = ffmpeg.filter(stream, 'atempo', 1/1.2)
            stream = ffmpeg.filter(stream, 'vibrato', f=5, d=0.8)
        
        # Сохраняем результат
        stream = ffmpeg.output(stream, output_file.name)
        ffmpeg.run(stream, overwrite_output=True)
        
        return output_file.name

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback-запросов"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Получаем ID сообщения и эффект
        message_id, effect_id = query.data.split(':')
        message_id = int(message_id)
        
        # Получаем сообщение
        message = await context.bot.get_message(chat_id=query.message.chat_id, message_id=message_id)
        
        if not message.voice:
            await query.message.reply_text("Пожалуйста, ответьте на голосовое сообщение")
            return
        
        # Обрабатываем голосовое сообщение
        await query.message.reply_text(f"Обрабатываю голосовое сообщение с эффектом: {EFFECTS[effect_id]}")
        output_file = await process_voice(message.voice, effect_id)
        
        # Отправляем обработанное сообщение
        with open(output_file, 'rb') as f:
            await query.message.reply_voice(voice=f)
        
        # Удаляем временные файлы
        os.unlink(output_file)
        
    except Exception as e:
        add_log(f"Error in callback: {str(e)}")
        await query.message.reply_text("Произошла ошибка при обработке голосового сообщения")

def main():
    """Основная функция"""
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 