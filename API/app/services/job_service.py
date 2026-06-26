from app.services.ollama_service import ollama_service


class JobService:

    def analyze_job(self, job_description: str):

        prompt = f"""
You are an expert technical recruiter.

Analyze this Job Description.

Return ONLY valid JSON.

Schema:

{{
    "job_title":"",
    "company":"",
    "required_skills":[],
    "preferred_skills":[],
    "experience_required":"",
    "responsibilities":[],
    "keywords":[]
}}

Job Description:

{job_description}
"""

        return ollama_service.chat(
            prompt=prompt,
            model="qwen3:8b"
        )


job_service = JobService()