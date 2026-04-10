"""
Legal Risk Detector
Analyzes legal documents to detect potential risks such as unfavorable clauses,
liabilities, missing protections, and ambiguous terms.
"""

import os
import re
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()


class RiskDetector:
    """Detects legal risks in document text using LLM analysis."""

    RISK_CATEGORIES = [
        "Unfavorable Clauses",
        "Legal Liabilities",
        "Missing Protections",
        "Ambiguous Terms",
        "Penalty Provisions",
        "Unilateral Rights",
    ]

    BATCH_THRESHOLD = 10
    BATCH_SIZE = 5

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

    def _call_llm(self, prompt: str, system_prompt: str, max_tokens: int = 1024) -> str:
        if self.client is None:
            return "LLM not configured."
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=messages,
                temperature=0.2, max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"LLM error: {e}"

    def detect_risks(self, text: str, doc_name: str = "") -> Dict:
        """
        Analyze text for legal risks.
        Returns dict with risk items grouped by category and an overall risk level.
        """
        system_prompt = (
            "You are a legal risk analyst. Analyze the following legal document text and "
            "identify potential risks. For each risk found, provide:\n"
            "- Category (one of: Unfavorable Clauses, Legal Liabilities, Missing Protections, "
            "Ambiguous Terms, Penalty Provisions, Unilateral Rights)\n"
            "- Description of the risk\n"
            "- Severity (High / Medium / Low)\n"
            "- The specific clause or phrase that poses the risk\n\n"
            "If no risks are found in a category, skip it.\n"
            "At the end, provide an OVERALL RISK LEVEL (High / Medium / Low) for the document."
        )

        # Limit text to fit context window
        truncated = text[:4000]
        prompt = f"Document: {doc_name}\n\nText:\n{truncated}\n\nAnalyze this for legal risks:"

        raw = self._call_llm(prompt, system_prompt, max_tokens=1200)
        return {"doc_name": doc_name, "raw_analysis": raw, "risks": self._parse_risks(raw)}

    def detect_page_risks(self, pages: List[Dict], doc_name: str = "") -> List[Dict]:
        """Analyze pages for risks. Uses batch mode for large documents."""
        real_pages = [p for p in pages if len(p.get("text", "").strip()) >= 30]
        empty_results = []
        for p in pages:
            if len(p.get("text", "").strip()) < 30:
                empty_results.append({
                    "page_num": p["page_num"],
                    "has_risks": False,
                    "risk_summary": "Insufficient text on this page.",
                })

        if len(real_pages) <= self.BATCH_THRESHOLD:
            analysis = self._page_risks_one_by_one(real_pages, doc_name)
        else:
            analysis = self._page_risks_batched(real_pages, doc_name)

        combined = empty_results + analysis
        combined.sort(key=lambda x: x["page_num"])
        return combined

    def _page_risks_one_by_one(self, pages: List[Dict], doc_name: str) -> List[Dict]:
        """Original per-page risk analysis for small documents."""
        results = []
        for page in pages:
            page_text = page.get("text", "").strip()
            system_prompt = (
                "You are a legal risk analyst. Briefly identify any legal risks in the "
                "following page text. List each risk with its severity (High/Medium/Low). "
                "If no risks, say 'No risks detected.' Keep response under 150 words."
            )
            prompt = f"Page {page['page_num']} of {doc_name}:\n\n{page_text[:2500]}"
            raw = self._call_llm(prompt, system_prompt, max_tokens=400)
            has_risks = "no risks" not in raw.lower()
            results.append({
                "page_num": page["page_num"],
                "has_risks": has_risks,
                "risk_summary": raw,
            })
        return results

    def _page_risks_batched(self, pages: List[Dict], doc_name: str) -> List[Dict]:
        """Batch multiple pages per LLM call for large documents."""
        results = []
        for i in range(0, len(pages), self.BATCH_SIZE):
            batch = pages[i:i + self.BATCH_SIZE]
            page_nums = [p["page_num"] for p in batch]

            system_prompt = (
                "You are a legal risk analyst. For EACH page below, briefly identify legal risks "
                "with severity (High/Medium/Low). If a page has no risks, say 'No risks detected.'\n\n"
                "Use this EXACT format for every page:\n"
                "=== Page N ===\n"
                "[risk analysis or 'No risks detected.']\n"
            )

            prompt_parts = [f"Document: {doc_name}\n"]
            for p in batch:
                text = p.get("text", "").strip()[:1200]
                prompt_parts.append(f"=== Page {p['page_num']} ===\n{text}\n")
            prompt = "\n".join(prompt_parts)

            max_tok = 200 * len(batch)
            raw = self._call_llm(prompt, system_prompt, max_tokens=min(max_tok, 2000))

            parsed = self._parse_batch_risk_response(raw, page_nums)
            results.extend(parsed)

        return results

    def _parse_batch_risk_response(self, raw: str, page_nums: List[int]) -> List[Dict]:
        """Split a batched risk response into per-page results."""
        sections = re.split(r'===\s*Page\s+(\d+)\s*===', raw)
        parsed_map: Dict[int, Dict] = {}
        idx = 1
        while idx < len(sections) - 1:
            try:
                pnum = int(sections[idx])
            except ValueError:
                idx += 2
                continue
            content = sections[idx + 1].strip()
            has_risks = "no risks" not in content.lower()
            parsed_map[pnum] = {
                "page_num": pnum,
                "has_risks": has_risks,
                "risk_summary": content,
            }
            idx += 2

        results = []
        for pn in page_nums:
            if pn in parsed_map:
                results.append(parsed_map[pn])
            else:
                results.append({
                    "page_num": pn,
                    "has_risks": False,
                    "risk_summary": "Could not parse batch analysis for this page.",
                })
        return results

    def _parse_risks(self, raw: str) -> List[Dict]:
        """Parse LLM output into structured risk items."""
        risks = []
        lines = raw.strip().split("\n")
        current = {}
        for line in lines:
            line = line.strip()
            if not line or line.startswith("---"):
                if current.get("description"):
                    risks.append(current)
                    current = {}
                continue
            lower = line.lower()
            if lower.startswith("category:") or lower.startswith("- category:"):
                if current.get("description"):
                    risks.append(current)
                current = {"category": line.split(":", 1)[1].strip()}
            elif lower.startswith("description:") or lower.startswith("- description:"):
                current["description"] = line.split(":", 1)[1].strip()
            elif lower.startswith("severity:") or lower.startswith("- severity:"):
                current["severity"] = line.split(":", 1)[1].strip()
            elif lower.startswith("clause:") or lower.startswith("- clause:"):
                current["clause"] = line.split(":", 1)[1].strip()
            elif lower.startswith("overall risk level:"):
                if current.get("description"):
                    risks.append(current)
                    current = {}
        if current.get("description"):
            risks.append(current)
        return risks
