import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

from model_code.query_processor import QueryProcessor
from model_code.retriever import MMRRetriever
from model_code.web_search import WebSearch


load_dotenv()


class AdaptiveRAG:

    def __init__(self):

        google_api_key = os.getenv("GOOGLE_API_KEY")

        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY not found in .env")

        # LLM
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3.6-flash",
            google_api_key=google_api_key,
        )

        # Components
        self.query_processor = QueryProcessor()
        self.retriever = MMRRetriever()
        self.web_search = WebSearch()

        # Context sufficiency prompt
        self.sufficiency_prompt = PromptTemplate.from_template(
            """
Determine whether the provided context contains enough information
to answer the question.

Return ONLY one word:

YES
or
NO

Question:
{question}

Context:
{context}
"""
        )

        # Final answer prompt
        self.answer_prompt = PromptTemplate.from_template(
            """
You are a helpful assistant.

Answer the question using the provided information.

Rules:
- Use the provided information as the primary source.
- Do not invent facts.
- If the information is insufficient, clearly say so.
- Give a concise and useful answer.

Question:
{question}

Information:
{context}

Answer:
"""
        )

    def _format_documents(self, documents):

        if not documents:
            return "No relevant information was retrieved."

        formatted = []

        for i, doc in enumerate(documents, 1):

            metadata = doc.metadata

            pdf_name = metadata.get("pdf_name", "Unknown")
            page_number = metadata.get("page_number", "Unknown")

            formatted.append(
                f"[Document {i}]\n"
                f"PDF: {pdf_name}\n"
                f"Page: {page_number}\n"
                f"Content:\n{doc.page_content}"
            )

        return "\n\n".join(formatted)

    def _is_context_sufficient(self, question, context):

        chain = self.sufficiency_prompt | self.llm

        response = chain.invoke({
            "question": question,
            "context": context,
        })

        result = response.content

        if isinstance(result, list):
            result = " ".join(
                item.get("text", "")
                for item in result
                if isinstance(item, dict)
            )

        return result.strip().upper().startswith("YES")

    def _generate_answer(self, question, context):

        chain = self.answer_prompt | self.llm

        response = chain.invoke({
            "question": question,
            "context": context,
        })

        result = response.content

        if isinstance(result, list):
            result = " ".join(
                item.get("text", "")
                for item in result
                if isinstance(item, dict)
            )

        return result.strip()

    def get_answer(self, question, user_id):

        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")

        if not user_id:
            raise ValueError("user_id is required.")

        # -------------------------------------------------
        # STEP 1: Create step-back query
        # -------------------------------------------------

        step_back_query = self.query_processor.step_back_query(
            question
        )

        # -------------------------------------------------
        # STEP 2: Retrieve from user's PDFs
        # -------------------------------------------------

        documents = self.retriever.retrieve(
            question=step_back_query,
            user_id=user_id,
            k=4,
            fetch_k=10,
            lambda_mult=0.5,
        )

        pdf_context = self._format_documents(documents)

        # -------------------------------------------------
        # STEP 3: Check whether PDF context is sufficient
        # -------------------------------------------------

        sufficient = self._is_context_sufficient(
            question,
            pdf_context,
        )

        # -------------------------------------------------
        # STEP 4A: PDF context is sufficient
        # -------------------------------------------------

        if sufficient:

            answer = self._generate_answer(
                question,
                pdf_context,
            )

            return {
                "answer": answer,
                "source": "pdf",
                "documents": documents,
                "step_back_query": step_back_query,
            }

        # -------------------------------------------------
        # STEP 4B: PDF context is insufficient
        # -------------------------------------------------

        web_results = self.web_search.search(
            question,
            max_results=5,
        )

        if web_results:

            web_context = "\n\n".join(
                f"[Web Result {i}]\n"
                f"Title: {result.get('title', '')}\n"
                f"URL: {result.get('url', '')}\n"
                f"Content:\n{result.get('content', '')}"
                for i, result in enumerate(web_results, 1)
            )

        else:

            web_context = "No web results were found."

        # -------------------------------------------------
        # STEP 5: Combine PDF + web context
        # -------------------------------------------------

        combined_context = (
            "INFORMATION FROM USER'S PDF:\n"
            f"{pdf_context}\n\n"
            "INFORMATION FROM WEB SEARCH:\n"
            f"{web_context}"
        )

        answer = self._generate_answer(
            question,
            combined_context,
        )

        return {
            "answer": answer,
            "source": "web",
            "documents": documents,
            "web_results": web_results,
            "step_back_query": step_back_query,
        }