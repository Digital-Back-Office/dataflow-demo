"""
Embedding Model Module
Creates vector embeddings using local SentenceTransformers model.
No API calls needed - runs entirely on local machine.
"""

import os
import numpy as np
from typing import List, Union, Optional


class EmbeddingModel:
    """Creates embeddings using local SentenceTransformers (no API cost)."""
    
    def __init__(self, 
                 model_name: str = "all-MiniLM-L6-v2",
                 data_dir: str = "data"):
        """
        Initialize the embedding model.
        
        Args:
            model_name: Name of the SentenceTransformer model (runs locally)
            data_dir: Directory to save embeddings
        """
        self.model_name = model_name
        self.data_dir = data_dir
        self.model = None
        self.embedding_dim = 384  # Default for all-MiniLM-L6-v2

        # Higher batch size improves throughput on CPU for larger document sets.
        # Keep this moderate to avoid memory spikes on low-resource machines.
        self.batch_size = int(os.getenv("EMBED_BATCH_SIZE", "96"))

        # Ensure data directory exists
        os.makedirs(self.data_dir, exist_ok=True)
    
    def _load_model(self):
        """Lazy load the embedding model."""
        if self.model is None:
            print(f"📦 Loading local embedding model: {self.model_name}...")
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            print(f"✅ Model loaded (dimension: {self.embedding_dim})")
    
    def encode(self, texts: Union[str, List[str]], show_progress: bool = True) -> np.ndarray:
        """
        Encode texts into embeddings (locally, no API).
        
        Args:
            texts: Single text or list of texts to encode
            show_progress: Whether to show progress bar
            
        Returns:
            Numpy array of embeddings
        """
        self._load_model()
        
        if isinstance(texts, str):
            texts = [texts]
        
        print(f"🔢 Creating embeddings for {len(texts)} texts (local model)...")
        embeddings = self.model.encode(
            texts,
            show_progress_bar=show_progress,
            batch_size=self.batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,  # Pre-normalize for cosine similarity
        )
        
        return embeddings
    
    def embed_chunks(self, chunks: List[dict]) -> np.ndarray:
        """
        Create embeddings for a list of chunks.
        
        Args:
            chunks: List of chunk dictionaries with 'text' key
            
        Returns:
            Numpy array of embeddings
        """
        texts = [chunk['text'] for chunk in chunks]
        embeddings = self.encode(texts)
        
        # Save embeddings
        self._save_embeddings(embeddings)
        
        print(f"✅ Created {len(embeddings)} embeddings (local, zero API cost)")
        return embeddings
    
    def _save_embeddings(self, embeddings: np.ndarray) -> str:
        """Save embeddings to disk."""
        filepath = os.path.join(self.data_dir, 'embeddings.npy')
        np.save(filepath, embeddings)
        return filepath
    
    def load_embeddings(self) -> Optional[np.ndarray]:
        """Load previously saved embeddings."""
        filepath = os.path.join(self.data_dir, 'embeddings.npy')
        
        if not os.path.exists(filepath):
            return None
        
        return np.load(filepath)
    
    def get_query_embedding(self, query: str) -> np.ndarray:
        """
        Get embedding for a single query.
        
        Args:
            query: Query text
            
        Returns:
            Embedding vector
        """
        self._load_model()
        return self.model.encode(
            [query], 
            convert_to_numpy=True,
            normalize_embeddings=True
        )[0]
