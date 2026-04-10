"""
Text Cleaner Module
Cleans scraped documentation by removing noise and formatting issues.
"""

import os
import re
import json
from typing import List, Dict
from tqdm import tqdm


class TextCleaner:
    """Cleans and preprocesses scraped documentation text."""
    
    # Patterns to remove (navigation, common UI elements, etc.)
    NOISE_PATTERNS = [
        r'Skip to content',
        r'Table of contents',
        r'Previous\s+Next',
        r'Edit on GitHub',
        r'Made with Material for MkDocs',
        r'Copyright ©.*',
        r'Back to top',
        r'Toggle navigation',
        r'Search\s*$',
        r'^\s*Menu\s*$',
        r'^\s*Close\s*$',
        r'^\d+\.\d+\.\d+$',  # Version numbers alone on a line
    ]
    
    def __init__(self, input_dir: str = "docs/raw", output_dir: str = "docs/processed"):
        """
        Initialize the cleaner.
        
        Args:
            input_dir: Directory containing raw documents
            output_dir: Directory to save cleaned documents
        """
        self.input_dir = input_dir
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Compile regex patterns
        self.noise_regex = [re.compile(p, re.IGNORECASE | re.MULTILINE) 
                          for p in self.NOISE_PATTERNS]
    
    def clean_text(self, text: str) -> str:
        """
        Clean a single text document.
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned text
        """
        # Remove noise patterns
        for pattern in self.noise_regex:
            text = pattern.sub('', text)
        
        # Split into lines for line-by-line cleaning
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Strip whitespace
            line = line.strip()
            
            # Skip very short lines (likely nav elements)
            if len(line) < 10:
                # Keep if it looks like a header or important
                if not re.match(r'^[A-Z][a-z]+\s*$', line):
                    if len(line) < 3:
                        continue
            
            # Skip lines that are just symbols or numbers
            if re.match(r'^[\d\W]+$', line):
                continue
            
            # Skip repeated words (e.g., "FastAPI FastAPI FastAPI")
            words = line.split()
            if len(words) > 2 and len(set(words)) == 1:
                continue
            
            cleaned_lines.append(line)
        
        # Join lines and clean up extra whitespace
        text = '\n'.join(cleaned_lines)
        
        # Remove multiple consecutive newlines (keep max 2)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove multiple consecutive spaces
        text = re.sub(r' {2,}', ' ', text)
        
        return text.strip()
    
    def clean_document(self, doc: Dict) -> Dict:
        """
        Clean a document dictionary.
        
        Args:
            doc: Document with 'content', 'title', 'url', 'name' keys
            
        Returns:
            Document with cleaned content
        """
        cleaned_content = self.clean_text(doc['content'])
        
        return {
            'name': doc['name'],
            'title': doc['title'],
            'url': doc['url'],
            'content': cleaned_content,
            'original_length': len(doc['content']),
            'cleaned_length': len(cleaned_content)
        }
    
    def clean_all(self, documents: List[Dict] = None) -> List[Dict]:
        """
        Clean all documents.
        
        Args:
            documents: List of document dicts. If None, loads from input_dir.
            
        Returns:
            List of cleaned documents
        """
        # Load from disk if not provided
        if documents is None:
            documents = self._load_raw_docs()
        
        if not documents:
            print("⚠️ No documents to clean")
            return []
        
        print(f"\n🧹 Cleaning {len(documents)} documents...")
        cleaned_docs = []
        
        for doc in tqdm(documents, desc="Cleaning"):
            cleaned = self.clean_document(doc)
            cleaned_docs.append(cleaned)
            self._save_cleaned(cleaned)
        
        # Calculate stats
        total_original = sum(d['original_length'] for d in cleaned_docs)
        total_cleaned = sum(d['cleaned_length'] for d in cleaned_docs)
        reduction = (1 - total_cleaned / total_original) * 100 if total_original > 0 else 0
        
        print(f"✅ Cleaned {len(cleaned_docs)} documents")
        print(f"   📊 Reduced size by {reduction:.1f}% ({total_original:,} → {total_cleaned:,} chars)")
        
        return cleaned_docs
    
    def _load_raw_docs(self) -> List[Dict]:
        """Load raw documents from input directory."""
        documents = []
        
        if not os.path.exists(self.input_dir):
            return documents
        
        for filename in os.listdir(self.input_dir):
            if filename.endswith('.txt'):
                filepath = os.path.join(self.input_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse the saved format
                lines = content.split('\n')
                title = lines[0].replace('Title: ', '') if lines else 'Untitled'
                url = lines[1].replace('Source: ', '') if len(lines) > 1 else ''
                main_content = '\n'.join(lines[4:]) if len(lines) > 4 else content
                
                documents.append({
                    'name': filename.replace('.txt', ''),
                    'title': title,
                    'url': url,
                    'content': main_content
                })
        
        return documents
    
    def _save_cleaned(self, doc: Dict) -> str:
        """Save cleaned document to file."""
        filename = f"{doc['name']}_cleaned.txt"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"Title: {doc['title']}\n")
            f.write(f"Source: {doc['url']}\n")
            f.write(f"{'='*60}\n\n")
            f.write(doc['content'])
        
        return filepath
    
    def load_cleaned_docs(self) -> List[Dict]:
        """Load previously cleaned documents from disk."""
        documents = []
        
        if not os.path.exists(self.output_dir):
            return documents
        
        for filename in os.listdir(self.output_dir):
            if filename.endswith('_cleaned.txt'):
                filepath = os.path.join(self.output_dir, filename)
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


if __name__ == "__main__":
    # Test the cleaner
    cleaner = TextCleaner()
    cleaned_docs = cleaner.clean_all()
    print(f"\nCleaned {len(cleaned_docs)} documents")
