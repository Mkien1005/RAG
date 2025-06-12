import json
import os
from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio
from dotenv import load_dotenv
from ask import ask, get_sessions, get_messages_by_session_id
from check_talk import is_programming_question, is_small_talk
import re
from fastapi.middleware.cors import CORSMiddleware
load_dotenv()
from auth import get_current_user
# Khởi tạo FastAPI
app = FastAPI()

origins = os.getenv("ORIGINS").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,     # Các nguồn được phép truy cập
    allow_credentials=True,    # Cho phép chia sẻ thông tin xác thực (cookie, header)
    allow_methods=["*"],       # Cho phép tất cả các phương thức HTTP (GET, POST, PUT, DELETE...)
    allow_headers=["*"],       # Cho phép tất cả các headers
    expose_headers=["x-session-id"]
)
class QueryInput(BaseModel):
    message: str
    sessionId: str | None = None

@app.get("/api/chat/sessions")
async def getSessions(user: dict = Depends(get_current_user)):
    #lấy danh sách từ mới nhất đến cũ nhất
    return await get_sessions(user)


@app.get("/api/chat/messages/{session_id}")
async def get_messages(session_id: str, user: dict = Depends(get_current_user)):
    return await get_messages_by_session_id(session_id, user)

# Endpoint FastAPI
@app.post("/api/chat/message")
async def query_endpoint(request: QueryInput, user: dict = Depends(get_current_user)):
    # Bước 1: Kiểm tra small talk
    if re.search(r'\b(xin chào|hello|hi|chào|chao|chào bạn|chao ban|chào bạn|chao ban)\b', request.message.lower()):
        # stream response
        return StreamingResponse("Xin chào, tôi là trợ lý lập trình. Tôi có thể giúp gì cho bạn?", media_type="text/plain")
    if not await is_programming_question(request.message):
        return StreamingResponse("Vui lòng hỏi câu hỏi liên quan đến lập trình.", media_type="text/plain")
    
    # Bước 3: Truy xuất từ ChromaDB
    return await ask(request, user)

@app.head("/")
async def health():
    return {"message": "OK"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))  # Mặc định cổng 8000 cho FastAPI
    uvicorn.run(app, host=os.getenv("HOST", "localhost"), port=port)

# Chạy ứng dụng: uvicorn app:app --reload