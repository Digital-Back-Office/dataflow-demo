"""
Document Chunker Module
Splits cleaned documents into smaller chunks for embedding and retrieval.
"""

import os
import json
import re
from typing import List, Dict, Optional
from tqdm import tqdm


class DocChunker:
    """Splits documents into chunks suitable for RAG."""
    
    def __init__(self, 
                 chunk_size: int = 500, 
                 chunk_overlap: int = 50,
                 input_dir: str = "docs/processed",
                 output_dir: str = "data"):
        """
        Initialize the chunker.
        
        Args:
            chunk_size: Target number of words per chunk
            chunk_overlap: Number of words to overlap between chunks
            input_dir: Directory containing cleaned documents
            output_dir: Directory to save chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.input_dir = input_dir
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def chunk_text(self, text: str, metadata: Dict = None) -> List[Dict]:
        """
        Split text into overlapping chunks.
        
        Args:
            text: Text to chunk
            metadata: Metadata to attach to each chunk (source, title, etc.)
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        if metadata is None:
            metadata = {}
        
        # Split into words
        words = text.split()
        
        if len(words) <= self.chunk_size:
            # Document is small enough to be a single chunk
            return [{
                'chunk_id': 0,
                'text': text,
                'word_count': len(words),
                **metadata
            }]
        
        chunks = []
        start = 0
        chunk_id = 0
        
        while start < len(words):
            # Calculate end position
            end = start + self.chunk_size
            
            # Get chunk words
            chunk_words = words[start:end]
            chunk_text = ' '.join(chunk_words)
            
            # Try to break at sentence boundary if possible
            if end < len(words):
                # Look for sentence ending near the end
                last_period = chunk_text.rfind('. ')
                last_question = chunk_text.rfind('? ')
                last_exclaim = chunk_text.rfind('! ')
                
                best_break = max(last_period, last_question, last_exclaim)
                
                if best_break > len(chunk_text) * 0.7:  # Only if break is in last 30%
                    chunk_text = chunk_text[:best_break + 1]
                    # Recalculate word count
                    chunk_words = chunk_text.split()
            
            chunks.append({
                'chunk_id': chunk_id,
                'text': chunk_text.strip(),
                'word_count': len(chunk_words),
                **metadata
            })
            
            # Move start position with overlap
            start = start + self.chunk_size - self.chunk_overlap
            chunk_id += 1
        
        return chunks
    
    def chunk_document(self, doc: Dict) -> List[Dict]:
        """
        Chunk a single document, preserving page-level metadata.
        If the document has 'pages', chunks are created per-page with page_num metadata.
        """
        pages = doc.get('pages', [])
        
        if pages and len(pages) > 1:
            # Page-aware chunking: chunk each page separately
            all_chunks = []
            for page in pages:
                page_text = page.get('text', '').strip()
                if not page_text:
                    continue
                metadata = {
                    'source': doc.get('url', ''),
                    'title': doc.get('title', 'Untitled'),
                    'doc_name': doc.get('name', 'unknown'),
                    'page_num': page.get('page_num', 0),
                }
                chunks = self.chunk_text(page_text, metadata)
                all_chunks.extend(chunks)
            return all_chunks
        
        # Fallback: no page info
        metadata = {
            'source': doc.get('url', ''),
            'title': doc.get('title', 'Untitled'),
            'doc_name': doc.get('name', 'unknown'),
            'page_num': 1,
        }
        return self.chunk_text(doc['content'], metadata)
    
    def chunk_all(self, documents: List[Dict] = None) -> List[Dict]:
        """
        Chunk all documents.
        
        Args:
            documents: List of document dicts. If None, loads from input_dir.
            
        Returns:
            List of all chunks from all documents
        """
        # Load from disk if not provided
        if documents is None:
            documents = self._load_cleaned_docs()
        
        if not documents:
            print("⚠️ No documents to chunk")
            return []
        
        print(f"\n✂️ Chunking {len(documents)} documents...")
        all_chunks = []
        
        for doc in tqdm(documents, desc="Chunking"):
            chunks = self.chunk_document(doc)
            all_chunks.extend(chunks)
        
        # Add global chunk IDs
        for i, chunk in enumerate(all_chunks):
            chunk['global_id'] = i
        
        # Save chunks
        self._save_chunks(all_chunks)
        
        print(f"✅ Created {len(all_chunks)} chunks from {len(documents)} documents")
        print(f"   📊 Average chunk size: {sum(c['word_count'] for c in all_chunks) / len(all_chunks):.0f} words")
        
        return all_chunks
    
    def _load_cleaned_docs(self) -> List[Dict]:
        """Load cleaned documents from input directory."""
        documents = []
        
        if not os.path.exists(self.input_dir):
            return documents
        
        for filename in os.listdir(self.input_dir):
            if filename.endswith('_cleaned.txt'):
                filepath = os.path.join(self.input_dir, filename)
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
    
    def _save_chunks(self, chunks: List[Dict]) -> str:
        """Save chunks to JSON file."""
        filepath = os.path.join(self.output_dir, 'chunks.json')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def load_chunks(self) -> List[Dict]:
        """Load previously created chunks from disk."""
        filepath = os.path.join(self.output_dir, 'chunks.json')
        
        if not os.path.exists(filepath):
            return []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)


if __name__ == "__main__":
    # Test the chunker
    chunker = DocChunker()
    chunks = chunker.chunk_all()
    print(f"\nCreated {len(chunks)} chunks")
    if chunks:
        print(f"\nSample chunk:")
        print(f"  Title: {chunks[0]['title']}")
        print(f"  Words: {chunks[0]['word_count']}")
        print(f"  Text: {chunks[0]['text'][:200]}...")
