import re
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
from dotenv import load_dotenv
load_dotenv()
# Hàm kiểm tra small talk
# def is_small_talk(question: str) -> bool:
#     small_talk_patterns = [
#         r"^(hi|hello|hey|chào|chào buổi sáng).*",
#         r".*(how are you|how's it going|bạn khỏe không).*",
#         r".*(thank you|cảm ơn|nice to meet you).*",
#     ]
#     for pattern in small_talk_patterns:
#         if re.match(pattern, question.lower()):
#             return True
#     return False

llm = ChatOpenAI(model="gpt-4o-mini")
async def is_small_talk(question: str) -> bool:
    prompt = f"""
    Bạn là một trợ lý phân loại câu hỏi. Hãy xác định xem câu hỏi sau có phải là small talk (trò chuyện thông thường, như chào hỏi, hỏi thăm, cảm ơn) hay không.
    Câu hỏi: "{question}"
    Trả về chỉ một từ: "yes" hoặc "no".
    """
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return response.content.lower() == "yes"

async def is_programming_question(question: str) -> bool:
    prompt = f"""
    Bạn là một trợ lý phân loại câu hỏi. Hãy xác định xem câu hỏi sau có liên quan đến lập trình C hay không. Chỉ xem xét các câu hỏi liên quan đến cú pháp, cách sử dụng, hoặc khái niệm trong ngôn ngữ lập trình C.
    Câu hỏi: "{question}"
    Trả về chỉ một từ: "yes" hoặc "no".
    """
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return response.content.lower() == "yes"

