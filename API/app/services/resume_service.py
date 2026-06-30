from app.services.ollama_service import ollama_service


class ResumeService:

    async def analyze_resume(self, resume_text: str) -> str:
        prompt = f"""
You are an expert ATS recruiter.

Return ONLY valid JSON.

Do NOT return markdown.

Do NOT wrap JSON inside ```.

Use this exact schema:

{{
    "candidate": {{
        "name": "",
        "email": "",
        "phone": ""
    }},
    "summary": "",
    "skills": [],
    "companies": [],
    "experience_years": 0,
    "strengths": [],
    "missing_skills": [],
    "recommended_roles": [],
    "ats_score": 0
}}

Resume:

{resume_text}
"""
        return await ollama_service.chat(prompt=prompt, model="qwen3:8b")


resume_service = ResumeService()
