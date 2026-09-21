import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

load_dotenv()


class QueryProcessor:

    def __init__(self):

        google_api_key = os.getenv("GOOGLE_API_KEY")

        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY not found in .env")

        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3.6-flash",
            temperature=0,
            google_api_key=google_api_key,
        )

        self.step_back_prompt = PromptTemplate.from_template(
            """
Rewrite the following question into a broader question
that captures the underlying topic.

Do not answer the question.
Return only the rewritten question.

Question: {question}
"""
        )

    def step_back_query(self, question: str) -> str:

        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")

        chain = self.step_back_prompt | self.llm

        response = chain.invoke({
            "question": question.strip()
        })

        content = response.content

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            texts = []

            for item in content:
                if isinstance(item, str):
                    texts.append(item)

                elif isinstance(item, dict) and "text" in item:
                    texts.append(item["text"])

            return " ".join(texts).strip()

        return str(content).strip()