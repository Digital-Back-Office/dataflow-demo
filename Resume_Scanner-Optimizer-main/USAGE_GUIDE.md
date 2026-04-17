# Resume ATS Scanner & Optimizer - Usage Guide

## 🚀 Quick Start

### 1. Installation & Setup

```bash
# Clone or download the project
cd Resume_Scanner&Optimizer

# Run the quick setup script
python setup.py

# Or manually install requirements
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 2. API Keys Configuration

The project includes your API keys in the `.env` file:
- **Groq API Key**: Configured and ready to use
- **OpenRouter API Key**: Configured as backup

### 3. LaTeX Installation (Required for PDF generation)

**Windows:**
- Install [MiKTeX](https://miktex.org/download) (recommended)
- Or install [TeX Live](https://www.tug.org/texlive/)

**macOS:**
- Install [MacTeX](https://www.tug.org/mactex/)

**Linux:**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install texlive-full

# Fedora/CentOS
sudo dnf install texlive-scheme-full
```

### 4. Run the Application

```bash
# Run the application
python run.py

# Or directly with streamlit
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`

## 📋 How to Use

### Step 1: Upload Your Resume
- Supported formats: PDF, DOCX
- Maximum file size: 10MB
- Ensure resume contains clear sections

### Step 2: Provide Job Description
- **Option 1**: Paste job description text directly
- **Option 2**: Provide job posting URL (supports LinkedIn, Indeed, etc.)

### Step 3: Analyze & Review Results
- Click "🚀 Analyze Resume" button
- Wait for AI-powered analysis to complete
- Review comprehensive results

### Step 4: Generate Optimized Resume
- Click "🔄 Generate LaTeX Resume" 
- Download the optimized PDF
- Optionally download LaTeX source code

## 📊 Understanding the Results

### ATS Compatibility Score
- **Overall Score**: Combined ATS compatibility (0-100%)
- **Skill Match**: How well your skills match job requirements
- **Experience**: Relevance of your experience to the role
- **Keywords**: Keyword density and coverage
- **Format**: ATS-friendly formatting compliance

### Keyword Gap Analysis
- **Critical Missing**: Required skills not found in your resume
- **Important Missing**: Preferred skills you should consider adding
- **Weak Keywords**: Skills mentioned but with low density
- **Overused Keywords**: Terms that might appear as keyword stuffing

### AI-Powered Suggestions
- **Bullet Improvements**: Rewritten bullet points with better impact
- **Impact Scores**: Estimated effectiveness of each suggestion
- **Added Keywords**: New terms incorporated from job description
- **Reasoning**: Explanation of why changes were made

### Format Analysis
- **Critical Issues**: Problems that may prevent ATS parsing
- **Warnings**: Formatting issues that could reduce performance
- **Safe Practices**: Good formatting already in use
- **Compatibility Score**: Overall format ATS-friendliness

## 🎯 Best Practices

### Resume Content
- Use clear section headers (EXPERIENCE, EDUCATION, SKILLS)
- Include quantifiable achievements with numbers
- Use standard bullet points (- or *)
- Maintain consistent formatting throughout

### ATS Optimization
- Include keywords from job description naturally
- Avoid tables, columns, and special characters
- Use standard fonts and single-column layout
- Keep resume length to 1-2 pages maximum

### AI Suggestions
- Review AI suggestions before applying
- Ensure all suggestions are truthful and accurate
- Focus on suggestions with high impact scores
- Customize suggestions to match your voice

## 🔧 Troubleshooting

### Common Issues

**LaTeX Compilation Failed**
- Ensure LaTeX is installed correctly
- Try running `pdflatex --version` in terminal
- Install missing packages if prompted

**API Key Errors**
- Verify `.env` file contains correct API keys
- Check internet connection
- Try switching between Groq and OpenRouter

**Resume Parsing Issues**
- Ensure file is not password-protected
- Try converting PDF to text-based format
- Check if resume has clear text content

**Job Description Not Parsing**
- For URLs, ensure the job posting is publicly accessible
- Try copying and pasting text directly
- Remove any special characters from job description

### Getting Help

1. **Check the logs**: Look for error messages in the terminal
2. **Verify setup**: Run `python run.py setup` to check configuration
3. **Test components**: Try with a simple resume and job description first
4. **Check dependencies**: Ensure all packages are installed correctly

## 📱 Features Overview

### Core Features
- ✅ Resume parsing (PDF/DOCX support)
- ✅ Job description analysis (text/URL input)
- ✅ ATS compatibility scoring
- ✅ Keyword gap analysis
- ✅ AI-powered bullet improvements
- ✅ ATS formatting detection
- ✅ LaTeX resume generation
- ✅ PDF compilation and download

### AI Integration
- **Groq API**: Fast, cost-effective AI suggestions
- **OpenRouter API**: Backup AI provider with multiple models
- **Smart Prompts**: Optimized prompts for resume improvement
- **Context-Aware**: Suggestions based on specific job requirements

### Export Options
- **Optimized PDF**: ATS-friendly resume in PDF format
- **LaTeX Source**: Editable LaTeX code for further customization
- **Download Ready**: Direct download from the interface

## 🎉 Success Tips

1. **Start Simple**: Test with a basic resume first
2. **Review Suggestions**: Don't accept all AI suggestions blindly
3. **Iterate**: Make improvements and re-analyze
4. **Track Progress**: Compare scores before and after optimization
5. **Stay Authentic**: Ensure your resume still represents you accurately

## 📞 Support

If you encounter issues:
1. Check this usage guide first
2. Review the error messages carefully
3. Verify all setup requirements are met
4. Test with different files if needed

The application is designed to be intuitive and user-friendly. Most issues are resolved by ensuring proper setup and following the best practices outlined above.
