"""
Document Scraper Module
Scrapes FastAPI documentation pages and saves raw content.
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from tqdm import tqdm


class DocScraper:
    """Scrapes documentation from FastAPI website."""
    
    # FastAPI tutorial pages to scrape
    FASTAPI_URLS = [
        ("first-steps", "https://fastapi.tiangolo.com/tutorial/first-steps/"),
        ("path-parameters", "https://fastapi.tiangolo.com/tutorial/path-params/"),
        ("query-parameters", "https://fastapi.tiangolo.com/tutorial/query-params/"),
        ("request-body", "https://fastapi.tiangolo.com/tutorial/body/"),
        ("query-params-validation", "https://fastapi.tiangolo.com/tutorial/query-params-str-validations/"),
        ("path-params-validation", "https://fastapi.tiangolo.com/tutorial/path-params-numeric-validations/"),
        ("body-multiple-params", "https://fastapi.tiangolo.com/tutorial/body-multiple-params/"),
        ("response-model", "https://fastapi.tiangolo.com/tutorial/response-model/"),
        ("extra-models", "https://fastapi.tiangolo.com/tutorial/extra-models/"),
        ("response-status-code", "https://fastapi.tiangolo.com/tutorial/response-status-code/"),
    ]
    
    def __init__(self, output_dir: str = "docs/raw"):
        """
        Initialize the scraper.
        
        Args:
            output_dir: Directory to save scraped documents
        """
        self.output_dir = output_dir
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        os.makedirs(output_dir, exist_ok=True)
    
    def scrape_page(self, url: str) -> Optional[Dict]:
        """
        Scrape a single documentation page.
        
        Args:
            url: URL of the page to scrape
            
        Returns:
            Dictionary with title, content, and url, or None if failed
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Extract title
            title = soup.find('h1')
            title_text = title.get_text(strip=True) if title else "Untitled"
            
            # Extract main content - FastAPI uses md-content class
            content_div = soup.find('article', class_='md-content')
            if not content_div:
                content_div = soup.find('div', class_='md-content')
            if not content_div:
                content_div = soup.find('main')
            
            if content_div:
                # Remove navigation, scripts, and other unwanted elements
                for element in content_div.find_all(['nav', 'script', 'style', 'footer', 'header']):
                    element.decompose()
                
                # Get text content
                content = content_div.get_text(separator='\n', strip=True)
            else:
                # Fallback: get body text
                content = soup.get_text(separator='\n', strip=True)
            
            return {
                'title': title_text,
                'content': content,
                'url': url
            }
            
        except requests.RequestException as e:
            print(f"Error scraping {url}: {e}")
            return None
    
    def scrape_all(self, urls: List[tuple] = None, delay: float = 1.0) -> List[Dict]:
        """
        Scrape all documentation pages.
        
        Args:
            urls: List of (name, url) tuples to scrape. Uses default if None.
            delay: Delay between requests in seconds
            
        Returns:
            List of scraped documents
        """
        if urls is None:
            urls = self.FASTAPI_URLS
        
        documents = []
        print(f"\n📥 Scraping {len(urls)} documentation pages...")
        
        for name, url in tqdm(urls, desc="Scraping"):
            doc = self.scrape_page(url)
            if doc:
                doc['name'] = name
                documents.append(doc)
                self._save_raw(name, doc)
            time.sleep(delay)  # Be polite to the server
        
        print(f"✅ Successfully scraped {len(documents)} pages")
        return documents
    
    def _save_raw(self, name: str, doc: Dict) -> str:
        """
        Save raw scraped content to file.
        
        Args:
            name: Document name (used for filename)
            doc: Document dictionary
            
        Returns:
            Path to saved file
        """
        filename = f"{name}.txt"
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"Title: {doc['title']}\n")
            f.write(f"Source: {doc['url']}\n")
            f.write(f"{'='*60}\n\n")
            f.write(doc['content'])
        
        return filepath
    
    def load_raw_docs(self) -> List[Dict]:
        """
        Load previously scraped raw documents from disk.
        
        Returns:
            List of document dictionaries
        """
        documents = []
        
        if not os.path.exists(self.output_dir):
            return documents
        
        for filename in os.listdir(self.output_dir):
            if filename.endswith('.txt'):
                filepath = os.path.join(self.output_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse the saved format
                lines = content.split('\n')
                title = lines[0].replace('Title: ', '') if lines else 'Untitled'
                url = lines[1].replace('Source: ', '') if len(lines) > 1 else ''
                
                # Skip header and get content
                main_content = '\n'.join(lines[4:]) if len(lines) > 4 else content
                
                documents.append({
                    'name': filename.replace('.txt', ''),
                    'title': title,
                    'url': url,
                    'content': main_content
                })
        
        return documents


if __name__ == "__main__":
    # Test the scraper
    scraper = DocScraper()
    docs = scraper.scrape_all()
    print(f"\nScraped {len(docs)} documents")
    for doc in docs:
        print(f"  - {doc['title']} ({len(doc['content'])} chars)")
