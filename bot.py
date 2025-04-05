import os
import logging
import tempfile
import ffmpeg
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, InlineQueryHandler, CallbackQueryHandler, ContextTypes
from flask import Flask, Response

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

# Создаем Flask приложение для healthcheck
app = Flask(__name__)

@app.route('/health')
def health_check():
    return Response("OK", status=200)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "Привет! Я бот для обработки голосовых сообщений.\n"
        "Ответьте на голосовое сообщение и вызовите меня через @имя_бота"
    )

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик инлайн-запросов"""
    try:
        # Проверяем, есть ли сообщение, на которое отвечаем
        if not update.inline_query.reply_to_message:
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

        # Проверяем, является ли сообщение голосовым
        if not update.inline_query.reply_to_message.voice:
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

    except Exception as e:
        logger.error(f"Error in inline query: {e}")
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
            stream = ffmpeg.filter(stream, 'aecho', 0.6, 0.3, 500, 0.2)
        
        # Сохраняем результат
        stream = ffmpeg.output(stream, output_file.name)
        ffmpeg.run(stream, overwrite_output=True)
        
        return output_file.name

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Получаем данные из callback
        message_id, effect_id = query.data.split(':')
        
        # Получаем сообщение
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
        
        # Обрабатываем голосовое сообщение
        voice_file = await context.bot.get_file(message.voice.file_id)
        processed_file = await process_voice(voice_file, effect_id)
        
        # Отправляем результат
        with open(processed_file, 'rb') as audio:
            await context.bot.send_voice(
                chat_id=update.effective_chat.id,
                voice=audio,
                reply_to_message_id=message.message_id,
                caption=f"Обработано с эффектом: {EFFECTS[effect_id]}"
            )
        
        # Очищаем временные файлы
        os.unlink(processed_file)
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Error in callback: {e}")
        await query.message.reply_text("Произошла ошибка при обработке голосового сообщения")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Update {update} caused error {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже."
        )

def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_error_handler(error_handler)
    
    # Запускаем Flask в отдельном потоке
    from threading import Thread
    Thread(target=lambda: app.run(host='0.0.0.0', port=int(os.getenv('PORT', 3000)))).start()
    
    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main() 