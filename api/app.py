# api/app.py

import os
from datetime import datetime, timedelta, timezone
from typing import List

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from .pdf_processor import PDFProcessor
from .models import UserCreate, Question
from .database import get_db, Database

from model_code.rag_main import AdaptiveRAG


# --------------------------------------------------
# Environment
# --------------------------------------------------

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise ValueError("SECRET_KEY not found in .env")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


# --------------------------------------------------
# FastAPI
# --------------------------------------------------

app = FastAPI(title="ChatPDF API")


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Initialize Components
# --------------------------------------------------

pdf_processor = PDFProcessor()
adaptive_rag = AdaptiveRAG()

COLLECTION_NAME = "chatpdf_documents"


# --------------------------------------------------
# Authentication
# --------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class LoginRequest(BaseModel):
    username: str
    password: str


def create_access_token(user_id: str):
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": user_id,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def get_current_user(
    token: str = Depends(oauth2_scheme),
):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        user_id = payload.get("sub")

        if user_id is None:
            raise credentials_exception

        return user_id

    except JWTError:
        raise credentials_exception


# --------------------------------------------------
# Register
# --------------------------------------------------

@app.post("/register")
async def register(
    user: UserCreate,
    db: Database = Depends(get_db),
):
    db_user = db.get_user_by_email(user.email)

    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered",
        )

    return db.create_user(
        user.email,
        user.password,
    )


# --------------------------------------------------
# Login
# --------------------------------------------------

@app.post("/token")
async def login(
    form_data: LoginRequest,
    db: Database = Depends(get_db),
):
    user = db.get_user_by_email(form_data.username)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
        )

    # Verify the plaintext password against
    # the hashed password stored in SQLite.
    if not db.verify_password(
        form_data.password,
        user.password,
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
        )

    access_token = create_access_token(
        user_id=user.user_id
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


# --------------------------------------------------
# Upload PDFs
# --------------------------------------------------

@app.post("/upload-pdfs")
async def upload_pdfs(
    files: List[UploadFile] = File(...),
    user_id: str = Depends(get_current_user),
):
    try:
        await pdf_processor.process_pdfs(
            files=files,
            collection_name=COLLECTION_NAME,
            user_id=user_id,
        )

        return {
            "message": "PDFs processed successfully",
            "user_id": user_id,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# --------------------------------------------------
# Ask Question
# --------------------------------------------------

@app.post("/ask")
async def ask_question(
    question: Question,
    user_id: str = Depends(get_current_user),
):
    try:
        result = adaptive_rag.get_answer(
            question=question.question,
            user_id=user_id,
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# --------------------------------------------------
# Run Server
# --------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )