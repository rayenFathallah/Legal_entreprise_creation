from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.chatbot_service import handle_chat_turn

router = APIRouter()

class ChatRequest(BaseModel):
    user_id: str
    message: str

class ChatResponse(BaseModel):
    reply: str

@router.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    if not request.user_id or not request.message:
        raise HTTPException(status_code=400, detail="user_id and message are required")
    reply_text = handle_chat_turn(request.user_id, request.message)
    return ChatResponse(reply=reply_text)
