from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "http://localhost:3000",
    "https://dhammaonline.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "message": "Dhamma Online FastAPI Backend Running"
    }


@app.get("/teachings")
def get_teachings():
    return [
        {
            "id": 1,
            "title": "Four Noble Truths",
            "category": "Wisdom"
        },
        {
            "id": 2,
            "title": "Vipassana Meditation",
            "category": "Meditation"
        },
        {
            "id": 3,
            "title": "Dependent Origination",
            "category": "Philosophy"
        }
    ]