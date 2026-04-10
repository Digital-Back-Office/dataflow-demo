"""
Page Importance Analyzer
Scores each page of a legal document for importance based on legal content relevance.
"""

import os
import re
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()


class PageAnalyzer:
    """Analyzes and scores each page of a document for legal importance."""

    BATCH_THRESHOLD = 10   # pages <= this → one-by-one; above → batched
    BATCH_SIZE = 5           # pages per LLM call in batch mode

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

    def _call_llm(self, prompt: str, system_prompt: str, max_tokens: int = 300) -> str:
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

    def analyze_pages(self, pages: List[Dict], doc_name: str = "") -> List[Dict]:
        """
        Analyze each page and assign an importance score and summary.
        Uses one-by-one mode for small docs, batch mode for large docs.
        """
        # Filter out near-empty pages early
        real_pages = [p for p in pages if len(p.get("text", "").strip()) >= 20]
        empty_results = []
        for p in pages:
            if len(p.get("text", "").strip()) < 20:
                empty_results.append({
                    "page_num": p.get("page_num", 0),
                    "importance": "Low",
                    "score": 1,
                    "summary": "Minimal content on this page.",
                    "key_topics": [],
                })

        if len(real_pages) <= self.BATCH_THRESHOLD:
            analysis = self._analyze_one_by_one(real_pages, doc_name)
        else:
            analysis = self._analyze_batched(real_pages, doc_name)

        combined = empty_results + analysis
        combined.sort(key=lambda x: x["page_num"])
        return combined

    def _analyze_one_by_one(self, pages: List[Dict], doc_name: str) -> List[Dict]:
        """Original per-page analysis for small documents."""
        results = []
        for page in pages:
            page_text = page.get("text", "").strip()
            page_num = page.get("page_num", 0)
            system_prompt = (
                "You are a legal document analyst. For the given page text:\n"
                "1. Rate importance as: Critical / High / Medium / Low\n"
                "2. Give a numeric score from 1-10\n"
                "3. Provide a one-sentence summary\n"
                "4. List key legal topics found (comma-separated)\n\n"
                "Response format (exactly):\n"
                "Importance: [level]\n"
                "Score: [1-10]\n"
                "Summary: [one sentence]\n"
                "Topics: [comma-separated list]"
            )
            prompt = f"Page {page_num} of '{doc_name}':\n\n{page_text[:2000]}"
            raw = self._call_llm(prompt, system_prompt, max_tokens=200)
            results.append(self._parse_page_analysis(raw, page_num))
        return results

    def _analyze_batched(self, pages: List[Dict], doc_name: str) -> List[Dict]:
        """Batch multiple pages per LLM call for large documents."""
        results = []
        for i in range(0, len(pages), self.BATCH_SIZE):
            batch = pages[i:i + self.BATCH_SIZE]
            page_nums = [p.get("page_num", 0) for p in batch]

            system_prompt = (
                "You are a legal document analyst. For EACH page below, provide:\n"
                "1. Importance: Critical / High / Medium / Low\n"
                "2. Score: 1-10\n"
                "3. Summary: one sentence\n"
                "4. Topics: comma-separated list\n\n"
                "Use this EXACT format for every page:\n"
                "=== Page N ===\n"
                "Importance: [level]\n"
                "Score: [1-10]\n"
                "Summary: [one sentence]\n"
                "Topics: [list]\n"
            )

            prompt_parts = [f"Document: {doc_name}\n"]
            for p in batch:
                text = p.get("text", "").strip()[:1200]
                prompt_parts.append(f"=== Page {p.get('page_num', 0)} ===\n{text}\n")
            prompt = "\n".join(prompt_parts)

            max_tok = 200 * len(batch)
            raw = self._call_llm(prompt, system_prompt, max_tokens=min(max_tok, 2000))

            parsed = self._parse_batch_response(raw, page_nums)
            results.extend(parsed)

        return results

    def _parse_batch_response(self, raw: str, page_nums: List[int]) -> List[Dict]:
        """Split a batched LLM response into per-page results."""
        sections = re.split(r'===\s*Page\s+(\d+)\s*===', raw)
        parsed_map: Dict[int, Dict] = {}
        # sections: ['', '1', 'content', '2', 'content', ...]
        idx = 1
        while idx < len(sections) - 1:
            try:
                pnum = int(sections[idx])
            except ValueError:
                idx += 2
                continue
            content = sections[idx + 1]
            parsed_map[pnum] = self._parse_page_analysis(content, pnum)
            idx += 2

        results = []
        for pn in page_nums:
            if pn in parsed_map:
                results.append(parsed_map[pn])
            else:
                results.append({
                    "page_num": pn,
                    "importance": "Medium",
                    "score": 5,
                    "summary": "Could not parse batch analysis for this page.",
                    "key_topics": [],
                })
        return results

    def _parse_page_analysis(self, raw: str, page_num: int) -> Dict:
        """Parse LLM page analysis output."""
        result = {
            "page_num": page_num,
            "importance": "Medium",
            "score": 5,
            "summary": "",
            "key_topics": [],
        }
        for line in raw.strip().split("\n"):
            line = line.strip()
            lower = line.lower()
            if lower.startswith("importance:"):
                val = line.split(":", 1)[1].strip()
                result["importance"] = val
            elif lower.startswith("score:"):
                try:
                    result["score"] = int(line.split(":", 1)[1].strip().split("/")[0].strip())
                except (ValueError, IndexError):
                    pass
            elif lower.startswith("summary:"):
                result["summary"] = line.split(":", 1)[1].strip()
            elif lower.startswith("topics:"):
                topics = line.split(":", 1)[1].strip()
                result["key_topics"] = [t.strip() for t in topics.split(",") if t.strip()]
        if not result["summary"]:
            result["summary"] = raw[:150]
        return result
