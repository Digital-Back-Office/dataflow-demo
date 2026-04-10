"""
FAQ Generator Module
Generates frequently asked questions from documentation.
"""

import os
import json
from typing import List, Dict, Optional
from dotenv import load_dotenv
from tqdm import tqdm


# Load environment variables
load_dotenv()


class FAQGenerator:
    """Generates FAQs from documentation using LLM."""
    
    def __init__(self, 
                 llm_provider: str = "groq",
                 data_dir: str = "data"):
        """
        Initialize the FAQ generator.
        
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
                temperature=0.4,
                max_tokens=1500
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"⚠️ LLM error: {str(e)}"
    
    def generate_faqs_from_section(self, 
                                    text: str, 
                                    title: str = None,
                                    num_faqs: int = 3) -> List[Dict]:
        """
        Generate FAQs from a single documentation section.
        
        Args:
            text: Section text
            title: Section title for context
            num_faqs: Number of FAQs to generate
            
        Returns:
            List of FAQ dictionaries with question, answer, source
        """
        system_prompt = """You are a technical documentation expert.
Generate clear, practical FAQ questions that developers commonly ask.
Answers must be grounded in the provided documentation.
Format: Return each Q&A on separate lines."""
        
        title_context = f" about '{title}'" if title else ""
        
        prompt = f"""From the following documentation{title_context}, generate {num_faqs} frequently asked developer questions with concise answers.

Documentation:
{text[:2500]}

Generate exactly {num_faqs} Q&A pairs in this format:
Q1: [question]
A1: [answer]

Q2: [question]
A2: [answer]

etc.

Ensure answers are STRICTLY based on the documentation provided."""
        
        response = self._call_llm(prompt, system_prompt)
        
        # Parse the response
        faqs = self._parse_faqs(response, title)
        return faqs
    
    def _parse_faqs(self, response: str, source_title: str = None) -> List[Dict]:
        """Parse FAQ response into structured format."""
        faqs = []
        lines = response.strip().split('\n')
        
        current_q = None
        current_a = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for question
            if line.startswith('Q') and ':' in line:
                # Save previous Q&A if exists
                if current_q and current_a:
                    faqs.append({
                        'question': current_q,
                        'answer': current_a,
                        'source': source_title or 'Documentation'
                    })
                
                # Extract new question
                current_q = line.split(':', 1)[1].strip()
                current_a = None
            
            # Check for answer
            elif line.startswith('A') and ':' in line:
                current_a = line.split(':', 1)[1].strip()
        
        # Don't forget last Q&A
        if current_q and current_a:
            faqs.append({
                'question': current_q,
                'answer': current_a,
                'source': source_title or 'Documentation'
            })
        
        return faqs
    
    def generate_all_faqs(self, 
                          documents: List[Dict] = None,
                          faqs_per_doc: int = 2,
                          total_faqs: int = 10) -> List[Dict]:
        """
        Generate FAQs from all documents.
        
        Args:
            documents: List of document dicts. Loads from disk if None.
            faqs_per_doc: FAQs to generate per document
            total_faqs: Maximum total FAQs to return
            
        Returns:
            List of all FAQ dictionaries
        """
        # Load from disk if not provided
        if documents is None:
            documents = self._load_cleaned_docs()
        
        if not documents:
            print("⚠️ No documents to generate FAQs from")
            return []
        
        print(f"\n❓ Generating FAQs from {len(documents)} documents...")
        all_faqs = []
        
        for doc in tqdm(documents, desc="Generating FAQs"):
            faqs = self.generate_faqs_from_section(
                doc['content'],
                doc.get('title', 'Untitled'),
                num_faqs=faqs_per_doc
            )
            all_faqs.extend(faqs)
            
            # Stop if we have enough
            if len(all_faqs) >= total_faqs:
                break
        
        # Limit to total_faqs
        all_faqs = all_faqs[:total_faqs]
        
        # Save FAQs
        self._save_faqs(all_faqs)
        
        print(f"✅ Generated {len(all_faqs)} FAQs")
        return all_faqs
    
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
    
    def _save_faqs(self, faqs: List[Dict]) -> str:
        """Save FAQs to JSON file."""
        filepath = os.path.join(self.data_dir, 'faqs.json')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(faqs, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def load_faqs(self) -> List[Dict]:
        """Load previously generated FAQs."""
        filepath = os.path.join(self.data_dir, 'faqs.json')
        
        if not os.path.exists(filepath):
            return []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)


if __name__ == "__main__":
    # Test the FAQ generator
    generator = FAQGenerator()
    faqs = generator.generate_all_faqs()
    
    print("\n" + "="*60)
    print("GENERATED FAQs")
    print("="*60)
    for i, faq in enumerate(faqs, 1):
        print(f"\nQ{i}: {faq['question']}")
        print(f"A{i}: {faq['answer']}")
        print(f"Source: {faq['source']}")
