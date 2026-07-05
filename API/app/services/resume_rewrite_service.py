from app.services.ollama_service import ollama_service


class ResumeRewriteService:

    async def rewrite(self, resume_text: str, job_description: str) -> str:
        prompt = f"""You are an expert ATS resume writer and career coach.

Rewrite the resume below to be highly optimized for the job description provided.

RULES:
- Keep ALL facts accurate — do NOT invent experience, companies, or skills
- Inject relevant keywords from the job description naturally into bullet points
- Strengthen weak bullet points with action verbs and quantifiable impact
- Remove or rewrite anything irrelevant to this role
- Use clean ATS-friendly formatting:
  * Section headers in ALL CAPS (SUMMARY, EXPERIENCE, SKILLS, EDUCATION)
  * Bullet points starting with •
  * Dates in format: Month YYYY – Month YYYY
  * No tables, no columns, no graphics
- Return ONLY the rewritten resume text. No explanation, no commentary.

JOB DESCRIPTION:
{job_description}

ORIGINAL RESUME:
{resume_text}

REWRITTEN RESUME:"""

        return await ollama_service.chat(prompt=prompt, model="qwen3:8b")


resume_rewrite_service = ResumeRewriteService()
