"""
Legal Document Summarizer
Main application entry point with CLI interface.

This application:
- Processes legal documents (PDF, DOCX, TXT)
- Creates embeddings and vector store
- Generates legal summaries and analysis
- Answers legal questions using reasoning-based RAG
- Detects risks and renewal terms
"""

import os
import sys
import argparse
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docs_ingestion.scrape_docs import DocScraper
from docs_ingestion.clean_text import TextCleaner
from docs_ingestion.chunk_docs import DocChunker
from docs_ingestion.doc_loader import DocumentLoader
from rag_pipeline.embeddings import EmbeddingModel
from rag_pipeline.vector_store import VectorStore
from rag_pipeline.retriever import Retriever
from rag_pipeline.qa import QAEngine
from summarization.section_summary import SectionSummarizer
from summarization.executive_summary import ExecutiveSummarizer
from summarization.faq_generator import FAQGenerator


class KnowledgeAssistant:
    """Main application class for the Enterprise Knowledge Assistant."""
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize the knowledge assistant.
        
        Args:
            data_dir: Directory for data storage
        """
        self.data_dir = data_dir
        
        # Initialize components (lazy loading)
        self._scraper = None
        self._cleaner = None
        self._chunker = None
        self._doc_loader = None
        self._embedding_model = None
        self._vector_store = None
        self._retriever = None
        self._qa_engine = None
        self._section_summarizer = None
        self._executive_summarizer = None
        self._faq_generator = None
    
    @property
    def scraper(self):
        if self._scraper is None:
            self._scraper = DocScraper()
        return self._scraper
    
    @property
    def cleaner(self):
        if self._cleaner is None:
            self._cleaner = TextCleaner()
        return self._cleaner
    
    @property
    def chunker(self):
        if self._chunker is None:
            self._chunker = DocChunker(output_dir=self.data_dir)
        return self._chunker
    
    @property
    def doc_loader(self):
        if self._doc_loader is None:
            self._doc_loader = DocumentLoader()
        return self._doc_loader
    
    @property
    def embedding_model(self):
        if self._embedding_model is None:
            self._embedding_model = EmbeddingModel(data_dir=self.data_dir)
        return self._embedding_model
    
    @property
    def vector_store(self):
        if self._vector_store is None:
            self._vector_store = VectorStore(data_dir=self.data_dir)
        return self._vector_store
    
    @property
    def retriever(self):
        if self._retriever is None:
            self._retriever = Retriever(
                embedding_model=self.embedding_model,
                vector_store=self.vector_store,
                data_dir=self.data_dir
            )
        return self._retriever
    
    @property
    def qa_engine(self):
        if self._qa_engine is None:
            self._qa_engine = QAEngine(
                retriever=self.retriever,
                data_dir=self.data_dir
            )
        return self._qa_engine
    
    @property
    def section_summarizer(self):
        if self._section_summarizer is None:
            self._section_summarizer = SectionSummarizer(data_dir=self.data_dir)
        return self._section_summarizer
    
    @property
    def executive_summarizer(self):
        if self._executive_summarizer is None:
            self._executive_summarizer = ExecutiveSummarizer(data_dir=self.data_dir)
        return self._executive_summarizer
    
    @property
    def faq_generator(self):
        if self._faq_generator is None:
            self._faq_generator = FAQGenerator(data_dir=self.data_dir)
        return self._faq_generator
    
    def ingest(self, scrape: bool = True) -> dict:
        """
        Run the full ingestion pipeline.
        
        Args:
            scrape: Whether to scrape docs (False to use existing raw docs)
            
        Returns:
            Dictionary with ingestion statistics
        """
        print("\n" + "="*60)
        print("📚 DOCUMENT INGESTION PIPELINE")
        print("="*60)
        
        stats = {
            'start_time': datetime.now().isoformat(),
            'stages': {}
        }
        
        # Step 1: Scrape documents
        if scrape:
            docs = self.scraper.scrape_all()
            stats['stages']['scrape'] = {'documents': len(docs)}
        else:
            docs = self.scraper.load_raw_docs()
            print(f"📂 Loaded {len(docs)} existing raw documents")
            stats['stages']['scrape'] = {'documents': len(docs), 'cached': True}
        
        # Step 2: Clean documents
        cleaned_docs = self.cleaner.clean_all(docs)
        stats['stages']['clean'] = {'documents': len(cleaned_docs)}
        
        # Step 3: Chunk documents
        chunks = self.chunker.chunk_all(cleaned_docs)
        stats['stages']['chunk'] = {'chunks': len(chunks)}
        
        # Step 4: Create embeddings
        embeddings = self.embedding_model.embed_chunks(chunks)
        stats['stages']['embed'] = {'embeddings': len(embeddings)}
        
        # Step 5: Build vector store (ChromaDB)
        self.vector_store.build_index(embeddings, chunks)
        stats['stages']['index'] = {'vectors': self.vector_store._get_or_create_collection().count()}
        
        stats['end_time'] = datetime.now().isoformat()
        
        print("\n" + "="*60)
        print("✅ INGESTION COMPLETE")
        print("="*60)
        print(f"   Documents scraped: {stats['stages']['scrape']['documents']}")
        print(f"   Documents cleaned: {stats['stages']['clean']['documents']}")
        print(f"   Chunks created: {stats['stages']['chunk']['chunks']}")
        print(f"   Embeddings generated: {stats['stages']['embed']['embeddings']}")
        print(f"   Vectors indexed: {stats['stages']['index']['vectors']}")
        
        return stats
    
    def summarize(self, generate_executive: bool = True) -> dict:
        """
        Generate summaries of the documentation.
        
        Args:
            generate_executive: Whether to also generate executive summary
            
        Returns:
            Dictionary with summaries
        """
        print("\n" + "="*60)
        print("📝 GENERATING SUMMARIES")
        print("="*60)
        
        # Generate section summaries
        section_summaries = self.section_summarizer.summarize_all_docs()
        
        result = {
            'section_summaries': section_summaries,
            'executive_summary': None
        }
        
        # Generate executive summary
        if generate_executive and section_summaries:
            exec_summary = self.executive_summarizer.generate_executive_summary(section_summaries)
            result['executive_summary'] = exec_summary
        
        return result
    
    def generate_faqs(self, num_faqs: int = 10) -> list:
        """
        Generate FAQs from documentation.
        
        Args:
            num_faqs: Number of FAQs to generate
            
        Returns:
            List of FAQ dictionaries
        """
        print("\n" + "="*60)
        print("❓ GENERATING FAQs")
        print("="*60)
        
        faqs = self.faq_generator.generate_all_faqs(total_faqs=num_faqs)
        return faqs
    
    def ask(self, question: str) -> dict:
        """
        Answer a question using RAG.
        
        Args:
            question: User question
            
        Returns:
            Dictionary with answer and sources
        """
        return self.qa_engine.answer(question)
    
    def interactive_mode(self):
        """Run interactive Q&A mode."""
        print("\n" + "="*60)
        print("🤖 INTERACTIVE Q&A MODE")
        print("="*60)
        print("Ask questions about FastAPI documentation.")
        print("Type 'quit' or 'exit' to stop.\n")
        
        if not self.qa_engine.is_ready():
            print("⚠️ Knowledge base not ready. Please run 'ingest' first.")
            return
        
        while True:
            try:
                question = input("\n❓ Your question: ").strip()
                
                if not question:
                    continue
                
                if question.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                result = self.ask(question)
                
                print(f"\n💡 Answer:")
                print(result['answer'])
                
                if result['sources']:
                    print(f"\n📚 Sources:")
                    for source in result['sources']:
                        print(f"   - {source['title']}")
                        print(f"     {source['url']}")
                        
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
    
    def show_status(self) -> dict:
        """Show current status of the knowledge base."""
        print("\n" + "="*60)
        print("📊 KNOWLEDGE BASE STATUS")
        print("="*60)
        
        status = {
            'vector_store': False,
            'chunks': 0,
            'summaries': 0,
            'faqs': 0,
            'ready': False
        }
        
        # Check vector store
        if self.vector_store.is_initialized():
            status['vector_store'] = True
            stats = self.vector_store.get_stats()
            status['chunks'] = stats['total_chunks']
        
        # Check summaries
        summaries = self.section_summarizer.load_summaries()
        status['summaries'] = len(summaries)
        
        # Check FAQs
        faqs = self.faq_generator.load_faqs()
        status['faqs'] = len(faqs)
        
        # Overall readiness
        status['ready'] = status['vector_store'] and status['chunks'] > 0
        
        print(f"   Vector Store: {'✅ Ready' if status['vector_store'] else '❌ Not initialized'}")
        print(f"   Indexed Chunks: {status['chunks']}")
        print(f"   Section Summaries: {status['summaries']}")
        print(f"   FAQs Generated: {status['faqs']}")
        print(f"   Overall Status: {'✅ Ready for questions' if status['ready'] else '❌ Run ingest first'}")
        
        return status
    
    def export_outputs(self, output_file: str = "output.md") -> str:
        """
        Export all generated outputs to a markdown file.
        
        Args:
            output_file: Path to output file
            
        Returns:
            Path to the output file
        """
        print(f"\n📄 Exporting outputs to {output_file}...")
        
        lines = [
            "# Enterprise Knowledge Assistant - Output Report",
            f"\nGenerated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            "---\n"
        ]
        
        # Executive Summary
        exec_summary = self.executive_summarizer.load_executive_summary()
        if exec_summary:
            lines.append("## Executive Summary\n")
            lines.append(exec_summary['summary'])
            lines.append(f"\n\n**Topics Covered:** {', '.join(exec_summary['topics'])}\n")
            lines.append("\n---\n")
        
        # Section Summaries
        summaries = self.section_summarizer.load_summaries()
        if summaries:
            lines.append("## Section Summaries\n")
            for s in summaries:
                lines.append(f"### {s['title']}\n")
                lines.append(f"**Source:** {s['url']}\n")
                lines.append(f"\n{s['summary']}\n")
            lines.append("\n---\n")
        
        # FAQs
        faqs = self.faq_generator.load_faqs()
        if faqs:
            lines.append("## Frequently Asked Questions\n")
            for i, faq in enumerate(faqs, 1):
                lines.append(f"### Q{i}: {faq['question']}\n")
                lines.append(f"**A:** {faq['answer']}\n")
                lines.append(f"*Source: {faq['source']}*\n")
            lines.append("\n---\n")
        
        # Sample Q&A (if we have some example questions)
        lines.append("## Sample Questions & Answers\n")
        lines.append("*Run the assistant in interactive mode to ask your own questions.*\n")
        
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        print(f"✅ Outputs exported to {output_file}")
        return output_file


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Legal Document Summarizer - Legal Document RAG System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py upload --files contract.pdf  # Upload and index a legal document
  python main.py summarize       # Generate legal summaries
  python main.py ask "What are the termination conditions?"
  python main.py interactive     # Interactive legal Q&A mode
  python main.py status          # Show knowledge base status
  python main.py export          # Export all outputs to markdown
  python main.py ui              # Launch Streamlit web UI
        """
    )
    
    parser.add_argument(
        'command',
        choices=['ingest', 'upload', 'summarize', 'faq', 'ask', 'interactive', 'status', 'export', 'all', 'ui'],
        help='Command to run'
    )
    
    parser.add_argument(
        'query',
        nargs='?',
        default=None,
        help='Question to ask (for "ask" command)'
    )
    
    parser.add_argument(
        '--no-scrape',
        action='store_true',
        help='Skip scraping, use existing raw documents'
    )
    
    parser.add_argument(
        '--num-faqs',
        type=int,
        default=10,
        help='Number of FAQs to generate (default: 10)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='output.md',
        help='Output file for export (default: output.md)'
    )
    
    parser.add_argument(
        '--files',
        nargs='+',
        default=None,
        help='File paths to upload (for "upload" command, max 3)'
    )
    
    args = parser.parse_args()
    
    # Initialize assistant
    assistant = KnowledgeAssistant()
    
    # Execute command
    if args.command == 'ui':
        import subprocess
        print("\n🌐 Launching Streamlit UI...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", "8501"])
        return
    
    if args.command == 'upload':
        if not args.files:
            print("❌ Please provide file paths. Usage: python main.py upload --files contract.pdf agreement.docx")
            return
        if len(args.files) > 3:
            print("⚠️ Maximum 3 files at a time.")
            return
        
        from docs_ingestion.doc_loader import DocumentLoader
        loader = DocumentLoader()
        docs = loader.load_multiple(args.files)
        
        if not docs:
            print("❌ No valid documents found.")
            return
        
        cleaner = assistant.cleaner
        chunker = assistant.chunker
        
        all_chunks = []
        for doc in docs:
            cleaned = cleaner.clean_document(doc)
            cleaned['pages'] = doc.get('pages', [])
            chunks = chunker.chunk_document(cleaned)
            all_chunks.extend(chunks)
            print(f"  📄 {doc['name']}: {len(chunks)} chunks from {doc.get('total_pages', 1)} page(s)")
        
        embeddings = assistant.embedding_model.embed_chunks(all_chunks)
        assistant.vector_store.add_document_chunks(embeddings, all_chunks)
        print(f"\n✅ Indexed {len(all_chunks)} chunks from {len(docs)} document(s) into ChromaDB")
        return
    
    if args.command == 'ingest':
        assistant.ingest(scrape=not args.no_scrape)
    
    elif args.command == 'summarize':
        result = assistant.summarize()
        
        if result['executive_summary']:
            print("\n" + "="*60)
            print("📊 EXECUTIVE SUMMARY")
            print("="*60)
            print(result['executive_summary']['summary'])
    
    elif args.command == 'faq':
        faqs = assistant.generate_faqs(num_faqs=args.num_faqs)
        
        print("\n" + "="*60)
        print("❓ GENERATED FAQs")
        print("="*60)
        for i, faq in enumerate(faqs, 1):
            print(f"\nQ{i}: {faq['question']}")
            print(f"A{i}: {faq['answer']}")
            print(f"Source: {faq['source']}")
    
    elif args.command == 'ask':
        if not args.query:
            print("❌ Please provide a question. Usage: python main.py ask \"Your question here\"")
            return
        
        result = assistant.ask(args.query)
        
        print("\n" + "="*60)
        print(f"❓ Question: {args.query}")
        print("="*60)
        print(f"\n💡 Answer:\n{result['answer']}")
        
        if result['sources']:
            print(f"\n📚 Sources:")
            for source in result['sources']:
                print(f"   - {source['title']}: {source['url']}")
    
    elif args.command == 'interactive':
        assistant.interactive_mode()
    
    elif args.command == 'status':
        assistant.show_status()
    
    elif args.command == 'export':
        assistant.export_outputs(args.output)
    
    elif args.command == 'all':
        # Run full pipeline
        print("\n🚀 Running full pipeline...")
        
        # 1. Ingest
        assistant.ingest(scrape=not args.no_scrape)
        
        # 2. Generate summaries
        assistant.summarize()
        
        # 3. Generate FAQs
        assistant.generate_faqs(num_faqs=args.num_faqs)
        
        # 4. Export outputs
        assistant.export_outputs(args.output)
        
        # 5. Show status
        assistant.show_status()
        
        print("\n" + "="*60)
        print("🎉 FULL PIPELINE COMPLETE!")
        print("="*60)
        print(f"   Outputs saved to: {args.output}")
        print("   Run 'python main.py interactive' to ask questions")
        print("   Run 'python main.py ui' to launch the web interface")


if __name__ == "__main__":
    main()
