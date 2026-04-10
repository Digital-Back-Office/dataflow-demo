"""
Section Summary Module
Generates summaries for individual documentation sections.
"""

import os
import json
from typing import List, Dict, Optional
from dotenv import load_dotenv
from tqdm import tqdm


# Load environment variables
load_dotenv()


class SectionSummarizer:
    """Generates summaries for documentation sections using LLM."""
    
    def __init__(self, 
                 llm_provider: str = "groq",
                 data_dir: str = "data"):
        """
        Initialize the summarizer.
        
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
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"⚠️ LLM error: {str(e)}"
    
    def summarize_section(self, text: str, title: str = None) -> str:
        """
        Summarize a single documentation section.
        
        Args:
            text: Section text to summarize
            title: Optional section title for context
            
        Returns:
            Summary string
        """
        system_prompt = """You are a legal document summarizer.
Create concise, accurate summaries of legal documents.
Focus on key clauses, obligations, rights, and legal implications.
Keep summaries under 100 words."""
        
        title_context = f" titled '{title}'" if title else ""
        
        prompt = f"""Summarize the following legal document section{title_context}. Focus on key legal terms, obligations, rights, and implications:

{text}

Provide a clear, concise legal summary (under 100 words) that captures the main clauses and key information."""
        
        return self._call_llm(prompt, system_prompt)
    
    def summarize_document(self, doc: Dict) -> Dict:
        """
        Summarize a full document.
        
        Args:
            doc: Document dictionary with 'content' and 'title'
            
        Returns:
            Dictionary with original doc info and summary
        """
        summary = self.summarize_section(
            doc['content'][:3000],  # Limit content length
            doc.get('title', 'Untitled')
        )
        
        return {
            'name': doc.get('name', 'unknown'),
            'title': doc.get('title', 'Untitled'),
            'url': doc.get('url', ''),
            'summary': summary
        }
    
    def summarize_all_docs(self, documents: List[Dict] = None) -> List[Dict]:
        """
        Summarize all documents.
        
        Args:
            documents: List of document dicts. Loads from disk if None.
            
        Returns:
            List of summary dictionaries
        """
        # Load from disk if not provided
        if documents is None:
            documents = self._load_cleaned_docs()
        
        if not documents:
            print("⚠️ No documents to summarize")
            return []
        
        print(f"\n📝 Summarizing {len(documents)} documents...")
        summaries = []
        
        for doc in tqdm(documents, desc="Summarizing"):
            summary = self.summarize_document(doc)
            summaries.append(summary)
        
        # Save summaries
        self._save_summaries(summaries)
        
        print(f"✅ Generated {len(summaries)} section summaries")
        return summaries
    
    def _load_cleaned_docs(self) -> List[Dict]:
        """Load cleaned documents from disk."""
        processed_dir = "docs/processed"
        documents = []
        
        if not os.path.exists(processed_dir):
            return documents
        
        for filename in os.listdir(processed_dir):
            if filename.endswith('_cleaned.txt'):
                filepath = os.path.join(processed_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                lines = content.split('\n')
                title = lines[0].replace('Title: ', '') if lines else 'Untitled'
                url = lines[1].replace('Source: ', '') if len(lines) > 1 else ''
                main_content = '\n'.join(lines[4:]) if len(lines) > 4 else content
                
                documents.append({
                    'name': filename.replace('_cleaned.txt', ''),
                    'title': title,
                    'url': url,
                    'content': main_content
                })
        
        return documents
    
    def _save_summaries(self, summaries: List[Dict]) -> str:
        """Save summaries to JSON file."""
        filepath = os.path.join(self.data_dir, 'section_summaries.json')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summaries, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def load_summaries(self) -> List[Dict]:
        """Load previously generated summaries."""
        filepath = os.path.join(self.data_dir, 'section_summaries.json')
        
        if not os.path.exists(filepath):
            return []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)


if __name__ == "__main__":
    # Test the summarizer
    summarizer = SectionSummarizer()
    summaries = summarizer.summarize_all_docs()
    
    print("\nSection Summaries:")
    for s in summaries:
        print(f"\n📄 {s['title']}")
        print(f"   {s['summary']}")
