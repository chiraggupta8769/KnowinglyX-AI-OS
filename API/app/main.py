from fastapi import FastAPI, Query, UploadFile, File
from ollama import Client
import fitz  # PyMuPDF

# Connect to local Ollama
client = Client(host="http://127.0.0.1:11434")

app = FastAPI(
    title="KnowinglyX AI OS",
    version="0.2.0"
)


@app.get("/")
def root():
    return {
        "status": "running",
        "project": "KnowinglyX AI OS",
        "version": "0.2.0"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "ollama": True,
        "model": "qwen3:8b"
    }


@app.get("/ai")
def ai(prompt: str = Query(..., description="Enter your prompt")):

    response = client.chat(
        model="qwen3:8b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return {
        "success": True,
        "response": response["message"]["content"]
    }


@app.post("/resume/analyze")
async def analyze_resume(file: UploadFile = File(...)):

    pdf_bytes = await file.read()

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    text = ""

    for page in doc:
        text += page.get_text()

    prompt = f"""
You are an expert technical recruiter.

Analyze this resume.

Return JSON with:

1. Name
2. Email
3. Phone
4. Skills
5. Companies
6. Total Experience
7. Strengths
8. Missing Skills
9. Best Remote Roles
10. ATS Score out of 100

Resume:

{text}
"""

    response = client.chat(
        model="qwen3:8b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return {
        "success": True,
        "analysis": response["message"]["content"]
    }