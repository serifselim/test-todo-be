from http import client

from fastapi import FastAPI, Depends
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from groq import Groq
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Geliştirme için
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# BURAYA KENDİ CONNECTION STRING'İNİ YAPIŞTIR
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class TodoDB(Base):
    __tablename__ = "todos"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class SuggestRequest(BaseModel):
    topic: str

# Tabloyu otomatik oluştur
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Todo(BaseModel):
    id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    completed: bool = False
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

@app.post("/suggest")
def suggest_todos(req: SuggestRequest):
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": "Sen bir yardımcı asistansın. Kullanıcının verdiği konuyla ilgili 5 adet kısa ve net todo önerisi üret. Sadece liste halinde yaz, başka bir şey ekleme."},
            {"role": "user", "content": req.topic}
        ]
    )
    suggestions = response.choices[0].message.content
    return {"suggestions": suggestions}

@app.get("/todos")
def get_todos(db: Session = Depends(get_db)):
    return db.query(TodoDB).all()

@app.post("/todos")
def create_todo(todo: Todo, db: Session = Depends(get_db)):
    db_todo = TodoDB(
        title=todo.title,
        description=todo.description,
        completed=todo.completed
    )
    db.add(db_todo)
    db.commit()
    db.refresh(db_todo)
    return db_todo

@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    todo = db.query(TodoDB).filter(TodoDB.id == todo_id).first()
    if not todo:
        return {"error": "Bulunamadı"}
    db.delete(todo)
    db.commit()
    return {"message": "Silindi"}

@app.put("/todos/check/{todo_id}")
def check_todo(todo_id: int, db: Session = Depends(get_db)):
    todo = db.query(TodoDB).filter(TodoDB.id == todo_id).first()
    if not todo:
        return {"error": "Bulunamadı"}
    todo.completed = not todo.completed
    db.commit()
    db.refresh(todo)
    return todo

@app.put("/todos/{todo_id}")
def update_todo(todo_id: int, updated: Todo, db: Session = Depends(get_db)):
    todo = db.query(TodoDB).filter(TodoDB.id == todo_id).first()
    if not todo:
        return {"error": "Bulunamadı"}
    todo.title = updated.title
    todo.description = updated.description
    todo.completed = updated.completed
    db.commit()
    db.refresh(todo)
    return todo