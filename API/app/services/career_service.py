import json

from app.services.resume_service import resume_service
from app.services.job_service import job_service
from app.services.match_service import match_service
from app.services.cover_letter_service import cover_letter_service


class CareerService:

    def analyze(self, resume_text: str, job_description: str):

        result = {}

        # Resume
        resume_raw = resume_service.analyze_resume(resume_text)
        result["resume_raw"] = resume_raw

        resume = json.loads(resume_raw)
        result["resume"] = resume

        # Job
        job_raw = job_service.analyze_job(job_description)
        result["job_raw"] = job_raw

        job = json.loads(job_raw)
        result["job"] = job

        # Match
        match_raw = match_service.match(resume, job)
        result["match_raw"] = match_raw

        match = json.loads(match_raw)
        result["match"] = match

        # Cover Letter
        cover_letter = cover_letter_service.generate(
            resume,
            job
        )

        result["cover_letter"] = cover_letter

        return result


career_service = CareerService()