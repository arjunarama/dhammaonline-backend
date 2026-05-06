from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from database import engine, create_db_and_tables
from models import Teaching

app = FastAPI()

origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://dhammaonline.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


@app.get("/")
def home():
    return {
        "message": "Dhamma Online FastAPI Backend Running"
    }


@app.get("/teachings")
def get_teachings():
    with Session(engine) as session:
        teachings = session.exec(select(Teaching)).all()
        return teachings
    

@app.post("/teachings")
def create_teaching(teaching: Teaching):
    with Session(engine) as session:
        session.add(teaching)
        session.commit()
        session.refresh(teaching)
        return teaching
    
@app.put("/teachings/{teaching_id}")
def update_teaching(teaching_id: int, updated_teaching: Teaching):
    with Session(engine) as session:

        teaching = session.get(Teaching, teaching_id)

        if not teaching:
            return {"error": "Teaching not found"}

        teaching.title = updated_teaching.title
        teaching.category = updated_teaching.category

        session.add(teaching)
        session.commit()
        session.refresh(teaching)

        return teaching
    
@app.delete("/teachings/{teaching_id}")
def delete_teaching(teaching_id: int):
    with Session(engine) as session:

        teaching = session.get(Teaching, teaching_id)

        if not teaching:
            return {"error": "Teaching not found"}

        session.delete(teaching)
        session.commit()

        return {"message": "Teaching deleted successfully"}