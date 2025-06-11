from langchain.prompts import PromptTemplate

# Tùy chỉnh hướng dẫn theo mức độ Bloom
bloom_instructions = {
    "remember": "Hãy đưa ra câu trả lời ngắn gọn, đúng trọng tâm để giúp sinh viên ghi nhớ kiến thức cơ bản về ngôn ngữ lập trình C.",
    "understand": "Hãy giải thích rõ ràng, dễ hiểu để giúp sinh viên hiểu khái niệm, ý nghĩa hoặc cách hoạt động của kiến thức C.",
    "apply": "Hãy hướng dẫn cách áp dụng kiến thức vào một ví dụ thực tế bằng ngôn ngữ C. Có thể minh họa bằng đoạn mã.",
    "analyze": "Hãy phân tích chi tiết câu hỏi, so sánh các khía cạnh khác nhau hoặc nêu rõ các thành phần trong ví dụ về lập trình C.",
    "evaluate": "Hãy đưa ra nhận xét hoặc đánh giá về phương pháp/giải pháp trong câu hỏi, nêu rõ ưu và nhược điểm trong ngữ cảnh lập trình C.",
    "create": "Hãy gợi ý cách kết hợp các kiến thức đã học để tạo ra một đoạn mã hoàn chỉnh hoặc giải pháp mới bằng ngôn ngữ C.",
}

def create_prompt(question: str, retrieved_docs: list, bloomLevel: str):
    context = "\n".join([doc.page_content for doc in retrieved_docs])
    print(context)
    instruction = bloom_instructions.get(bloomLevel.lower(), bloom_instructions["understand"])

    prompt_template = PromptTemplate(
        input_variables=["question", "context", "instruction"],
        template="""
        Bạn là một trợ lý lập trình thân thiện, đang giúp sinh viên năm nhất học ngôn ngữ lập trình C.
        
        {instruction}
        
        Dưới đây là phần tài liệu tham khảo:
        {context}

        Câu hỏi của sinh viên: {question}

        Trả lời bằng tiếng Việt, dễ hiểu và phù hợp với sinh viên mới học lập trình.
        Nếu trong tài liệu không có câu trả lời, hãy trả lời "Không tìm thấy thông tin phù hợp"
        Nếu tài liệu không đề cập không phù hợp, bạn có thể tự đưa ra ví dụ khác phù hợp.
        """
    )

    return prompt_template.format(question=question, context=context, instruction=instruction)
