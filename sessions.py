from fastapi import Depends
from app import get_current_user
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
load_dotenv()
MONGO_URL = os.getenv("MONGODB_URI")
client = AsyncIOMotorClient(MONGO_URL)
db = client.get_database("test")
sessions_collection = db.get_collection("sessions")
messages_collection = db.get_collection("messages")
async def get_sessions(user: dict = Depends(get_current_user)):
    #lấy danh sách từ mới nhất đến cũ nhất
    sessions = await sessions_collection.find({"user_id": user["sub"]}).sort("created_at", -1).to_list(None)
    for session in sessions:
        session["_id"] = str(session["_id"])
        session["messages"] = [str(message_id) for message_id in session["messages"]]
    return sessions

async def get_messages(session_id: str, user: dict = Depends(get_current_user)):
    #lấy danh sách từ mới nhất đến cũ nhất
    messages = await messages_collection.find({"session_id": session_id}).sort("created_at", -1).to_list(None)
    for message in messages:
        message["_id"] = str(message["_id"])
    return messages

async def delete_session(session_id: str, user: dict = Depends(get_current_user)):
    await sessions_collection.delete_one({"user_id": user["sub"], "_id": session_id})
    return {"message": "Session deleted successfully"}


