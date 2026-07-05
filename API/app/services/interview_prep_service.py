from app.services.ollama_service import ollama_service


class InterviewPrepService:

    async def generate(self, resume_text: str, job_description: str) -> str:
        prompt = f"""You are an expert technical interviewer and career coach.

Based on the resume and job description below, generate a targeted interview preparation guide.

Return ONLY valid JSON. Do NOT wrap in markdown.

Schema:
{{
  "role_summary": "One sentence: what this role needs most",
  "questions": [
    {{
      "category": "Behavioral | Technical | Situational | Role-Specific",
      "question": "The interview question",
      "why_asked": "Why recruiters ask this for this specific role",
      "coached_answer": "A strong answer template personalized to this candidate's background",
      "red_flags": "What a weak answer looks like"
    }}
  ],
  "salary_range": "Estimated range based on role and experience",
  "negotiation_tip": "One specific salary negotiation tip for this candidate"
}}

Generate 8-10 questions. Mix behavioral, technical, and role-specific.

RESUME:
{resume_text}

JOB DESCRIPTION:
{job_description}"""

        return await ollama_service.chat(prompt=prompt, model="qwen3:8b")


interview_prep_service = InterviewPrepService()
