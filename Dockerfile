# የ Python መሠረት
FROM python:3.11-slim

# የሥራ ማውጫ መፍጠር
WORKDIR /app

# አስፈላጊ ፋይሎችን መቅዳት
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ሙሉውን ኮድ መቅዳት
COPY . .

# ቦቱን ማስጀመር
CMD ["python", "bot.py"]
