FROM python:3.9
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
# Railway ላይ ሰርቨሩ እንዳይዘጋ ይህ መስመር ወሳኝ ነው
EXPOSE 8080
CMD ["python", "app.py"]
