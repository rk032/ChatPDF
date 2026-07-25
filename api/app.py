# api/app.py
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os
from dotenv import load_dotenv
from .pdf_processor import PDFProcessor
from .models import UserCreate, User, Question
from database import get_db, Database

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize PDF Processor
pdf_processor = PDFProcessor()

# API Routes
@app.post("/register")
async def register(user: UserCreate, db: Database = Depends(get_db)):
    db_user = db.get_user_by_email(user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return db.create_user(user.email, user.password)

from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/token")
async def login(form_data: LoginRequest, db: Database = Depends(get_db)):
    try:
        user = db.get_user_by_email(form_data.username)
        print(user)
        print(form_data)
        if not user or form_data.password != user.password:
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        return {"message": "Login successful"}
    except Exception as e:
        print(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload-pdfs")
async def upload_pdfs(files: List[UploadFile] = File(...), db: Database = Depends(get_db)):
    try:
        await pdf_processor.process_pdfs(files, collection_name="default")  # Use a default collection name for simplicity
        return {"message": "PDFs processed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ask")
async def ask_question(question: Question, db: Database = Depends(get_db)):
    try:
        response = await pdf_processor.get_answer(question.question, collection_name="default")
        return {"answer": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
