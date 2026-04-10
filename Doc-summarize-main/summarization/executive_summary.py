"""
Executive Summary Module
Generates high-level summary of all documentation.
"""

import os
import json
from typing import List, Dict, Optional
from dotenv import load_dotenv


# Load environment variables
load_dotenv()


class ExecutiveSummarizer:
    """Generates executive summary from all documentation sections."""
    
    def __init__(self, 
                 llm_provider: str = "groq",
                 data_dir: str = "data"):
        """
        Initialize the executive summarizer.
        
        Args:
            llm_provider: LLM provider ('groq' or 'openai')
            data_dir: Directory for data storage
        """
        self.llm_provider = llm_provider
        self.data_dir = data_dir
        self.client = None
        self._init_llm()
        
        os.makedirs(data_dir, exist_ok=True)
    
    def _init_llm(self):
        """Initialize the LLM client."""
        if self.llm_provider == "groq":
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                from groq import Groq
                self.client = Groq(api_key=api_key)
                self.model = "llama-3.1-8b-instant"
            else:
                print("⚠️ GROQ_API_KEY not found. Set it in .env file.")
        elif self.llm_provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)
                self.model = "gpt-3.5-turbo"
            else:
                print("⚠️ OPENAI_API_KEY not found. Set it in .env file.")
    
    def _call_llm(self, prompt: str, system_prompt: str = None) -> str:
        """Call the LLM with a prompt."""
        if self.client is None:
            return "⚠️ LLM not configured. Please set API key in .env file."
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
                max_tokens=800
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"⚠️ LLM error: {str(e)}"
    
    def generate_executive_summary(self, section_summaries: List[Dict] = None) -> Dict:
        """
        Generate an executive summary from all section summaries.
        
        Args:
            section_summaries: List of section summary dicts. Loads from disk if None.
            
        Returns:
            Dictionary with executive summary and metadata
        """
        # Load from disk if not provided
        if section_summaries is None:
            section_summaries = self._load_section_summaries()
        
        if not section_summaries:
            return {
                'summary': "No section summaries available to generate executive summary.",
                'num_sections': 0,
                'topics': []
            }
        
        print(f"\n📊 Generating executive summary from {len(section_summaries)} sections...")
        
        # Combine section summaries
        combined = "\n\n".join([
            f"**{s['title']}**: {s['summary']}"
            for s in section_summaries
        ])
        
        # Extract topics
        topics = [s['title'] for s in section_summaries]
        
        system_prompt = """You are a legal document expert.
Create executive summaries of legal documents that give readers a clear overview.
Focus on key obligations, rights, risks, and important dates.
Be professional and precise."""
        
        prompt = f"""Based on the following legal document section summaries, create a comprehensive executive summary (250-300 words) that:

1. Identifies the type of legal document (contract, agreement, policy, etc.)
2. Highlights key obligations and rights of the parties
3. Summarizes important dates, deadlines, and conditions
4. Notes any significant risks or concerns

Section Summaries:
{combined}

Generate a well-structured legal executive summary:"""
        
        executive_summary = self._call_llm(prompt, system_prompt)
        
        result = {
            'summary': executive_summary,
            'num_sections': len(section_summaries),
            'topics': topics
        }
        
        # Save to disk
        self._save_executive_summary(result)
        
        print("✅ Executive summary generated")
        return result
    
    def _load_section_summaries(self) -> List[Dict]:
        """Load section summaries from disk."""
        filepath = os.path.join(self.data_dir, 'section_summaries.json')
        
        if not os.path.exists(filepath):
            return []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_executive_summary(self, summary: Dict) -> str:
        """Save executive summary to disk."""
        filepath = os.path.join(self.data_dir, 'executive_summary.json')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def load_executive_summary(self) -> Optional[Dict]:
        """Load previously generated executive summary."""
        filepath = os.path.join(self.data_dir, 'executive_summary.json')
        
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)


if __name__ == "__main__":
    # Test the executive summarizer
    summarizer = ExecutiveSummarizer()
    result = summarizer.generate_executive_summary()
    
    print("\n" + "="*60)
    print("EXECUTIVE SUMMARY")
    print("="*60)
    print(result['summary'])
    print(f"\nTopics covered: {', '.join(result['topics'])}")
