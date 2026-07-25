# api/pdf_processor.py
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_community.vectorstores import Qdrant
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
import google.generativeai as genai
import qdrant_client
from qdrant_client.http import models
import os
import io
import fitz
import pytesseract
from PIL import Image
from typing import List
from fastapi import UploadFile
import uuid

class PDFProcessor:
    def __init__(self):
        # Initialize configurations
        self.GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        self.QDRANT_URL = os.getenv("QDRANT_URL")
        self.QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
        
        # Initialize clients and models
        genai.configure(api_key=self.GOOGLE_API_KEY)
        self.client = qdrant_client.QdrantClient(
            url=self.QDRANT_URL,
            api_key=self.QDRANT_API_KEY,
        )
        self.embed_model = HuggingFaceBgeEmbeddings(
            model_name="BAAI/bge-large-en",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        self.model_name = "gemini-pro"

    async def process_pdfs(self, files: List[UploadFile], collection_name: str):
        # Extract text from PDFs
        text, pdf_metadata = await self._get_pdf_text(files)
        
        # Create text chunks
        chunks_with_metadata = self._get_text_chunks(text, pdf_metadata)
        
        # Store in vector database
        await self._store_vectors(chunks_with_metadata, collection_name)

    async def _get_pdf_text(self, files: List[UploadFile]):
        text = ""
        pdf_metadata = {}
        
        for file in files:
            contents = await file.read()
            pdf_text = ""
            
            # Process with PyPDF2
            pdf_reader = PdfReader(io.BytesIO(contents))
            pdf_document = fitz.open("pdf", contents)
            
            for page_index, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                pdf_text += page_text
                
                # Process images in PDF
                pdf_page = pdf_document[page_index]
                for img in pdf_page.get_images(full=True):
                    xref = img[0]
                    base_image = pdf_document.extract_image(xref)
                    image_bytes = base_image["image"]
                    image = Image.open(io.BytesIO(image_bytes))
                    ocr_text = pytesseract.image_to_string(image)
                    pdf_text += ocr_text
            
            text += pdf_text
            pdf_metadata[file.filename] = pdf_text
            
        return text, pdf_metadata

    def _get_text_chunks(self, text: str, metadata: dict):
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=100
        )
        chunks = text_splitter.split_text(text)
        
        chunks_with_metadata = []
        for chunk in chunks:
            for pdf_name, pdf_text in metadata.items():
                if chunk in pdf_text:
                    chunks_with_metadata.append({
                        "text": chunk,
                        "metadata": {
                            "pdf_name": pdf_name,
                            "chunk_id": str(uuid.uuid4())
                        }
                    })
                    break
        
        return chunks_with_metadata

    async def _store_vectors(self, chunks_with_metadata: List[dict], collection_name: str):
        collections = self.client.get_collections().collections
        collection_exists = any(c.name == collection_name for c in collections)
        
        if not collection_exists:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=len(self.embed_model.client.encode("test")),
                    distance=models.Distance.COSINE
                )
            )
        
        texts = [chunk["text"] for chunk in chunks_with_metadata]
        metadatas = [chunk["metadata"] for chunk in chunks_with_metadata]
        
        vector_store = Qdrant(
            client=self.client,
            collection_name=collection_name,
            embeddings=self.embed_model
        )
        
        vector_store.add_texts(texts=texts, metadatas=metadatas)

    async def get_answer(self, question: str, collection_name: str) -> str:
        vector_store = Qdrant(
            client=self.client,
            collection_name=collection_name,
            embeddings=self.embed_model
        )
        
        docs = vector_store.similarity_search(question)
        chain = self._get_conversational_chain()
        
        response = chain(
            {"input_documents": docs, "question": question},
            return_only_outputs=True
        )
        
        return response["output_text"]

    def _get_conversational_chain(self):
        prompt_template = """
        Answer the question as detailed as possible from the provided context, make sure to provide all the details, if the answer is not in
        provided context just say, "answer is not available in the context", don't provide the wrong answer\n\n
        Context:\n {context}?\n
        Question: \n{question}\n

        Answer:
        """

        model = ChatGoogleGenerativeAI(
            model=self.model_name,
            temperature=0.3,
            google_api_key=self.GOOGLE_API_KEY
        )

        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question"]
        )
        
        return load_qa_chain(model, chain_type="stuff", prompt=prompt)