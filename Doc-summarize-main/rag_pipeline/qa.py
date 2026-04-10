"""
Question Answering Module
Reasoning-based RAG Q&A for legal documents using Groq LLM.
"""

import os
from typing import List, Dict, Optional
from dotenv import load_dotenv
from .retriever import Retriever

load_dotenv()


class QAEngine:
    
    NO_INFO_MESSAGE = "The document does not contain information relevant to this query."
    
    def __init__(self, 
                 retriever: Retriever = None,
                 llm_provider: str = "groq",
                 data_dir: str = "data"):
        self.retriever = retriever or Retriever(data_dir=data_dir)
        self.llm_provider = llm_provider
        self.client = None
        self._init_llm()
    
    def _init_llm(self):
        if self.llm_provider == "groq":
            api_key = os.getenv("GROQ_API_KEY")
            if api_key:
                from groq import Groq
                self.client = Groq(api_key=api_key)
                self.model = "llama-3.1-8b-instant"
        elif self.llm_provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)
                self.model = "gpt-3.5-turbo"
    
    def _call_llm(self, prompt: str, system_prompt: str = None, max_tokens: int = 1024) -> str:
        if self.client is None:
            return "LLM not configured. Please set API key in .env file."
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=messages,
                temperature=0.3, max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"LLM error: {str(e)}"
    
    def answer(self, 
               question: str, 
               top_k: int = 4,
               include_sources: bool = True,
               doc_filter: str = None) -> Dict:
        """
        Answer a question using reasoning-based RAG.
        The model reasons through retrieved legal context before answering.
        """
        chunks = self.retriever.retrieve(question, top_k=top_k, doc_filter=doc_filter)
        
        if not chunks:
            return {
                'question': question,
                'answer': self.NO_INFO_MESSAGE,
                'sources': [],
                'has_context': False,
            }
        
        context = self.retriever.format_context(chunks, include_sources=True)
        
        system_prompt = (
            "You are a legal document analyst. When answering questions:\n"
            "1. REASON through the relevant clauses step-by-step\n"
            "2. Cite specific sections/pages from the context\n"
            "3. Highlight any legal implications or risks related to the question\n"
            "4. Provide a clear, well-structured answer\n"
            "5. If the context is insufficient, state what is missing\n\n"
            "Answer ONLY from the provided context. Be precise and legally aware."
        )
        
        prompt = f"""Context from legal document:
{context}

Legal Question: {question}

Provide a reasoning-based answer. First analyze the relevant clauses, then give your conclusion:"""
        
        answer = self._call_llm(prompt, system_prompt, max_tokens=900)
        sources = self.retriever.get_sources(chunks)
        
        return {
            'question': question,
            'answer': answer,
            'sources': sources,
            'has_context': True,
            'num_chunks_used': len(chunks),
            'pages_referenced': sorted(set(c.get('page_num', 0) for c in chunks if c.get('page_num'))),
        }
    
    def answer_with_context(self, question: str, context: str) -> str:
        """Answer a question with provided context (no retrieval)."""
        system_prompt = (
            "You are a legal document analyst. "
            "Answer based on the provided context with legal reasoning. Be concise."
        )
        prompt = f"""Context:\n{context}\n\nQ: {question}\nA:"""
        return self._call_llm(prompt, system_prompt, max_tokens=600)
    
    def is_ready(self) -> bool:
        return (self.client is not None and 
                self.retriever.vector_store.is_initialized())
