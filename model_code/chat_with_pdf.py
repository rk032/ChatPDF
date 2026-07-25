import streamlit as st
from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import os
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
import google.generativeai as genai
from langchain_community.vectorstores import Qdrant
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
import uuid
import qdrant_client
from qdrant_client.http import models
import hashlib
import warnings 
warnings.filterwarnings("ignore")

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

# Validate API keys
if not all([GOOGLE_API_KEY, QDRANT_URL, QDRANT_API_KEY]):
    raise ValueError("Missing required API keys in environment variables")

# Initialize Qdrant client
client = qdrant_client.QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY,
)

try:
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    st.error(f"Error configuring Google API: {str(e)}")
    raise

# Set model name with fallback
model_name = os.getenv("MODEL_NAME", "gemini-pro")

# Initialize BGE embeddings
embed_model = HuggingFaceBgeEmbeddings(
    model_name="BAAI/bge-large-en",
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': True}
)

def generate_user_id(email):
    """Generate a consistent user ID from email"""
    return hashlib.md5(email.lower().encode()).hexdigest()

def init_session_state():
    """Initialize session state variables"""
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None

def login_user():
    """Handle user login"""
    st.sidebar.title("User Login")
    email = st.sidebar.text_input("Enter your email")
    if email:
        user_id = generate_user_id(email)
        st.session_state.user_email = email
        st.session_state.user_id = user_id
        return True
    return False

def get_pdf_text(pdf_docs):
    try:
        text = ""
        pdf_metadata = {}
        for pdf in pdf_docs:
            pdf_reader = PdfReader(pdf)
            pdf_text = ""
            for page in pdf_reader.pages:
                pdf_text += page.extract_text()
            text += pdf_text
            # Store text with PDF name
            pdf_metadata[pdf.name] = pdf_text
        return text, pdf_metadata
    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
        raise

def get_text_chunks(text, metadata):
    try:
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = text_splitter.split_text(text)
        
        # Create chunks with metadata
        chunks_with_metadata = []
        for chunk in chunks:
            # Find which PDF this chunk belongs to
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
    except Exception as e:
        st.error(f"Error splitting text: {str(e)}")
        raise

def get_vector_store(chunks_with_metadata, collection_name):
    try:
        # Create or get collection
        collections = client.get_collections().collections
        collection_exists = any(c.name == collection_name for c in collections)
        
        if not collection_exists:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=len(embed_model.client.encode("test")),
                    distance=models.Distance.COSINE
                )
            )

        # Create Qdrant vector store
        texts = [chunk["text"] for chunk in chunks_with_metadata]
        metadatas = [chunk["metadata"] for chunk in chunks_with_metadata]
        
        vector_store = Qdrant(
            client=client,
            collection_name=collection_name,
            embeddings=embed_model
        )
        
        # Add texts with metadata
        vector_store.add_texts(texts=texts, metadatas=metadatas)
        
        return vector_store
    except Exception as e:
        st.error(f"Error creating vector store: {str(e)}")
        raise


def get_conversational_chain():
    try:
        prompt_template = """
        Answer the question as detailed as possible from the provided context, make sure to provide all the details, if the answer is not in
        provided context just say, "answer is not available in the context", don't provide the wrong answer\n\n
        Context:\n {context}?\n
        Question: \n{question}\n

        Answer:
        """

        model = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0.3,
            google_api_key=GOOGLE_API_KEY
        )

        prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
        chain = load_qa_chain(model, chain_type="stuff", prompt=prompt)
        return chain
    except Exception as e:
        st.error(f"Error creating conversation chain: {str(e)}")
        raise

def user_input(user_question, collection_name):
    try:
        vector_store = Qdrant(
            client=client,
            collection_name=collection_name,
            embeddings=embed_model
        )
        
        docs = vector_store.similarity_search(user_question)
        chain = get_conversational_chain()
        
        response = chain(
            {"input_documents":docs, "question": user_question},
            return_only_outputs=True
        )
        
        # Display source PDF information
        source_pdfs = set(doc.metadata.get('pdf_name', 'Unknown') for doc in docs)
        st.info(f"Sources: {', '.join(source_pdfs)}")
        
        st.write("Reply: ", response["output_text"])
    except Exception as e:
        st.error(f"Error processing question: {str(e)}")
        raise

import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

# Database initialization
DB_PATH = "user_data.db"

def init_db():
    """Initialize the SQLite database and create tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            user_id TEXT UNIQUE NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def register_user(email, password):
    """Register a new user with email and hashed password."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Generate unique user ID
        user_id = generate_user_id(email)
        hashed_password = generate_password_hash(password)
        
        cursor.execute("INSERT INTO users (email, password, user_id) VALUES (?, ?, ?)",
                       (email, hashed_password, user_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        st.error("Email already registered!")
        return False
    except Exception as e:
        st.error(f"Error registering user: {str(e)}")
        return False

def login_user(email, password):
    """Authenticate a user by email and password."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT password, user_id FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        conn.close()
        
        if row and check_password_hash(row[0], password):
            st.session_state.user_email = email
            st.session_state.user_id = row[1]
            return True
        else:
            st.error("Invalid email or password!")
            return False
    except Exception as e:
        st.error(f"Error logging in: {str(e)}")
        return False

def login_or_register():
    """Handle user login or registration."""
    st.sidebar.title("User Authentication")
    auth_action = st.sidebar.radio("Choose Action", ["Login", "Register"])
    
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Password", type="password")
    
    if st.sidebar.button("Submit"):
        if auth_action == "Login":
            if login_user(email, password):
                st.sidebar.success("Logged in successfully!")
        elif auth_action == "Register":
            if register_user(email, password):
                st.sidebar.success("Registered successfully! Please log in.")


def main():
    try:
        st.set_page_config(page_title="Chat PDF")
        st.header("Chat with PDF using Gemini💁")
        
        init_session_state()
        
        # Handle login or registration
        if not st.session_state.user_id:
            login_or_register()
            if not st.session_state.user_id:
                st.warning("Please log in or register to continue.")
                return
        
        # Display user info 
        st.sidebar.success(f"Logged in as: {st.session_state.user_email}")
        
        user_question = st.text_input("Ask a Question from the PDF Files")
        
        if user_question and st.session_state.user_id:
            user_input(user_question, st.session_state.user_id)

        with st.sidebar:
            st.title("Menu:")
            pdf_docs = st.file_uploader("Upload your PDF Files and Click on the Submit & Process Button", accept_multiple_files=True)
            if st.button("Submit & Process"):
                if not pdf_docs:
                    st.error("Please upload at least one PDF file")
                    return
                    
                with st.spinner("Processing..."):
                    raw_text, pdf_metadata = get_pdf_text(pdf_docs)
                    chunks_with_metadata = get_text_chunks(raw_text, pdf_metadata)
                    get_vector_store(chunks_with_metadata, st.session_state.user_id)
                    st.success("Done")

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")

        
if __name__ == "__main__":
    init_db()
    main()
