FROM python:3.7.4

WORKDIR /app

COPY requirements.txt .
COPY src . 
RUN pip install -r requirements.txt

COPY . .

# Ensure gunicorn.sh has executable permissions
RUN chmod +x ./gunicorn.sh

ENV PYTHONUNBUFFERED 1

EXPOSE 5000

# CMD ["sh", "-c", "cd src && python3 application.py"]
CMD ["./gunicorn.sh"]