"""
Vector Store Module
ChromaDB-based vector storage and similarity search with local embeddings.
"""

import os
import json
import numpy as np
from typing import List, Dict, Tuple, Optional


class VectorStore:
    """ChromaDB vector store for persistent similarity search."""
    
    def __init__(self, 
                 dimension: int = 384,
                 data_dir: str = "data",
                 collection_name: str = "doc_chunks"):
        self.dimension = dimension
        self.data_dir = data_dir
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        
        os.makedirs(data_dir, exist_ok=True)
        self._init_chroma()
    
    def _init_chroma(self):
        """Initialize ChromaDB client with persistent storage."""
        import chromadb
        
        persist_dir = os.path.join(self.data_dir, "chroma_db")
        os.makedirs(persist_dir, exist_ok=True)
        self.client = chromadb.PersistentClient(path=persist_dir)
    
    def _get_or_create_collection(self):
        """Get or create the ChromaDB collection."""
        if self.collection is None:
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        return self.collection
    
    def build_index(self, embeddings: np.ndarray, chunks: List[Dict]) -> None:
        """
        Build ChromaDB index from embeddings and chunks.
        """
        print(f"🏗️ Building ChromaDB index with {len(embeddings)} vectors...")
        
        # Delete existing collection and recreate
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        
        self.collection = self.client.create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        ids = [str(i) for i in range(len(chunks))]
        documents = [chunk.get('text', '') for chunk in chunks]
        metadatas = []
        for chunk in chunks:
            meta = {
                'source': str(chunk.get('source', '')),
                'title': str(chunk.get('title', 'Untitled')),
                'doc_name': str(chunk.get('doc_name', 'unknown')),
                'chunk_id': str(chunk.get('chunk_id', 0)),
                'word_count': int(chunk.get('word_count', 0)),
                'page_num': int(chunk.get('page_num', 1)),
            }
            metadatas.append(meta)
        
        embeddings_list = embeddings.astype('float32').tolist()
        
        # Add in batches (ChromaDB limit)
        batch_size = 5000
        for start in range(0, len(ids), batch_size):
            end = min(start + batch_size, len(ids))
            self.collection.add(
                ids=ids[start:end],
                embeddings=embeddings_list[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
            )
        
        # Save chunks JSON for compatibility
        chunks_path = os.path.join(self.data_dir, 'chunks_indexed.json')
        with open(chunks_path, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)
        
        print(f"✅ ChromaDB index built with {self.collection.count()} vectors")
    
    def add_document_chunks(self, embeddings: np.ndarray, chunks: List[Dict], start_id: int = 0) -> None:
        """
        Add chunks from a new document without rebuilding the entire index.
        """
        collection = self._get_or_create_collection()
        current_count = collection.count()
        
        ids = [str(current_count + i) for i in range(len(chunks))]
        documents = [chunk.get('text', '') for chunk in chunks]
        metadatas = []
        for chunk in chunks:
            meta = {
                'source': str(chunk.get('source', '')),
                'title': str(chunk.get('title', 'Untitled')),
                'doc_name': str(chunk.get('doc_name', 'unknown')),
                'chunk_id': str(chunk.get('chunk_id', 0)),
                'word_count': int(chunk.get('word_count', 0)),
                'page_num': int(chunk.get('page_num', 1)),
            }
            metadatas.append(meta)
        
        embeddings_list = embeddings.astype('float32').tolist()
        
        batch_size = 5000
        for start in range(0, len(ids), batch_size):
            end = min(start + batch_size, len(ids))
            collection.add(
                ids=ids[start:end],
                embeddings=embeddings_list[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
            )
    
    def search(self, 
               query_embedding: np.ndarray, 
               top_k: int = 3,
               score_threshold: float = 0.0) -> List[Dict]:
        """Search for similar chunks across all documents."""
        collection = self._get_or_create_collection()
        
        if collection.count() == 0:
            return []
        
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)
        
        query_list = query_embedding.astype('float32').tolist()
        
        results = collection.query(
            query_embeddings=query_list,
            n_results=min(top_k, collection.count()),
            include=["documents", "metadatas", "distances"]
        )
        
        output = []
        if results and results['ids'] and results['ids'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                distance = results['distances'][0][i]
                score = 1.0 - distance  # cosine distance → similarity
                
                if score >= score_threshold:
                    chunk = {
                        'text': results['documents'][0][i],
                        'score': float(score),
                    }
                    if results['metadatas'] and results['metadatas'][0]:
                        meta = results['metadatas'][0][i]
                        chunk['source'] = meta.get('source', '')
                        chunk['title'] = meta.get('title', 'Untitled')
                        chunk['doc_name'] = meta.get('doc_name', 'unknown')
                        chunk['page_num'] = meta.get('page_num', 1)
                    output.append(chunk)
        
        return output
    
    def search_by_document(self, 
                           query_embedding: np.ndarray,
                           doc_name: str,
                           top_k: int = 3,
                           score_threshold: float = 0.0) -> List[Dict]:
        """Search within a specific document."""
        collection = self._get_or_create_collection()
        
        if collection.count() == 0:
            return []
        
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)
        
        query_list = query_embedding.astype('float32').tolist()
        
        try:
            results = collection.query(
                query_embeddings=query_list,
                n_results=min(top_k * 2, collection.count()),
                where={"doc_name": doc_name},
                include=["documents", "metadatas", "distances"]
            )
        except Exception:
            return self.search(query_embedding, top_k, score_threshold)
        
        output = []
        if results and results['ids'] and results['ids'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                distance = results['distances'][0][i]
                score = 1.0 - distance
                
                if score >= score_threshold:
                    chunk = {
                        'text': results['documents'][0][i],
                        'score': float(score),
                    }
                    if results['metadatas'] and results['metadatas'][0]:
                        meta = results['metadatas'][0][i]
                        chunk['source'] = meta.get('source', '')
                        chunk['title'] = meta.get('title', 'Untitled')
                        chunk['doc_name'] = meta.get('doc_name', 'unknown')
                        chunk['page_num'] = meta.get('page_num', 1)
                    output.append(chunk)
        
        return output[:top_k]
    
    def get_all_documents(self) -> List[str]:
        """Get list of all unique document names in the store."""
        collection = self._get_or_create_collection()
        
        if collection.count() == 0:
            return []
        
        all_data = collection.get(include=["metadatas"])
        doc_names = set()
        if all_data and all_data['metadatas']:
            for meta in all_data['metadatas']:
                doc_names.add(meta.get('doc_name', 'unknown'))
        
        return sorted(list(doc_names))
    
    def delete_document(self, doc_name: str) -> int:
        """Delete all chunks for a specific document."""
        collection = self._get_or_create_collection()
        
        if collection.count() == 0:
            return 0
        
        results = collection.get(
            where={"doc_name": doc_name},
            include=[]
        )
        
        if results and results['ids']:
            count = len(results['ids'])
            collection.delete(ids=results['ids'])
            return count
        
        return 0
    
    def is_initialized(self) -> bool:
        """Check if the store has data."""
        try:
            collection = self._get_or_create_collection()
            return collection.count() > 0
        except Exception:
            return False
    
    def get_stats(self) -> Dict:
        """Get store statistics."""
        collection = self._get_or_create_collection()
        count = collection.count()
        docs = self.get_all_documents()
        
        return {
            'total_chunks': count,
            'documents': docs,
            'num_documents': len(docs)
        }
