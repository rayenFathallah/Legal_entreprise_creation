from fastapi import FastAPI
from app.api.routes_chat import router as chat_router

app = FastAPI(
    title="Chatbot RNE",
    description="API pour un chatbot multi‐étapes utilisant les données scrappées du CNRE",
    version="1.0"
)

app.include_router(chat_router, prefix="/api")

@app.get("/")
def read_root():
    return {"status": "up"}
