import datetime
from typing import List
from pydantic import BaseModel, Field


class Section(BaseModel):
    title: str
    description: str

class Chapter(BaseModel):
    chapter_title: str
    chapter_description: str
    sections: List[str] = []

class Course(BaseModel):
    course_title: str
    description: str
    topic: str
    chapters: List[Chapter]

class CourseRequest(BaseModel):
    topic: str = Field(..., example="Lập trình C")

class ChatRequest(BaseModel):
    message: str
    sessionId: str = None
    gpa: float = None
    history: list = []  # Lịch sử hội thoại, mặc định là rỗng

class SectionRequest(BaseModel):
    chapter_id: str
    chapter_title: str

# class Session(BaseModel):
#     _id: str
#     userId: str
#     title: str
#     messages: list
#     createdAt: datetime
#     updatedAt: datetime

# class Message(BaseModel):
#     _id: str
#     sessionId: str
#     content: str
#     sender: str
#     createdAt: datetime
#     updatedAt: datetime

