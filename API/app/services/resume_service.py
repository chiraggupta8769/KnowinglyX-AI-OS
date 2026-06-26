from app.services.ollama_service import ollama_service


class ResumeService:

    def analyze_resume(self, resume_text: str):

        prompt = f"""
You are an expert ATS recruiter.

Analyze the following resume.

Return your answer in Markdown with these sections:

# Candidate Name

# Summary

# Skills

# Experience

# Strengths

# Missing Skills

# Recommended Job Roles

# ATS Score (0-100)

Resume:

{resume_text}
"""

        return ollama_service.chat(
            prompt=prompt,
            model="qwen3:8b"
        )


resume_service = ResumeService()