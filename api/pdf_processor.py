import io
import os
import uuid
from typing import List, Dict, Any

import pymupdf
import pytesseract
from PIL import Image
from fastapi import UploadFile

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models


class PDFProcessor:
    """
    Handles PDF ingestion.

    Responsibilities:
    1. Extract text from PDFs page-by-page.
    2. OCR images contained inside PDFs.
    3. Split extracted content into chunks.
    4. Generate BGE-small embeddings.
    5. Store chunks + metadata in Qdrant Cloud.

    Retrieval and answer generation will be handled by separate
    components later.
    """

    def __init__(self):

        # ---------------------------------------------------------
        # Environment variables
        # ---------------------------------------------------------

        self.QDRANT_URL = os.getenv("QDRANT_URL")
        self.QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

        if not self.QDRANT_URL:
            raise ValueError("QDRANT_URL is missing from environment variables")

        if not self.QDRANT_API_KEY:
            raise ValueError(
                "QDRANT_API_KEY is missing from environment variables"
            )

        # ---------------------------------------------------------
        # Qdrant Cloud
        # ---------------------------------------------------------

        self.client = QdrantClient(
            url=self.QDRANT_URL,
            api_key=self.QDRANT_API_KEY,
        )

        # ---------------------------------------------------------
        # Embedding model
        # ---------------------------------------------------------

        self.embed_model = HuggingFaceEmbeddings(
            model_name="BAAI/bge-small-en-v1.5",
            model_kwargs={
                "device": "cpu"
            },
            encode_kwargs={
                "normalize_embeddings": True
            },
        )

        # Get embedding dimension dynamically.
        test_embedding = self.embed_model.embed_query("test")
        self.embedding_dimension = len(test_embedding)

        # ---------------------------------------------------------
        # Text splitter
        # ---------------------------------------------------------

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=150,
            separators=[
                "\n\n",
                "\n",
                ". ",
                " ",
                "",
            ],
        )

    # =============================================================
    # PUBLIC METHOD
    # =============================================================

    async def process_pdfs(
        self,
        files: List[UploadFile],
        collection_name: str,
        user_id: str,
    ):
        """
        Process uploaded PDFs and store their chunks in Qdrant.
        """

        if not files:
            raise ValueError("No PDF files were provided")

        # Make sure the collection exists.
        self._ensure_collection(collection_name)

        all_documents = []

        for file in files:

            if not file.filename.lower().endswith(".pdf"):
                continue

            contents = await file.read()

            if not contents:
                continue

            documents = self._process_single_pdf(
                contents=contents,
                filename=file.filename,
                user_id=user_id,
            )

            all_documents.extend(documents)

        if not all_documents:
            raise ValueError("No readable content was extracted from the PDFs")

        # Store documents in Qdrant.
        vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=collection_name,
            embedding=self.embed_model,
        )

        texts = [
            document["text"]
            for document in all_documents
        ]

        metadatas = [
            document["metadata"]
            for document in all_documents
        ]

        vector_store.add_texts(
            texts=texts,
            metadatas=metadatas,
        )

        return {
            "files_processed": len(files),
            "chunks_created": len(all_documents),
            "collection_name": collection_name,
        }

    # =============================================================
    # PDF PROCESSING
    # =============================================================

    def _process_single_pdf(
        self,
        contents: bytes,
        filename: str,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Process one PDF while preserving page-level metadata.
        """

        pdf_document = pymupdf.open(
            stream=contents,
            filetype="pdf",
        )

        documents = []

        try:

            for page_number, page in enumerate(
                pdf_document,
                start=1,
            ):

                # -------------------------------------------------
                # Extract normal PDF text
                # -------------------------------------------------

                page_text = page.get_text("text") or ""

                # -------------------------------------------------
                # Extract and OCR images
                # -------------------------------------------------

                ocr_text = self._extract_image_text(
                    pdf_document,
                    page,
                )

                # Combine text sources.
                combined_text = (
                    page_text.strip()
                    + "\n"
                    + ocr_text.strip()
                ).strip()

                if not combined_text:
                    continue

                # -------------------------------------------------
                # Chunk this page independently
                # -------------------------------------------------

                chunks = self.text_splitter.split_text(
                    combined_text
                )

                for chunk_index, chunk in enumerate(
                    chunks
                ):

                    metadata = {
                        "user_id": user_id,
                        "pdf_name": filename,
                        "page_number": page_number,
                        "chunk_index": chunk_index,
                        "chunk_id": str(uuid.uuid4()),
                    }

                    documents.append(
                        {
                            "text": chunk,
                            "metadata": metadata,
                        }
                    )

        finally:
            pdf_document.close()

        return documents

    # =============================================================
    # OCR
    # =============================================================

    def _extract_image_text(
        self,
        pdf_document,
        page,
    ) -> str:
        """
        Extract images from a PDF page and run OCR on them.
        """

        ocr_results = []

        images = page.get_images(full=True)

        for image_info in images:

            xref = image_info[0]

            try:

                base_image = pdf_document.extract_image(
                    xref
                )

                image_bytes = base_image["image"]

                image = Image.open(
                    io.BytesIO(image_bytes)
                )

                text = pytesseract.image_to_string(
                    image
                )

                if text and text.strip():
                    ocr_results.append(
                        text.strip()
                    )

            except Exception:
                # If an individual image cannot be processed,
                # continue processing the rest of the PDF.
                continue

        return "\n".join(ocr_results)

    # =============================================================
    # QDRANT
    # =============================================================

    def _ensure_collection(
        self,
        collection_name: str,
    ):
        """
        Create the Qdrant collection if it doesn't exist.
        """

        collections = self.client.get_collections()

        exists = any(
            collection.name == collection_name
            for collection in collections.collections
        )

        if exists:
            return

        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=self.embedding_dimension,
                distance=models.Distance.COSINE,
            ),
        )

        self.client.create_payload_index(
            collection_name=collection_name,
            field_name="metadata.user_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )