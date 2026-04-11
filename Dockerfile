FROM python:3.9-slim
RUN pip install pyTelegramBotAPI
COPY . /app
WORKDIR /app
CMD ["python", "bot.py"]
