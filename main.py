from fastapi import FastAPI, Request
import logging

# Setup logging
logging.basicConfig(
    filename="requests.log",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

app = FastAPI()

@app.post("/log")
async def log_data(request: Request):
        data = await request.json()
        print("Received data:", data)
        logging.info(f"Received JSON: {data}")
        return {"status": "logged", "received": data}

