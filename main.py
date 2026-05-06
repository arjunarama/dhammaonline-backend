from fastapi import FastAPI

app = FastAPI()


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