# 1. Python መጫን
FROM python:3.10-slim

# 2. በሰርቨሩ ላይ የሚሰራበትን ፎልደር መፍጠር
WORKDIR /app

# 3. የላይብረሪ ዝርዝርን (requirements.txt) ኮፒ ማድረግ
COPY requirements.txt .

# 4. አስፈላጊ የሆኑ ላይብረሪዎችን መጫን
RUN pip install --no-cache-dir -r requirements.txt

# 5. ሁሉንም የቦት ፋይሎች ኮፒ ማድረግ
COPY . .

# 6. ቦቱን ማስነሳት
CMD ["python", "bot.py"]
