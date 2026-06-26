from app.services.ollama_service import ollama_service


class MatchService:

    def match(self, resume_json: dict, job_json: dict):

        prompt = f"""
You are an ATS recruiter.

Compare the Resume JSON with the Job JSON.

Return ONLY valid JSON.

Schema:

{{
    "match_score": 0,
    "matched_skills": [],
    "missing_skills": [],
    "resume_improvements": [],
    "interview_questions": []
}}

Resume:

{resume_json}

Job:

{job_json}
"""

        return ollama_service.chat(
            prompt=prompt,
            model="qwen3:8b"
        )


match_service = MatchService()