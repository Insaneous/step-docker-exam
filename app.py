import logging
from fastapi import FastAPI, Depends
import requests
import asyncpg
import aioredis
import os
from contextlib import asynccontextmanager
import json

LOG_FILE = "/app/logs/app.log"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

API_KEY = "nope"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/currency_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
CACHE_TTL = 1800 

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Connecting to database and redis...")
    app.state.db = await asyncpg.connect(DATABASE_URL)
    app.state.redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
    
    await app.state.db.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rates (
            id SERIAL PRIMARY KEY,
            currency VARCHAR(10),
            rate1 FLOAT,
            rate2 FLOAT,
            diff FLOAT,
            timestamp TIMESTAMP DEFAULT NOW()
        )
    """)
    
    logging.info("All your base are belong to us!(Database and redis are ready)")
    yield

    logging.info("Closing database and redis connections...")
    await app.state.db.close()
    await app.state.redis.close()
    logging.info("Connections closed.")

app = FastAPI(lifespan=lifespan)

async def get_db():
    return app.state.db

async def get_redis():
    return app.state.redis

@app.get("/first")
async def first(redis=Depends(get_redis)):
    cached_data = await redis.get("first_rates")
    if cached_data:
        logging.info("Using cached data for /first")
        return json.loads(cached_data)

    api = requests.get(f"https://v6.exchangerate-api.com/v6/{API_KEY}/latest/USD")
    data = api.json()
    
    logging.info("Fetched data from first API")
    await redis.set("first_rates", json.dumps(data), ex=CACHE_TTL)
    return data

@app.get("/second")
async def second(redis=Depends(get_redis)):
    cached_data = await redis.get("second_rates")
    if cached_data:
        logging.info("Using cached data for /second")
        return json.loads(cached_data)

    api = requests.get("https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json")
    data = api.json()
    
    logging.info("Fetched data from second API")
    await redis.set("second_rates", json.dumps(data), ex=CACHE_TTL)
    return data

@app.get("/diff")
async def diff(db=Depends(get_db), redis=Depends(get_redis)):
    logging.info("Calculating currency differences...")
    
    data1, data2 = await first(redis), await second(redis)
    diff = {}

    for currency, value1 in data1.get("conversion_rates").items():
        value2 = data2.get("usd").get(currency.lower())
        if value2:
            difference = abs(value1 - value2)
            diff[currency] = difference
            
            await db.execute(
                "INSERT INTO exchange_rates (currency, rate1, rate2, diff) VALUES ($1, $2, $3, $4)",
                currency, value1, value2, difference
            )
            logging.info(f"Saved diff for {currency}: {difference}")

    return diff

@app.get("/history")
async def history(db=Depends(get_db)):
    rows = await db.fetch("SELECT * FROM exchange_rates ORDER BY timestamp DESC LIMIT 10")
    logging.info("Fetched last 10 currency exchange rates")
    return rows