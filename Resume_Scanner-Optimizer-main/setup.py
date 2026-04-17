#!/usr/bin/env python3
"""
Quick setup script for Resume ATS Scanner & Optimizer
"""

import subprocess
import sys
import os

def install_requirements():
    """Install required packages"""
    print("📦 Installing required packages...")
    try:
        # Update pip first
        print("🔄 Updating pip...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
        
        # Install requirements
        print("📥 Installing packages from requirements.txt...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Requirements installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing requirements: {e}")
        print("💡 Try installing manually:")
        print("   pip install streamlit pdfplumber python-docx spacy nltk scikit-learn pandas numpy requests beautifulsoup4 reportlab python-dotenv openai groq openrouter PyPDF2 regex")
        return False

def install_spacy_model():
    """Install spaCy English model"""
    print("🧠 Installing spaCy English model...")
    try:
        subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
        print("✅ spaCy model installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing spaCy model: {e}")
        print("💡 Try running manually: python -m spacy download en_core_web_sm")
        return False

def main():
    """Main setup function"""
    print("🚀 Resume ATS Scanner & Optimizer - Quick Setup")
    print("=" * 50)
    
    # Install requirements
    if not install_requirements():
        print("\n❌ Setup failed during package installation")
        return False
    
    # Install spaCy model
    if not install_spacy_model():
        print("\n❌ Setup failed during spaCy model installation")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Ensure you have LaTeX installed (MiKTeX, TeX Live, or MacTeX)")
    print("2. Run the application: python run.py")
    print("3. Open your browser to http://localhost:8501")
    print("\n📖 For detailed instructions, see README.md")
    
    return True

if __name__ == "__main__":
    main()