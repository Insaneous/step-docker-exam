FROM python:3.10

RUN apt-get update && apt-get install -y netcat-openbsd

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY ./requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

COPY . /app/

COPY wait-for-postgres.sh /wait-for-postgres.sh

RUN chmod +x /wait-for-postgres.sh

CMD ["/wait-for-postgres.sh", "db", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
