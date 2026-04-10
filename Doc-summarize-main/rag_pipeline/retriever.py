"""
Retriever Module
Retrieves relevant document chunks with context optimization for Groq free tier.
"""

import os
import re
from typing import List, Dict, Optional
from .embeddings import EmbeddingModel
from .vector_store import VectorStore


class Retriever:
    """Retrieves and optimizes context chunks for LLM consumption."""
    
    # Groq free tier limits: ~6000 tokens input for llama-3.1-8b-instant
    MAX_CONTEXT_WORDS = 1500  # ~2000 tokens, leaves room for prompt + response
    MAX_CHUNK_WORDS = 400     # Per-chunk limit
    
    def __init__(self, 
                 embedding_model: EmbeddingModel = None,
                 vector_store: VectorStore = None,
                 data_dir: str = "data"):
        self.data_dir = data_dir
        self.embedding_model = embedding_model or EmbeddingModel(data_dir=data_dir)
        self.vector_store = vector_store or VectorStore(data_dir=data_dir)
    
    def retrieve(self, 
                 query: str, 
                 top_k: int = 3,
                 score_threshold: float = 0.0,
                 doc_filter: str = None) -> List[Dict]:
        """
        Retrieve relevant chunks for a query, optionally filtered by document.
        
        Args:
            query: User query
            top_k: Number of chunks to retrieve
            score_threshold: Minimum similarity score (0-1)
            doc_filter: If set, only search within this document
            
        Returns:
            List of relevant chunks with metadata and scores
        """
        if not self.vector_store.is_initialized():
            print("⚠️ Vector store not initialized. Please run ingestion first.")
            return []
        
        # Get query embedding
        query_embedding = self.embedding_model.get_query_embedding(query)
        
        # Search (optionally filtered by document)
        if doc_filter:
            results = self.vector_store.search_by_document(
                query_embedding, doc_filter, top_k=top_k, score_threshold=score_threshold
            )
        else:
            results = self.vector_store.search(
                query_embedding, top_k=top_k, score_threshold=score_threshold
            )
        
        return results 
    
    def _truncate_chunk(self, text: str, max_words: int = None) -> str:
        """Truncate a chunk to max_words, breaking at sentence boundary."""
        max_words = max_words or self.MAX_CHUNK_WORDS
        words = text.split()
        if len(words) <= max_words:
            return text
        
        truncated = ' '.join(words[:max_words])
        # Try to break at last sentence
        last_period = truncated.rfind('. ')
        if last_period > len(truncated) * 0.6:
            truncated = truncated[:last_period + 1]
        return truncated
    
    def _deduplicate_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """Remove near-duplicate chunks based on text overlap."""
        if len(chunks) <= 1:
            return chunks
        
        unique = [chunks[0]]
        for chunk in chunks[1:]:
            is_dup = False
            chunk_words = set(chunk['text'].lower().split())
            
            for existing in unique:
                existing_words = set(existing['text'].lower().split())
                # If >70% word overlap, skip
                if len(chunk_words) > 0:
                    overlap = len(chunk_words & existing_words) / len(chunk_words)
                    if overlap > 0.7:
                        is_dup = True
                        break
            
            if not is_dup:
                unique.append(chunk)
        
        return unique
    
    def _compress_text(self, text: str) -> str:
        """Remove filler/repetitive content to save tokens."""
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        # Remove common filler phrases
        fillers = [
            r'As mentioned (earlier|above|before),?\s*',
            r'It is important to note that\s*',
            r'Please note that\s*',
            r'In this section,?\s*we will\s*',
            r'Let\'s (?:take a )?look at\s*',
        ]
        for filler in fillers:
            text = re.sub(filler, '', text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def format_context(self, chunks: List[Dict], include_sources: bool = True) -> str:
        """
        Format retrieved chunks into an optimized context string for Groq.
        Deduplicates, truncates, and compresses to minimize token usage.
        
        Args:
            chunks: List of retrieved chunks
            include_sources: Whether to include source info
            
        Returns:
            Optimized context string
        """
        if not chunks:
            return ""
        
        # Step 1: Deduplicate
        chunks = self._deduplicate_chunks(chunks)
        
        # Step 2: Build context parts with truncation
        context_parts = []
        total_words = 0
        
        for i, chunk in enumerate(chunks, 1):
            text = self._compress_text(chunk['text'])
            text = self._truncate_chunk(text)
            
            word_count = len(text.split())
            if total_words + word_count > self.MAX_CONTEXT_WORDS:
                # Truncate this chunk to fit remaining budget
                remaining = self.MAX_CONTEXT_WORDS - total_words
                if remaining < 50:
                    break
                text = self._truncate_chunk(text, remaining)
            
            if include_sources:
                title = chunk.get('title', 'Untitled')
                doc_name = chunk.get('doc_name', '')
                page = chunk.get('page_num', '')
                header = f"[{title} | {doc_name}"
                if page:
                    header += f" | Page {page}"
                header += "]"
                context_parts.append(f"{header}\n{text}")
            else:
                context_parts.append(f"[Section {i}]\n{text}")
            
            total_words += len(text.split())
        
        return "\n\n".join(context_parts)
    
    def get_sources(self, chunks: List[Dict]) -> List[Dict]:
        """Extract source information from chunks."""
        sources = []
        seen = set()
        
        for chunk in chunks:
            source_url = chunk.get('source', '')
            doc_name = chunk.get('doc_name', '')
            key = source_url or doc_name
            
            if key and key not in seen:
                seen.add(key)
                sources.append({
                    'title': chunk.get('title', 'Untitled'),
                    'url': source_url,
                    'doc_name': doc_name
                })
        
        return sources
