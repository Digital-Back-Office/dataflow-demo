import os
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
import groq
import openai
from src.resume_parser import ParsedResume, ResumeSection
from src.job_parser import JobRequirements
from src.config import Config


@dataclass
class BulletSuggestion:
    original_bullet: str
    improved_bullet: str
    reason: str
    added_keywords: List[str]
    impact_score: float


@dataclass
class SectionSuggestion:
    section_name: str
    suggestions: List[BulletSuggestion]
    overall_feedback: str


class AISuggestionEngine:
    def __init__(self):
        self.config = Config()
        self.client = self._initialize_ai_client()

    def _initialize_ai_client(self):
        """Initialize AI client using environment variables (Dataflow secrets)"""

        groq_api_key = os.getenv("GROQ_API_KEY")
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")

        if self.config.PREFERRED_AI_PROVIDER == "groq":
            if not groq_api_key:
                raise ValueError("GROQ_API_KEY not found in environment variables")

            try:
                return groq.Groq(api_key=groq_api_key)
            except Exception as e:
                print(f"Error initializing Groq client: {e}")
                return None

        else:
            # Try OpenRouter first
            if openrouter_api_key:
                try:
                    return openai.OpenAI(
                        api_key=openrouter_api_key,
                        base_url="https://openrouter.ai/api/v1"
                    )
                except Exception as e:
                    print(f"Error initializing OpenRouter client: {e}")

            # Fallback to Groq
            if groq_api_key:
                try:
                    return groq.Groq(api_key=groq_api_key)
                except Exception as e:
                    print(f"Error initializing fallback Groq client: {e}")

            raise ValueError("No valid API keys found in environment variables")

    def _call_ai_api(self, prompt: str) -> str:
        """Call the appropriate AI API"""
        if not self.client:
            raise Exception("AI client not initialized")

        try:
            response = self.client.chat.completions.create(
                model=self.config.GROQ_MODEL
                if self.config.PREFERRED_AI_PROVIDER == "groq"
                else self.config.OPENROUTER_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )
            return response.choices[0].message.content

        except Exception as e:
            print(f"Error calling AI API: {e}")

            # Fallback to Groq
            groq_api_key = os.getenv("GROQ_API_KEY")

            if groq_api_key:
                try:
                    groq_client = groq.Groq(api_key=groq_api_key)
                    response = groq_client.chat.completions.create(
                        model=self.config.GROQ_MODEL,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=500
                    )
                    return response.choices[0].message.content
                except Exception as e2:
                    print(f"Fallback Groq API also failed: {e2}")

            raise Exception("All AI providers failed")

    def generate_bullet_improvements(self, resume: ParsedResume, job: JobRequirements) -> List[SectionSuggestion]:
        """Generate AI-powered bullet point improvements - FOCUS ON KEYWORDS ONLY"""
        suggestions = []

        experience_sections = [
            s for s in resume.sections
            if s.title.lower() in ['experience', 'work', 'employment']
        ]

        for section in experience_sections:
            if not section.bullet_points:
                continue

            bullet_suggestions = []

            for bullet in section.bullet_points[:3]:
                suggestion = self._improve_single_bullet(bullet, resume, job)
                if suggestion:
                    bullet_suggestions.append(suggestion)

            if bullet_suggestions:
                suggestions.append(SectionSuggestion(
                    section_name=section.title,
                    suggestions=bullet_suggestions,
                    overall_feedback="Added relevant technical keywords to improve ATS compatibility"
                ))

        return suggestions

    def _improve_single_bullet(self, bullet: str, resume: ParsedResume, job: JobRequirements) -> Optional[BulletSuggestion]:
        prompt = self._create_bullet_improvement_prompt(bullet, resume, job)

        try:
            response = self._call_ai_api(prompt)
            return self._parse_bullet_response(response, bullet)
        except Exception as e:
            print(f"Error improving bullet: {str(e)}")
            return self._create_fallback_suggestion(bullet, job)

    def _create_bullet_improvement_prompt(self, bullet: str, resume: ParsedResume, job: JobRequirements) -> str:
        required_skills_str = ', '.join(job.required_skills[:10])
        responsibilities_str = '\n'.join(job.responsibilities[:3])

        return f"""
You are an expert resume writer. Improve the bullet using ONLY keywords.

CURRENT BULLET:
{bullet}

REQUIRED SKILLS:
{required_skills_str}

RESPONSIBILITIES:
{responsibilities_str}

RULES:
- Do NOT rewrite
- Only add keywords
- Keep concise

OUTPUT JSON:
{{
    "improved_bullet": "",
    "reason": "",
    "added_keywords": [],
    "impact_score": 85
}}
"""

    def _parse_bullet_response(self, response: str, original_bullet: str) -> Optional[BulletSuggestion]:
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                return None

            data = json.loads(response[json_start:json_end])

            return BulletSuggestion(
                original_bullet=original_bullet,
                improved_bullet=data.get('improved_bullet', ''),
                reason=data.get('reason', ''),
                added_keywords=data.get('added_keywords', []),
                impact_score=float(data.get('impact_score', 0))
            )

        except Exception as e:
            print(f"Parse error: {e}")
            return None

    def _create_fallback_suggestion(self, bullet: str, job: JobRequirements) -> BulletSuggestion:
        keywords = job.required_skills[:2]

        improved = bullet + " | " + ", ".join(keywords)

        return BulletSuggestion(
            original_bullet=bullet,
            improved_bullet=improved,
            reason="Fallback keyword addition",
            added_keywords=keywords,
            impact_score=60.0
        )