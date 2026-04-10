"""
Renewal Detector
Identifies renewal dates, expiry clauses, and renewal policies in legal documents.
"""

import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()


class RenewalDetector:
    """Detects contract renewal dates, expiry clauses, and renewal terms."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.client = None
        self.model = "llama-3.1-8b-instant"
        self._init_llm()

    def _init_llm(self):
        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            from groq import Groq
            self.client = Groq(api_key=api_key)

    def _call_llm(self, prompt: str, system_prompt: str, max_tokens: int = 800) -> str:
        if self.client is None:
            return "LLM not configured."
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=messages,
                temperature=0.1, max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"LLM error: {e}"

    def detect_renewals(self, text: str, doc_name: str = "") -> Dict:
        """
        Analyze document text for renewal/expiry information.
        Returns structured renewal data.
        """
        system_prompt = (
            "You are a legal contract analyst specializing in renewal and expiry terms. "
            "Analyze the document and extract:\n"
            "1. Contract/policy start date (if mentioned)\n"
            "2. Contract/policy end date or expiry date\n"
            "3. Renewal terms (auto-renewal, manual renewal, notice period)\n"
            "4. Termination conditions\n"
            "5. Key renewal deadlines or notice periods\n\n"
            "Format each finding clearly. If a field is not found, state 'Not specified'. "
            "Keep response concise and structured."
        )

        truncated = text[:4000]
        prompt = f"Document: {doc_name}\n\nText:\n{truncated}\n\nExtract renewal and expiry information:"

        raw = self._call_llm(prompt, system_prompt, max_tokens=800)
        return {
            "doc_name": doc_name,
            "raw_analysis": raw,
            "renewals": self._parse_renewals(raw),
        }

    def _parse_renewals(self, raw: str) -> List[Dict]:
        """Parse LLM output into structured renewal items."""
        items = []
        lines = raw.strip().split("\n")
        current = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            lower = line.lower()
            for key_label, key in [
                ("start date", "start_date"),
                ("end date", "end_date"),
                ("expiry", "expiry_date"),
                ("renewal term", "renewal_terms"),
                ("auto-renewal", "auto_renewal"),
                ("termination", "termination"),
                ("notice period", "notice_period"),
                ("deadline", "deadline"),
            ]:
                if key_label in lower:
                    val = line.split(":", 1)[1].strip() if ":" in line else line
                    current[key] = val
        if current:
            items.append(current)
        return items
