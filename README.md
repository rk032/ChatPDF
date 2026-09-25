# ChatPDF — Adaptive RAG

A full-stack **ChatPDF application** that allows users to upload PDF documents and ask questions about their contents using an **Adaptive Retrieval-Augmented Generation (RAG)** pipeline.

The system combines PDF processing, semantic embeddings, Qdrant Cloud, MMR retrieval, step-back query transformation, Google Gemini, and Tavily web search behind a FastAPI backend with a Streamlit frontend.

---

## Features

- User registration and JWT authentication
- Upload and process multiple PDF documents
- PDF text extraction with OCR support
- Semantic search using BGE embeddings
- Qdrant Cloud vector storage
- MMR-based retrieval
- Step-back query transformation
- Adaptive web search fallback using Tavily
- Google Gemini for query processing and answer generation
- User-specific document retrieval
- FastAPI backend
- Streamlit frontend

---

## Architecture

```text
                         ┌──────────────────┐
                         │    Streamlit     │
                         │     Frontend     │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │     FastAPI      │
                         │      Backend     │
                         └────────┬─────────┘
                                  │
              ┌───────────────────┴───────────────────┐
              │                                       │
              ▼                                       ▼
       ┌──────────────┐                        ┌──────────────┐
       │ PDF Processor│                        │  Adaptive RAG│
       └──────┬───────┘                        └──────┬───────┘
              │                                       │
              ▼                                       ▼
       ┌──────────────┐                        ┌──────────────┐
       │    BGE       │                        │ Step-back    │
       │  Embeddings  │                        │    Query     │
       └──────┬───────┘                        └──────┬───────┘
              │                                       │
              ▼                                       ▼
       ┌──────────────┐                        ┌──────────────┐
       │   Qdrant     │◄───────────────────────│ MMR Retrieval│
       │    Cloud     │                        └──────┬───────┘
       └──────────────┘                               │
                                                     ▼
                                            ┌─────────────────┐
                                            │ Context Check   │
                                            └────────┬────────┘
                                                     │
                                      ┌──────────────┴──────────────┐
                                      │                             │
                                  Sufficient                  Insufficient
                                      │                             │
                                      ▼                             ▼
                                  ┌─────────┐                ┌──────────┐
                                  │ Gemini  │                │  Tavily  │
                                  │   LLM   │                │   Web    │
                                  └────┬────┘                └────┬─────┘
                                       │                            │
                                       └────────────┬───────────────┘
                                                    ▼
                                                 Answer
```

---

## How It Works

The application follows an adaptive RAG pipeline rather than sending every question directly to an LLM.

### PDF Processing

Uploaded PDFs are processed to extract their content. OCR is used when required for image-based PDF content. The extracted text is divided into smaller chunks for efficient retrieval.

### Embeddings

Document chunks are converted into semantic vector representations using `BAAI/bge-small-en-v1.5` and stored in Qdrant Cloud.

### Retrieval

The user's question is transformed using **step-back prompting**, and relevant document chunks are retrieved from Qdrant using **Maximum Marginal Relevance (MMR)**.

MMR helps retrieve relevant information while reducing repetitive results.

### Context Evaluation

The retrieved PDF context is evaluated to determine whether it contains enough information to answer the question.

### Adaptive Web Search

If the PDF context is insufficient, the system uses **Tavily** to search for additional information. The retrieved PDF and web information can then be combined before being passed to Gemini.

### Answer Generation

Google Gemini uses the available context to generate the final answer.

---

## Tech Stack

### Frontend
- Streamlit
- Python
- Requests

### Backend
- FastAPI
- Uvicorn
- Pydantic

### RAG / AI
- LangChain
- Google Gemini
- Hugging Face

### Vector Database
- Qdrant Cloud

### PDF Processing
- PyMuPDF
- Tesseract OCR
- Pillow

### Web Search
- Tavily

### Authentication
- SQLite
- JWT
- Werkzeug

---

## Project Structure

```text
ChatPDF/
│
├── api/
│   ├── app.py
│   ├── database.py
│   ├── models.py
│   └── pdf_processor.py
│
├── model_code/
│   ├── query_processor.py
│   ├── retriever.py
│   ├── web_search.py
│   └── adaptive_rag.py
│
├── frontend/
│   └── app.py
│
├── .gitignore
├── requirements.txt
```

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/rk032/ChatPDF.git
cd ChatPDF
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

On Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your_google_api_key
QDRANT_URL=your_qdrant_cloud_url
QDRANT_API_KEY=your_qdrant_api_key
TAVILY_API_KEY=your_tavily_api_key
DB_PATH=chat_app.db
SECRET_KEY=your_secret_key
```

## Running the Application

The application currently runs locally using a FastAPI backend and Streamlit frontend.

### Start the Backend

From the project root:

```bash
python -m api.app
```

### Start the Frontend

Open another terminal and run:

```bash
streamlit run frontend/app.py
```

The Streamlit application will normally be available at:

---

## Application Flow

```text
Create Account
      │
      ▼
    Login
      │
      ▼
 Upload PDF
      │
      ▼
Process & Store
      │
      ▼
 Ask Question
      │
      ▼
 Retrieve Relevant Context
      │
      ▼
 Adaptive RAG
      │
      ▼
    Answer
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/register` | Create a new user account |
| `POST` | `/token` | Authenticate and receive a JWT |
| `POST` | `/upload-pdfs` | Upload PDF documents |
| `POST` | `/ask` | Ask questions about uploaded documents |

Protected endpoints require JWT authentication.

---

## Security

The application includes:

- Password hashing
- JWT-based authentication
- User-specific document retrieval
- Environment-based API key management

Each authenticated user's documents are isolated during retrieval using their user identity.

---

## Current Status

The project is currently under development and is being tested locally.

The core RAG pipeline and application components are implemented, including:

- PDF processing
- OCR
- Document chunking
- Local embeddings
- Qdrant Cloud storage
- MMR retrieval
- Step-back querying
- Gemini integration
- Tavily web search
- Adaptive RAG
- JWT authentication
- FastAPI backend
- Streamlit frontend

Deployment is not part of the current implementation.

---
