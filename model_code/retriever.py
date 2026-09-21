import os
from typing import List

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient


class MMRRetriever:
    """
    Handles retrieval of relevant PDF chunks from Qdrant Cloud.

    Retrieval strategy:
        Maximal Marginal Relevance (MMR)

    The retriever also restricts results to the authenticated
    user's documents using the user_id metadata field.
    """

    def __init__(self):

        # ---------------------------------------------------------
        # Environment variables
        # ---------------------------------------------------------

        self.qdrant_url = os.getenv("QDRANT_URL")
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY")

        if not self.qdrant_url:
            raise ValueError(
                "QDRANT_URL is missing from environment variables"
            )

        if not self.qdrant_api_key:
            raise ValueError(
                "QDRANT_API_KEY is missing from environment variables"
            )

        # ---------------------------------------------------------
        # Qdrant
        # ---------------------------------------------------------

        self.client = QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key,
        )

        # ---------------------------------------------------------
        # BGE-small embeddings
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

        # ---------------------------------------------------------
        # Collection
        # ---------------------------------------------------------

        self.collection_name = "chatpdf_test2"

        # ---------------------------------------------------------
        # Qdrant vector store
        # ---------------------------------------------------------

        self.vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embedding=self.embed_model,
        )

    # =========================================================
    # MMR RETRIEVAL
    # =========================================================

    def retrieve(
        self,
        question: str,
        user_id: str,
        k: int = 4,
        fetch_k: int = 10,
        lambda_mult: float = 0.5,
    ) -> List[Document]:
        """
        Retrieve documents using Maximal Marginal Relevance.

        Parameters
        ----------
        question:
            User's original question.

        user_id:
            Authenticated user's ID.

        k:
            Number of final documents returned.

        fetch_k:
            Number of candidate documents considered before MMR.

        lambda_mult:
            Balance between relevance and diversity.

            1.0 -> prioritize relevance
            0.0 -> prioritize diversity
        """

        # -----------------------------------------------------
        # User filter
        # -----------------------------------------------------

        qdrant_filter = {
            "must": [
                {
                    "key": "metadata.user_id",
                    "match": {
                        "value": user_id
                    },
                }
            ]
        }

        # -----------------------------------------------------
        # Create retriever
        # -----------------------------------------------------

        retriever = self.vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": k,
                "fetch_k": fetch_k,
                "lambda_mult": lambda_mult,
                "filter": qdrant_filter,
            },
        )

        # -----------------------------------------------------
        # Retrieve
        # -----------------------------------------------------

        documents = retriever.invoke(question)

        return documents