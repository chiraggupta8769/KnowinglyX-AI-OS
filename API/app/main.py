from ollama import Client

client = Client(host="http://127.0.0.1:11434")
from fastapi import FastAPI

app = FastAPI(
    title="KnowinglyX AI OS",
    version="0.1.0"
)


@app.get("/")
def root():
    return {
        "status": "running",
        "message": "KnowinglyX AI OS 🚀"
    }


@app.get("/ai")
def ai():
    response = client.chat(
        model="qwen3:8b",
        messages=[
            {
                "role": "user",
                "content": "Say hello to Chirag in one sentence."
            }
        ]
    )

    return {
        "response": response["message"]["content"]
    }