"""
CareerService — chains 4 services with fail-fast error handling.
Any stage failure returns immediately with the failing stage name and error.
No partial results are stitched together.
"""
from __future__ import annotations

import json
import logging

from app.services.resume_service import resume_service
from app.services.job_service import job_service
from app.services.match_service import match_service
from app.services.cover_letter_service import cover_letter_service
from app.services.ollama_service import OllamaError

logger = logging.getLogger(__name__)


class CareerServiceError(Exception):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage
        self.message = message


class CareerService:

    async def analyze(self, resume_text: str, job_description: str) -> dict:
        """
        Run the full career analysis pipeline.
        Returns a dict with all stage results, or raises CareerServiceError
        at the first failing stage.
        """
        result: dict = {}

        # Stage 1 — Resume
        try:
            resume_raw = await resume_service.analyze_resume(resume_text)
        except OllamaError as exc:
            raise CareerServiceError("resume", f"Ollama error: {exc}") from exc
        except Exception as exc:
            raise CareerServiceError("resume", str(exc)) from exc

        try:
            resume = json.loads(resume_raw)
        except json.JSONDecodeError as exc:
            raise CareerServiceError(
                "resume",
                f"Model returned non-JSON: {resume_raw[:200]}",
            ) from exc

        result["resume_raw"] = resume_raw
        result["resume"] = resume

        # Stage 2 — Job
        try:
            job_raw = await job_service.analyze_job(job_description)
        except OllamaError as exc:
            raise CareerServiceError("job", f"Ollama error: {exc}") from exc
        except Exception as exc:
            raise CareerServiceError("job", str(exc)) from exc

        try:
            job = json.loads(job_raw)
        except json.JSONDecodeError as exc:
            raise CareerServiceError(
                "job",
                f"Model returned non-JSON: {job_raw[:200]}",
            ) from exc

        result["job_raw"] = job_raw
        result["job"] = job

        # Stage 3 — Match
        try:
            match_raw = await match_service.match(resume, job)
        except OllamaError as exc:
            raise CareerServiceError("match", f"Ollama error: {exc}") from exc
        except Exception as exc:
            raise CareerServiceError("match", str(exc)) from exc

        try:
            match = json.loads(match_raw)
        except json.JSONDecodeError as exc:
            raise CareerServiceError(
                "match",
                f"Model returned non-JSON: {match_raw[:200]}",
            ) from exc

        result["match_raw"] = match_raw
        result["match"] = match

        # Stage 4 — Cover Letter
        try:
            cover_letter = await cover_letter_service.generate(resume, job)
        except OllamaError as exc:
            raise CareerServiceError("cover_letter", f"Ollama error: {exc}") from exc
        except Exception as exc:
            raise CareerServiceError("cover_letter", str(exc)) from exc

        result["cover_letter"] = cover_letter

        return result


career_service = CareerService()
