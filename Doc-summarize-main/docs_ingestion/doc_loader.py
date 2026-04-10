"""
Document Loader Module
Handles uploading and processing multiple document types (PDF, TXT, MD, DOCX).
Supports page-level extraction for legal document analysis.
"""

import os
import re
from typing import List, Dict, Optional
from pathlib import Path


class DocumentLoader:
    """Loads and processes uploaded documents with page-level indexing."""
    
    SUPPORTED_EXTENSIONS = {'.txt', '.md', '.pdf', '.docx', '.html', '.rst'}
    
    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = upload_dir
        os.makedirs(upload_dir, exist_ok=True)
    
    def load_file(self, file_path: str) -> Optional[Dict]:
        """
        Load a single file and extract text content.
        Returns document dict with name, title, content, url, and pages list.
        """
        path = Path(file_path)
        ext = path.suffix.lower()
        name = path.stem
        
        if ext not in self.SUPPORTED_EXTENSIONS:
            print(f"⚠️ Unsupported file type: {ext}")
            return None
        
        try:
            if ext == '.pdf':
                content, pages = self._load_pdf_with_pages(file_path)
            elif ext == '.docx':
                content, pages = self._load_docx_with_pages(file_path)
            elif ext in ('.txt', '.md', '.rst', '.html'):
                content = self._load_text(file_path)
                pages = [{"page_num": 1, "text": content}]
            else:
                content = self._load_text(file_path)
                pages = [{"page_num": 1, "text": content}]
            
            if not content or len(content.strip()) < 10:
                print(f"⚠️ File {name} has no extractable content")
                return None
            
            return {
                'name': name,
                'title': self._generate_title(name),
                'content': content,
                'url': f"file://{file_path}",
                'file_type': ext,
                'file_size': os.path.getsize(file_path),
                'file_path': file_path,
                'pages': pages,
                'total_pages': len(pages),
            }
        except Exception as e:
            print(f"❌ Error loading {file_path}: {e}")
            return None
    
    def load_multiple(self, file_paths: List[str]) -> List[Dict]:
        """Load multiple files at once."""
        documents = []
        for fp in file_paths:
            doc = self.load_file(fp)
            if doc:
                documents.append(doc)
        return documents
    
    def _load_text(self, file_path: str) -> str:
        """Load a plain text file."""
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        with open(file_path, 'rb') as f:
            return f.read().decode('utf-8', errors='ignore')
    
    def _load_pdf_with_pages(self, file_path: str) -> tuple:
        """Load PDF with per-page text extraction."""
        try:
            import PyPDF2
            pages = []
            text_parts = []
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for i, page in enumerate(reader.pages):
                    page_text = page.extract_text() or ""
                    pages.append({"page_num": i + 1, "text": page_text})
                    if page_text.strip():
                        text_parts.append(page_text)
            return '\n\n'.join(text_parts), pages
        except ImportError:
            print("⚠️ PyPDF2 not installed. Install with: pip install PyPDF2")
            return "", []
        except Exception as e:
            print(f"❌ PDF extraction error: {e}")
            return "", []
    
    def _load_docx_with_pages(self, file_path: str) -> tuple:
        """Load DOCX with simulated page breaks."""
        try:
            import docx
            doc = docx.Document(file_path)
            all_paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            full_text = '\n\n'.join(all_paragraphs)
            # Simulate pages by splitting every ~3000 chars
            page_size = 3000
            pages = []
            for i in range(0, len(full_text), page_size):
                chunk = full_text[i:i + page_size]
                pages.append({"page_num": len(pages) + 1, "text": chunk})
            if not pages:
                pages = [{"page_num": 1, "text": full_text}]
            return full_text, pages
        except ImportError:
            print("⚠️ python-docx not installed.")
            return "", []
        except Exception as e:
            print(f"❌ DOCX extraction error: {e}")
            return "", []
    
    def _generate_title(self, filename: str) -> str:
        """Generate a readable title from filename."""
        title = filename.replace('_', ' ').replace('-', ' ')
        title = re.sub(r'\s+', ' ', title).strip()
        return title.title()
    
    def save_uploaded(self, file_path: str) -> str:
        """Copy an uploaded file to the upload directory."""
        import shutil
        dest = os.path.join(self.upload_dir, os.path.basename(file_path))
        if file_path != dest:
            shutil.copy2(file_path, dest)
        return dest
