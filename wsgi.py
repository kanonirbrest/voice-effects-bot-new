import sys
import os

# Добавляем путь к проекту
path = '/home/ysakovich/mysite'
if path not in sys.path:
    sys.path.append(path)

# Импортируем Flask приложение из bot.py
from bot import app as application 