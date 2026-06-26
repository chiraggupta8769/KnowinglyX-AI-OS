from app.services.ollama_service import ollama_service


class CoverLetterService:

    def generate(self, resume: dict, job: dict):

        prompt = f"""
You are an expert recruiter.

Using the Resume JSON and Job JSON below, write a professional one-page cover letter.

Rules:
- Personalized
- ATS friendly
- Professional tone
- No placeholders
- Ready to send

Resume:

{resume}

Job:

{job}
"""

        return ollama_service.chat(
            prompt=prompt,
            model="qwen3:8b"
        )


cover_letter_service = CoverLetterService()