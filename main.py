from fastapi import FastAPI

app = FastAPI(title="Track Number")

@app.get("/")
def home():
    return {
        "message": "Welcome to Track Number Project"
    }