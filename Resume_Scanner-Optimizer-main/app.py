import streamlit as st
import tempfile
import os
import sys
import logging
import re
from pathlib import Path
import time
from typing import Dict, List
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Add current directory to Python path to fix src module imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import our modules
from src.resume_parser import ResumeParser
from src.job_parser import JobDescriptionParser
from src.ats_scorer import ATSScorer
from src.keyword_analyzer import KeywordAnalyzer
from src.ai_suggestions import AISuggestionEngine
from src.format_detector import ATSFormatDetector


# Configure page
st.set_page_config(
    page_title="Resume ATS Scanner & Optimizer",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'parsed_resume' not in st.session_state:
    st.session_state.parsed_resume = None
if 'parsed_job' not in st.session_state:
    st.session_state.parsed_job = None
if 'ats_score' not in st.session_state:
    st.session_state.ats_score = None
if 'keyword_analysis' not in st.session_state:
    st.session_state.keyword_analysis = None
if 'ai_suggestions' not in st.session_state:
    st.session_state.ai_suggestions = None
if 'format_analysis' not in st.session_state:
    st.session_state.format_analysis = None

def clean_keywords(keywords):
    """Clean and filter keywords to remove nonsense phrases"""
    cleaned = []
    stopwords = {'the', 'a', 'an', 'for', 'with', 'to', 'of', 'and', 'in', 'on', 'at', 'by', 
                 'from', 'or', 'but', 'not', 'be', 'are', 'is', 'was', 'were', 'been', 'have',
                 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
                 'software', 'engineer', 'developer', 'candidate', 'experience', 'skills',
                 'develop', 'document', 'comply', 'work', 'team', 'company'}
    
    # Technical skills and technologies that should be kept
    technical_keywords = {
        'python', 'java', 'javascript', 'c++', 'c#', 'go', 'rust', 'scala', 'ruby',
        'react', 'angular', 'vue', 'node', 'django', 'flask', 'spring', 'express',
        'sql', 'nosql', 'mongodb', 'postgresql', 'mysql', 'oracle', 'cassandra',
        'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform', 'jenkins',
        'git', 'linux', 'ubuntu', 'windows', 'macos', 'unix',
        'html', 'css', 'typescript', 'webpack', 'babel', 'npm', 'yarn',
        'tensorflow', 'pytorch', 'keras', 'scikit-learn', 'pandas', 'numpy',
        'rest', 'graphql', 'api', 'microservices', 'serverless', 'devops',
        'agile', 'scrum', 'kanban', 'jira', 'confluence', 'slack'
    }
    
    for keyword in keywords:
        if not keyword or not isinstance(keyword, str):
            continue
            
        keyword_lower = keyword.lower().strip()
        
        # Skip if it's a stopword or too short/long
        if (keyword_lower in stopwords or 
            len(keyword_lower) < 2 or 
            len(keyword_lower) > 50 or
            'software engineer' in keyword_lower or
            'ideal candidates' in keyword_lower):
            continue
        
        # Keep if it's a known technical keyword
        if keyword_lower in technical_keywords:
            cleaned.append(keyword)
        # Keep if it looks like a technical term (contains tech indicators)
        elif any(tech in keyword_lower for tech in ['python', 'java', 'script', 'sql', 'aws', 'docker', 'git', 'react', 'node']):
            cleaned.append(keyword)
    
    return list(set(cleaned))  # Remove duplicates

def categorize_keywords(keywords):
    """Categorize keywords into logical groups"""
    categories = {
        'Programming Languages': [],
        'Frameworks & Libraries': [],
        'Tools & Platforms': []
    }
    
    programming_langs = {'python', 'java', 'javascript', 'c++', 'c#', 'go', 'rust', 'scala', 'ruby', 'typescript', 'html', 'css'}
    frameworks = {'react', 'angular', 'vue', 'django', 'flask', 'spring', 'express', 'tensorflow', 'pytorch', 'keras', 'scikit-learn'}
    tools = {'git', 'linux', 'ubuntu', 'npm', 'yarn', 'webpack', 'babel', 'jira', 'confluence', 'slack', 'aws', 'docker', 'kubernetes'}
    
    for keyword in keywords:
        keyword_lower = keyword.lower()
        
        if keyword_lower in programming_langs:
            categories['Programming Languages'].append(keyword)
        elif keyword_lower in frameworks:
            categories['Frameworks & Libraries'].append(keyword)
        else:
            categories['Tools & Platforms'].append(keyword)
    
    # Remove empty categories
    return {k: v for k, v in categories.items() if v}

def get_recommendations(enhanced_analysis):
    """Generate actionable recommendations based on enhanced analysis"""
    recommendations = []
    
    # Action verb recommendations
    if enhanced_analysis.get('action_verb_risks', {}).get('issues', []):
        recommendations.append({
            'issue': 'Weak Action Verbs',
            'explanation': 'Your resume uses weak action verbs that don\'t effectively '
                         'showcase your contributions and achievements. Strong action verbs '
                         'demonstrate initiative and impact.',
            'action': 'Rewrite bullet points using strong action verbs:\n'
                     '- Replace "Responsible for" with "Developed" or "Managed"\n'
                     '- Replace "Worked on" with "Implemented" or "Created"\n'
                     '- Replace "Helped with" with "Assisted" or "Contributed to"\n'
                     '- Add measurable outcomes: "increased efficiency by 35%"'
        })
    
    # Keyword recommendations
    if enhanced_analysis.get('keyword_gaps', {}).get('missing_critical'):
        recommendations.append({
            'issue': 'Missing Critical Keywords',
            'explanation': 'Your resume is missing several keywords that are specifically '
                         'mentioned in the job description. ATS systems scan for these exact '
                         'keywords when matching candidates to job requirements. Missing keywords '
                         'can significantly lower your ATS score.',
            'action': 'Integrate these missing keywords naturally into your resume:\n'
                     '- Add them to your Skills section\n'
                     '- Include them in Experience bullet points\n'
                     '- Mention them in Project descriptions\n'
                     '- Use them in Professional Summary if relevant'
        })
    
    # Format recommendations
    format_issues = enhanced_analysis.get('format_risks', {}).get('issues', [])
    if format_issues:
        recommendations.append({
            'issue': 'ATS Format Risks Detected',
            'explanation': 'Your resume contains formatting elements that can cause ATS '
                         'systems to fail or misinterpret your information. ATS systems work best '
                         'with clean, simple formatting without complex layouts or special characters.',
            'action': 'Fix these formatting issues:\n'
                     '- Remove tables and convert to bullet points\n'
                     '- Replace non-standard bullets with standard ones (- or *)\n'
                     '- Remove all emojis and unicode symbols\n'
                     '- Use consistent date format (e.g., Jan 2024 – Mar 2024)\n'
                     '- Ensure single-column layout'
        })
    
    return recommendations


def inject_global_styles():
    """Inject global CSS styles used across the app."""
    st.markdown("""
    <style>
    .metric-card {
        background-color: #f8f9fa;
        padding: 1.2rem;
        border-radius: 0.5rem;
        border-left: 4px solid #2c3e50;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .keyword-chip {
        display: inline-block;
        background-color: #e8f4f8;
        color: #2c3e50;
        padding: 0.3rem 0.8rem;
        margin: 0.15rem;
        border-radius: 0.3rem;
        font-size: 0.85rem;
        font-weight: 500;
        border: 1px solid #d1e7dd;
    }
    .missing-chip {
        display: inline-block;
        background-color: #f8e8e8;
        color: #721c24;
        padding: 0.3rem 0.8rem;
        margin: 0.15rem;
        border-radius: 0.3rem;
        font-size: 0.85rem;
        font-weight: 500;
        border: 1px solid #f5c6cb;
    }
    .compact-list {
        line-height: 1.4;
        margin: 0.3rem 0;
        color: #495057;
    }
    .section-header {
        background-color: #2c3e50;
        color: white;
        padding: 0.6rem 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0 0.5rem 0;
        font-weight: 600;
        font-size: 1.1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    /* Sidebar buttons (Analyze Resume, etc) */
    div[data-testid="stSidebar"] button,
    div[data-testid="stSidebar"] .stButton > button {
        background-color: #2c3e50 !important;
        color: white !important;
        border: none !important;
        border-radius: 0.75rem !important;
        padding: 0.8rem 1.2rem !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
        width: 100% !important;
    }
    div[data-testid="stSidebar"] button:hover,
    div[data-testid="stSidebar"] .stButton > button:hover {
        background-color: #34495e !important;
    }
    /* Ensure Streamlit primary/secondary buttons match theme (including Analyze button) */
    button[kind="primary"],
    button[kind="secondary"],
    .stButton button,
    .stButton button:focus {
        background-color: #2c3e50 !important;
        color: white !important;
        border: none !important;
    }
    /* Radio button color override - more specific */
    .stRadio input[type="radio"],
    .stRadio div[role="radiogroup"] input[type="radio"],
    input[type="radio"][name*="job_input_type"],
    [data-testid="stSidebar"] input[type="radio"] {
        accent-color: #1f4e79 !important;
        border: 1px solid #1f4e79 !important;
        box-shadow: none !important;
        background-color: white !important;
    }
    .stRadio input[type="radio"]:checked,
    .stRadio div[role="radiogroup"] input[type="radio"]:checked,
    input[type="radio"][name*="job_input_type"]:checked,
    [data-testid="stSidebar"] input[type="radio"]:checked {
        accent-color: #1f4e79 !important;
        border-color: #1f4e79 !important;
        background-color: white !important;
    }
    [data-testid="stSidebar"] input[type="radio"] + label,
    [data-testid="stSidebar"] input[type="radio"]:checked + label {
        color: #1f4e79 !important;
        font-weight: 600 !important;
    }
    [data-testid="stSidebar"] input[type="radio"]:checked ~ span,
    [data-testid="stSidebar"] input[type="radio"]:checked + span {
        color: #1f4e79 !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] [aria-checked="true"] {
        color: #1f4e79 !important;
    }
    .stRadio input[type="radio"]:checked + label,
    .stRadio div[role="radiogroup"] input[type="radio"]:checked + label,
    input[type="radio"][name*="job_input_type"]:checked + label {
        color: #1f4e79 !important;
        font-weight: 700 !important;
    }

    .match-assessments-title {
        font-size: 2.1rem;
        font-weight: 800;
        color: #06d6a0;
        margin-bottom: 0.8rem;
    }

    .donut-container {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 260px;
        background: #ffffff;
        border-radius: 1rem;
        box-shadow: 0 10px 20px rgba(0,0,0,0.08);
        border: 1px solid #e7eff8;
    }

    .donut {
        position: relative;
        width: 210px;
        height: 210px;
        border-radius: 50%;
        background: #d9eefd;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .donut-fill {
        position: absolute;
        inset: 0;
        border-radius: 50%;
        background: conic-gradient(#06d6a0 0deg, #06d6a0 var(--donut-degree), #ddd var(--donut-degree), #ddd 360deg);
    }

    .donut-inner {
        width: 132px;
        height: 132px;
        border-radius: 50%;
        background: #ffffff;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-direction: column;
        box-shadow: 0 3px 12px rgba(0,0,0,0.12);
    }

    .score-card {
        background: linear-gradient(135deg, #f8b500 0%, #fbd46d 100%);
        border-radius: 1rem;
        padding: 1.3rem;
        color: #0f1f3d;
        box-shadow: 0 10px 20px rgba(0,0,0,0.12);
        line-height: 1.45;
    }

    .score-card h4 {
        margin: 0;
        font-size: 1.3rem;
        font-weight: 800;
    }

    .score-card p {
        margin: 0.65rem 0 0.2rem 0;
        font-size: 1rem;
    }

    .recommendation-box {
        background: linear-gradient(90deg, #c9f7f1, #e6f7ff);
        border-radius: 0.75rem;
        padding: 1rem;
        margin: 0.5rem 0;
        border: 1px solid #a4d0f4;
    }

    .scorecard-section {
        background: #ffffff;
        border-radius: 1rem;
        padding: 1rem;
        border: 1px solid #e7eff8;
        box-shadow: 0 8px 16px rgba(0,0,0,0.06);
    }

    .scorecard-tab {
        display: inline-block;
        background: #e0f2ff;
        color: #0c4a6e;
        border-radius: 999px;
        padding: 0.35rem 0.8rem;
        font-weight: 700;
        margin-right: 0.45rem;
        margin-bottom: 0.5rem;
    }

    .scorecard-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 0.75rem;
    }

    .scorecard-table td {
        padding: 0.55rem 0.6rem;
        border-bottom: 1px solid #e6eef8;
        font-size: 0.95rem;
    }

    .scorecard-table td:first-child {
        font-weight: 600;
    }

    .checkmark {
        color: #16a34a;
        font-weight: 800;
    }
    }
    /* Label styling for radio buttons */
    .stRadio label {
        color: #2c3e50 !important;
        font-weight: 500 !important;
    }
    /* Force Streamlit native radio selected style to dark blue */
    [data-testid="stSidebar"] [role="radiogroup"] [role="radio"],
    [data-testid="stSidebar"] [role="radiogroup"] [role="radio"] * {
        color: #1f4e79 !important;
        border-color: #1f4e79 !important;
    }
    [data-testid="stSidebar"] [role="radiogroup"] [role="radio"][aria-checked="true"] {
        background-color: rgba(31, 78, 121, 0.1) !important;
        border-color: #1f4e79 !important;
        color: #1f4e79 !important;
    }
    [data-testid="stSidebar"] [role="radiogroup"] [role="radio"][aria-checked="true"] svg * {
        fill: #1f4e79 !important;
        stroke: #1f4e79 !important;
    }
    /* Shrink clear/X button in file uploader */
    .stFileUploader button[title="Clear"],
    .stFileUploader button[aria-label="Clear"],
    button[title="Clear"],
    button[aria-label="Clear"] {
        font-size: 0.7rem !important;
        width: 1.2rem !important;
        height: 1.2rem !important;
        padding: 0 !important;
        min-width: 0 !important;
        line-height: 1 !important;
    }
    </style>
    """, unsafe_allow_html=True)


def main():
    # Inject global CSS styles
    inject_global_styles()

    # Header (centered)
    st.markdown('<h1 style="text-align: center; margin-top: 0.5rem;">Resume ATS Scanner & Optimizer</h1>', unsafe_allow_html=True)
    
    # Sidebar for file uploads
    with st.sidebar:
        st.header("Upload Documents")
        
        # Resume upload
        resume_file = st.file_uploader(
            "Upload Resume (PDF/DOCX)",
            type=['pdf', 'docx'],
            key="resume_upload"
        )
        
        # Job description input
        st.subheader("Job Description")
        job_input_type = st.selectbox(
            "Input Method",
            ["Text Input", "URL Input"],
            key="job_input_type",
            index=0
        )
        
        if job_input_type == "Text Input":
            job_text = st.text_area(
                "Paste Job Description",
                height=200,
                key="job_text",
                help="Paste the complete job description text here"
            )
            job_url = None
        else:
            job_url = st.text_input(
                "Job Posting URL",
                key="job_url",
                help="Enter the URL of the job posting"
            )
            job_text = None
        
        # Analysis button
        analyze_button = st.button(
            "Analyze Resume",
            type="primary",
            use_container_width=True
        )
    
    # Main content area
    if analyze_button and resume_file and (job_text or job_url):
        with st.spinner("Analyzing your resume against job description..."):
            try:
                # Parse resume
                resume_parser = ResumeParser()
                
                # Save uploaded file temporarily
                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{resume_file.name.split('.')[-1]}") as tmp_file:
                    tmp_file.write(resume_file.getvalue())
                    tmp_file_path = tmp_file.name
                
                # Parse resume
                st.session_state.parsed_resume = resume_parser.parse_file(
                    tmp_file_path,
                    resume_file.name.split('.')[-1]
                )
                logging.debug(f"Resume parsed successfully. Name: {st.session_state.parsed_resume.name}")
                
                # Clean up temp file
                os.unlink(tmp_file_path)
                
                # Parse job description
                job_parser = JobDescriptionParser()
                if job_url:
                    st.session_state.parsed_job = job_parser.parse_job_description(job_url, is_url=True)
                else:
                    st.session_state.parsed_job = job_parser.parse_job_description(job_text, is_url=False)
                
                logging.debug(f"Job parsed successfully. Required skills: {st.session_state.parsed_job.required_skills}")
                
                # Perform ATS scoring
                ats_scorer = ATSScorer()
                st.session_state.ats_score = ats_scorer.calculate_ats_score(
                    st.session_state.parsed_resume,
                    st.session_state.parsed_job
                )
                
                # Keyword analysis with cleaning
                keyword_analyzer = KeywordAnalyzer()
                raw_analysis = keyword_analyzer.analyze_keyword_gaps(
                    st.session_state.parsed_resume,
                    st.session_state.parsed_job
                )
                
                # Clean keywords
                cleaned_critical = clean_keywords(raw_analysis.missing_critical)
                cleaned_important = clean_keywords(raw_analysis.missing_important)
                
                # Categorize keywords
                categorized_critical = categorize_keywords(cleaned_critical)
                categorized_important = categorize_keywords(cleaned_important)
                
                st.session_state.keyword_analysis = {
                    'missing_critical': cleaned_critical,
                    'missing_important': cleaned_important,
                    'categorized_critical': categorized_critical,
                    'categorized_important': categorized_important
                }
                
                # Format analysis
                format_detector = ATSFormatDetector()
                st.session_state.format_analysis = format_detector.analyze_formatting(
                    st.session_state.parsed_resume
                )
                
                # AI suggestions
                with st.spinner("Generating AI-powered suggestions..."):
                    ai_engine = AISuggestionEngine()
                    st.session_state.ai_suggestions = ai_engine.generate_bullet_improvements(
                        st.session_state.parsed_resume,
                        st.session_state.parsed_job
                    )
                
                st.success("Analysis complete!")

            except Exception as e:
                st.error(f"Error during analysis: {str(e)}")
                logging.error(f"Analysis error: {str(e)}")
                return
    
    # Display results
    if st.session_state.ats_score:
        display_results()
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #666;'>"
        "Powered by AI | Built for Job Seekers | ATS-Friendly Resume Optimization"
        "</div>",
        unsafe_allow_html=True
    )

def render_match_score(ats_score):
    fig = px.pie(
        names=['Matched', 'Remaining'],
        values=[ats_score.overall_score, max(0, 100-ats_score.overall_score)],
        hole=0.6,
        color_discrete_sequence=['#7dd3fc', '#e2e8f0']
    )
    fig.update_layout(
        showlegend=False,
        margin=dict(t=0,b=0,l=0,r=0),
        paper_bgcolor='rgba(0,0,0,0)',
        annotations=[dict(text=f"<b>{ats_score.overall_score:.1f}%</b><br>Overall", x=0.5, y=0.5, showarrow=False, font=dict(size=20, color='#0f172a'))]
    )

    st.plotly_chart(fig, use_container_width=True)


def render_resume_quality():
    st.markdown('### Resume Quality')
    st.markdown('Your resume has been evaluated against a set of criteria to ensure it is high quality.')
    
    # Get actual resume data from session state
    parsed_resume = st.session_state.get('parsed_resume')
    ats_score = st.session_state.get('ats_score')
    
    if not parsed_resume or not ats_score:
        st.info("No resume data available for quality check")
        return
    
    # Dynamic quality checks based on actual resume
    checklist = []
    
    # Word count check
    resume_text = st.session_state.get('resume_text', '')
    word_count = len(resume_text.split()) if resume_text else 0
    checklist.append(('Resume length (300+ words)', '✔️' if word_count >= 300 else '❌'))
    
    # Contact info check
    has_contact = (hasattr(parsed_resume, 'contact_info') and 
                  (parsed_resume.contact_info.get('email') or parsed_resume.contact_info.get('phone')))
    checklist.append(('Contact information present', '✔️' if has_contact else '❌'))
    
    # Experience section check
    has_experience = any('experience' in section.title.lower() or 'work' in section.title.lower() 
                       for section in parsed_resume.sections)
    checklist.append(('Experience section present', '✔️' if has_experience else '❌'))
    
    # Education section check
    has_education = any('education' in section.title.lower() or 'academic' in section.title.lower() 
                     for section in parsed_resume.sections)
    checklist.append(('Education section present', '✔️' if has_education else '❌'))
    
    # Skills section check
    has_skills = (hasattr(parsed_resume, 'skills') and len(parsed_resume.skills) > 0)
    checklist.append(('Skills section present', '✔️' if has_skills else '❌'))
    
    for item, mark in checklist:
        st.markdown(f"<p style='margin: 0.25rem 0; font-size: 1rem;'>{mark} {item}</p>", unsafe_allow_html=True)
    
    # Add experience level analysis
    analyze_experience_level(resume_text, parsed_resume)
    
    # Add resume strength score
    calculate_resume_strength_score(checklist, word_count, parsed_resume)

def analyze_experience_level(resume_text, parsed_resume):
    """Analyze experience level from resume content"""
    st.markdown("#### Experience Level Analysis")
    
    # Extract years of experience
    import re
    year_patterns = [
        r'(\d+)\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)',
        r'(\d{4})\s*-\s*(\d{4})',
        r'(\d{4})\s*-\s*present',
        r'experience.*?(\d+)\s*(?:years?|yrs?)',
    ]
    
    total_years = 0
    for pattern in year_patterns:
        matches = re.findall(pattern, resume_text.lower())
        for match in matches:
            if isinstance(match, tuple) and len(match) == 2:
                try:
                    start_year, end_year = match
                    if end_year == 'present':
                        end_year = 2024
                    total_years = max(total_years, int(end_year) - int(start_year))
                except:
                    continue
            elif isinstance(match, str):
                try:
                    total_years = max(total_years, int(match))
                except:
                    continue
    
    # Determine experience level
    if total_years >= 7:
        level = "Senior"
        color = "Expert"
        description = "Expert level with extensive experience"
    elif total_years >= 3:
        level = "Mid-Level"
        color = "Experienced"
        description = "Experienced professional with solid background"
    elif total_years >= 1:
        level = "Junior"
        color = "Growing"
        description = "Early career with growing expertise"
    else:
        level = "Entry-Level"
        color = "Starting"
        description = "Starting professional journey"
    
    # Display experience level
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Experience Level", f"{level}")
    
    with col2:
        st.metric("Estimated Years", f"{total_years}+")
    
    with col3:
        st.metric("Career Stage", description)
    
    # Add career insights
    if total_years < 2:
        st.info("**Tip**: Focus on highlighting projects, internships, and technical skills to compensate for limited work experience.")
    elif total_years < 5:
        st.info("**Tip**: Emphasize growth, achievements, and increasing responsibilities to show career progression.")
    else:
        st.info("**Tip**: Highlight leadership, mentoring, and strategic impact to demonstrate senior-level capabilities.")

def calculate_resume_strength_score(checklist, word_count, parsed_resume):
    """Calculate comprehensive resume strength score"""
    st.markdown("### Resume Strength Score")
    
    # Base score from checklist
    checklist_score = sum(1 for _, mark in checklist if '✔️' in mark) / len(checklist) * 30
    
    # Word count score (optimal 400-600 words)
    if 400 <= word_count <= 600:
        word_score = 25
    elif 300 <= word_count < 400 or 600 < word_count <= 800:
        word_score = 20
    elif word_count >= 300:
        word_score = 15
    else:
        word_score = 5
    
    # Skills diversity score
    skills_count = len(parsed_resume.skills) if hasattr(parsed_resume, 'skills') else 0
    if skills_count >= 15:
        skills_score = 25
    elif skills_count >= 10:
        skills_score = 20
    elif skills_count >= 5:
        skills_score = 15
    else:
        skills_score = 10
    
    # Section completeness score
    section_types = set()
    for section in parsed_resume.sections:
        title_lower = section.title.lower()
        if 'experience' in title_lower or 'work' in title_lower:
            section_types.add('experience')
        elif 'education' in title_lower or 'academic' in title_lower:
            section_types.add('education')
        elif 'project' in title_lower:
            section_types.add('projects')
        elif 'skill' in title_lower:
            section_types.add('skills')
    
    section_score = len(section_types) * 5
    
    # Total score
    total_score = checklist_score + word_score + skills_score + section_score
    total_score = min(total_score, 100)  # Cap at 100
    
    # Display score with visual representation
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # Create gauge chart
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = total_score,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Resume Strength"},
            delta = {'reference': 80},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 50], 'color': "lightgray"},
                    {'range': [50, 80], 'color': "gray"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        
        fig.update_layout(height=300, font=dict(color="darkblue", size=14))
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("#### Score Breakdown:")
        st.markdown(f"• **Content Quality**: {checklist_score:.1f}/30")
        st.markdown(f"• **Word Count**: {word_score}/25")
        st.markdown(f"• **Skills Diversity**: {skills_score}/25")
        st.markdown(f"• **Section Completeness**: {section_score}/20")
        
        # Recommendations based on score
        if total_score >= 85:
            st.success("**Excellent Resume!** Your resume is well-structured and comprehensive.")
        elif total_score >= 70:
            st.info("**Good Resume!** Consider adding more details to reach excellence.")
        elif total_score >= 50:
            st.warning("**Needs Improvement** - Add more sections and details to strengthen your resume.")
        else:
            st.error("**Major Revision Needed** - Significantly expand your resume content.")

def render_hard_skills_table():
    st.markdown('### Hard Skills Analysis')
    
    # Get actual resume and job data
    parsed_resume = st.session_state.get('parsed_resume')
    parsed_job = st.session_state.get('parsed_job')
    resume_text = st.session_state.get('resume_text', '')
    job_text = st.session_state.get('job_text', '')
    
    if not parsed_resume or not parsed_job:
        st.info("No resume or job data available for skills comparison")
        return
    
    # Comprehensive skill extraction from actual content
    def extract_skills_from_text(text, skill_categories):
        found_skills = set()
        text_lower = text.lower()
        
        for category, skills in skill_categories.items():
            for skill in skills:
                # Check for exact skill mentions
                if skill.lower() in text_lower:
                    found_skills.add(skill)
                # Check for variations
                elif any(variant.lower() in text_lower for variant in [skill.replace('.', ''), skill.replace('.js', ''), skill.replace(' ', '')]):
                    found_skills.add(skill)
        
        return found_skills
    
    # Enhanced skill categories with more comprehensive lists
    skill_categories = {
        'Programming Languages': [
            'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'c', 'go', 'rust', 
            'scala', 'ruby', 'php', 'swift', 'kotlin', 'dart', 'perl', 'r', 'matlab'
        ],
        'Web Technologies': [
            'html', 'css', 'react', 'angular', 'vue', 'node.js', 'express', 'django', 
            'flask', 'spring', 'laravel', 'rails', 'asp.net', 'next.js', 'gatsby', 'webpack'
        ],
        'Databases': [
            'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'oracle', 'sqlite', 
            'cassandra', 'elasticsearch', 'dynamodb', 'firebase', 'supabase'
        ],
        'Cloud & DevOps': [
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform', 'jenkins', 
            'gitlab', 'github actions', 'ansible', 'puppet', 'chef', 'nagios', 'prometheus'
        ],
        'AI/ML & Data Science': [
            'tensorflow', 'pytorch', 'keras', 'scikit-learn', 'pandas', 'numpy', 
            'opencv', 'nltk', 'spacy', 'hugging face', 'langchain', 'llm', 'machine learning', 
            'deep learning', 'data science', 'computer vision', 'nlp'
        ],
        'Tools & Technologies': [
            'git', 'github', 'gitlab', 'vscode', 'intellij', 'eclipse', 'postman', 
            'jira', 'slack', 'power bi', 'tableau', 'excel', 'linux', 'ubuntu', 'windows',
            'macos', 'jupyter', 'anaconda', 'docker', 'kubernetes', 'nginx', 'apache'
        ],
        'Frameworks & Libraries': [
            'spring boot', 'spring mvc', 'jsf', 'wicket', 'gwt', 'hibernate', 'jpa', 
            'mybatis', 'redux', 'mobx', 'bootstrap', 'tailwind', 'material ui', 'ant design'
        ],
        'Testing & QA': [
            'jest', 'mocha', 'jasmine', 'selenium', 'cypress', 'junit', 'pytest', 
            'test-driven development', 'tdd', 'bdd', 'unit testing', 'integration testing'
        ]
    }
    
    # Extract skills from both sources
    resume_skills = extract_skills_from_text(resume_text, skill_categories)
    job_skills = extract_skills_from_text(job_text, skill_categories)
    
    # Build comprehensive comparison table
    all_skills = []
    for category, skills in skill_categories.items():
        for skill in skills:
            if skill in resume_skills or skill in job_skills:
                all_skills.append(skill)
    
    # Sort by relevance (skills in both sources first)
    all_skills.sort(key=lambda x: (x in resume_skills and x in job_skills, x in job_skills, x in resume_skills), reverse=True)
    
    # Create comparison data
    skills_data = []
    for skill in all_skills[:25]:  # Show top 25 relevant skills
        in_resume = '✔️' if skill in resume_skills else '❌'
        in_job = '✔️' if skill in job_skills else '❌'
        skills_data.append((skill.title(), in_resume, in_job))
    
    if skills_data:
        df = pd.DataFrame(skills_data, columns=['Skill', 'Your Resume', 'Job Description'])
        st.table(df)
        
        # Add skill gap analysis
        missing_skills = [skill for skill in all_skills if skill in job_skills and skill not in resume_skills]
        extra_skills = [skill for skill in all_skills if skill in resume_skills and skill not in job_skills]
        
        if missing_skills:
            st.markdown(f"🎯 **Missing Skills to Add**: {', '.join(missing_skills[:8])}")
        
        if extra_skills:
            st.markdown(f"💡 **Additional Skills You Have**: {', '.join(extra_skills[:8])}")
        
        # Add skills radar chart
        create_skills_radar_chart(skill_categories, resume_skills, job_skills)
        
        # Add skill compatibility score
        calculate_skill_compatibility(resume_skills, job_skills, all_skills)
        
    else:
        st.info("No technical skills found in resume or job description")

def create_skills_radar_chart(skill_categories, resume_skills, job_skills):
    """Create an interactive radar chart for skill comparison"""
    st.markdown("### 📊 Skills Compatibility Radar")
    
    # Calculate category scores
    categories = []
    resume_scores = []
    job_scores = []
    
    for category, skills in skill_categories.items():
        resume_count = sum(1 for skill in skills if skill in resume_skills)
        job_count = sum(1 for skill in skills if skill in job_skills)
        total_count = len(skills)
        
        if total_count > 0:
            categories.append(category.replace(' ', '\n'))
            resume_scores.append((resume_count / total_count) * 100)
            job_scores.append((job_count / total_count) * 100)
    
    if categories:
        fig = go.Figure()
        
        fig.add_trace(go.Scatterpolar(
            r=resume_scores,
            theta=categories,
            fill='toself',
            name='Your Skills',
            line_color='rgba(59, 130, 246, 0.8)',
            fillcolor='rgba(59, 130, 246, 0.2)'
        ))
        
        fig.add_trace(go.Scatterpolar(
            r=job_scores,
            theta=categories,
            fill='toself',
            name='Job Requirements',
            line_color='rgba(239, 68, 68, 0.8)',
            fillcolor='rgba(239, 68, 68, 0.2)'
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    tickfont=dict(size=10)
                )
            ),
            showlegend=True,
            title="Skills Coverage Analysis",
            height=500,
            font=dict(size=12)
        )
        
        st.plotly_chart(fig, use_container_width=True)

def calculate_skill_compatibility(resume_skills, job_skills, all_skills):
    """Calculate and display detailed skill compatibility metrics"""
    st.markdown("### 🎯 Skill Compatibility Analysis")
    
    # Calculate metrics
    matching_skills = resume_skills & job_skills
    missing_skills = job_skills - resume_skills
    extra_skills = resume_skills - job_skills
    
    total_job_skills = len(job_skills)
    total_resume_skills = len(resume_skills)
    
    if total_job_skills > 0:
        match_percentage = (len(matching_skills) / total_job_skills) * 100
    else:
        match_percentage = 0
    
    # Display metrics in columns
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Skill Match", f"{match_percentage:.1f}%", delta=f"{len(matching_skills)} skills")
    
    with col2:
        st.metric("Your Skills", total_resume_skills, delta=f"{len(extra_skills)} extra")
    
    with col3:
        st.metric("Required Skills", total_job_skills, delta=f"{len(missing_skills)} missing")
    
    with col4:
        compatibility_score = (match_percentage * 0.7 + min(total_resume_skills / total_job_skills * 30, 30)) if total_job_skills > 0 else 0
        st.metric("Compatibility", f"{compatibility_score:.1f}%")
    
    # Detailed breakdown
    if matching_skills:
        st.markdown("#### ✅ Matching Skills")
        st.write(", ".join(sorted(matching_skills)))
    
    if missing_skills:
        st.markdown("#### ⚠️ Skills to Add")
        st.write(", ".join(sorted(missing_skills)))
    
    if extra_skills:
        st.markdown("#### 💡 Bonus Skills")
        st.write(", ".join(sorted(extra_skills)))


def render_ats_section(ats_score, matched_keyword_list):
    st.markdown('### ATS Optimization')
    
    # Get actual ATS score data
    breakdown = getattr(ats_score, 'detailed_breakdown', {}) or {}
    
    # Dynamic ATS metrics
    st.markdown('<ul style="list-style:none; padding-left:0;">', unsafe_allow_html=True)
    
    # Overall ATS score
    st.markdown(f'<li style="color:#0f172a;">✔️ ATS score: {ats_score.overall_score:.1f}%</li>', unsafe_allow_html=True)
    
    # Skill match score
    st.markdown(f'<li style="color:#0f172a;">✔️ Skill match score: {ats_score.skill_match_score:.1f}%</li>', unsafe_allow_html=True)
    
    # Experience match score
    st.markdown(f'<li style="color:#0f172a;">✔️ Experience match score: {ats_score.experience_match_score:.1f}%</li>', unsafe_allow_html=True)
    
    # Keyword density score
    st.markdown(f'<li style="color:#0f172a;">✔️ Keyword density score: {ats_score.keyword_density_score:.1f}%</li>', unsafe_allow_html=True)
    
    # Format compatibility score
    st.markdown(f'<li style="color:#0f172a;">✔️ Format compatibility score: {ats_score.format_compatibility_score:.1f}%</li>', unsafe_allow_html=True)
    
    # Resume length check
    word_count = breakdown.get('resume_word_count', 0)
    st.markdown(f'<li style="color:#0f172a;">✔️ Resume word count: {word_count}</li>', unsafe_allow_html=True)
    
    # Standard section headers check
    exp_sections = breakdown.get('experience_sections_found', 0)
    edu_sections = breakdown.get('education_sections_found', 0)
    st.markdown(f'<li style="color:#0f172a;">✔️ Experience sections: {exp_sections}</li>', unsafe_allow_html=True)
    st.markdown(f'<li style="color:#0f172a;">✔️ Education sections: {edu_sections}</li>', unsafe_allow_html=True)
    
    # Missing skills suggestions
    missing_skills = breakdown.get('missing_required_skills', [])
    if missing_skills:
        st.markdown('<li style="color:#f59e0b;">⚠️ Missing skills to add:</li>', unsafe_allow_html=True)
        for skill in missing_skills[:5]:  # Show top 5 missing skills
            st.markdown(f'<li style="color:#f59e0b; margin-left:1rem;">• {skill}</li>', unsafe_allow_html=True)
    else:
        st.markdown('<li style="color:#0f172a;">✔️ All required skills present</li>', unsafe_allow_html=True)
    
    st.markdown('</ul>', unsafe_allow_html=True)

    st.markdown('### Key JD Keywords')
    parsed_job = st.session_state.get('parsed_job')
    keyword_data = st.session_state.get('keyword_analysis', {}) or {}

    if parsed_job:
        parsed_job_keywords = [k for k in (parsed_job.required_skills or []) + (parsed_job.preferred_skills or []) + (parsed_job.keywords or []) if k]
    else:
        parsed_job_keywords = []

    fallback_keywords = (keyword_data.get('missing_critical', []) or []) + (keyword_data.get('missing_important', []) or []) + matched_keyword_list

    # Use unique keywords preserving order
    seen = set()
    tags = []
    for kw in parsed_job_keywords + fallback_keywords:
        kw_str = str(kw).strip()
        if not kw_str or kw_str.lower() in {'and', 'with', 'for', 'the', 'a', 'an', 'to', 'of', 'in', 'on', 'at', 'by', 'as'}:
            continue
        if kw_str.lower() in seen:
            continue
        seen.add(kw_str.lower())
        tags.append(kw_str)
        if len(tags) >= 18:
            break

    if not tags:
        tags = ['python', 'aws', 'sql', 'communication', 'leadership']

    col_items = ' '.join([
        f"<span style='display:inline-block;background:#dbeafe;color:#1d4ed8;border-radius:999px;padding:0.2rem 0.5rem;margin:0.15rem;font-size:0.85rem;'>{t}</span>"
        for t in tags
    ])

    st.markdown(f"<div>{col_items}</div>", unsafe_allow_html=True)


def render_ai_recommendations():
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<h3>AI Recommendations</h3>', unsafe_allow_html=True)
    ai_suggestions = st.session_state.get('ai_suggestions')
    keyword_data = st.session_state.get('keyword_analysis', {}) or {}
    missing_skills = (keyword_data.get('missing_critical') or []) + (keyword_data.get('missing_important') or [])

    def render_suggestion(bullet_text):
        st.markdown(f"<div style='margin-bottom:0.45rem;'>• {bullet_text}</div>", unsafe_allow_html=True)

    rendered_any = False

    if ai_suggestions and len(ai_suggestions) > 0:
        for section in ai_suggestions:
            if section.suggestions:
                st.markdown(f"<strong>{section.section_name}</strong>", unsafe_allow_html=True)
                for bullet_suggestion in section.suggestions:
                    text = bullet_suggestion.improved_bullet or bullet_suggestion.original_bullet
                    keywords = ', '.join(bullet_suggestion.added_keywords) if bullet_suggestion.added_keywords else None
                    if keywords:
                        render_suggestion(f"{text} (Keywords: {keywords})")
                    else:
                        render_suggestion(text)
                    rendered_any = True

    if not rendered_any:
        if missing_skills:
            render_suggestion('Include missing JD keywords: ' + ', '.join(missing_skills[:6]))
            rendered_any = True

        render_suggestion('Add measurable results (e.g., reduced processing time by 30%, increased coverage by 25%).')
        render_suggestion('Use action verbs and context: improved, led, architected, delivered, optimized.')

        parsed_job = st.session_state.get('parsed_job')
        if parsed_job and hasattr(parsed_job, 'title'):
            render_suggestion(f"Emphasize the role focus: '{parsed_job.title}' in your summary and top achievements.")

    st.markdown('</div>', unsafe_allow_html=True)


def display_results():
    st.markdown('<h1 style="color:#ffffff; text-align:center; margin-bottom:1rem;">Match Assessments</h1>', unsafe_allow_html=True)

    ats_score = st.session_state.ats_score
    breakdown = ats_score.detailed_breakdown
    matched_keyword_list = breakdown.get('matched_required_skills', [])

    st.markdown('<div style="display:flex; flex-wrap:wrap; gap:1rem;">', unsafe_allow_html=True)

    with st.container():
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<h3 style="margin-bottom:0.5rem;">Match Score</h3>', unsafe_allow_html=True)
            render_match_score(ats_score)
            st.markdown('</div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="card" style="background: linear-gradient(135deg, #fef3c7, #fde68a);">', unsafe_allow_html=True)
            st.markdown('<h3 style="margin-bottom:0.5rem;">Matching Metrics</h3>', unsafe_allow_html=True)
            st.markdown(f'<p style="margin:0.25rem 0 0.75rem; font-size: 1.15rem; font-weight:600;">Overall Score: <strong>{ats_score.overall_score:.1f}%</strong></p>', unsafe_allow_html=True)

            st.markdown('<ul style="padding-left:1rem; margin:0; font-size:1.1rem; line-height:1.5;">', unsafe_allow_html=True)
            st.markdown(f'<li>Skill Match: <strong>{ats_score.skill_match_score:.1f}%</strong></li>', unsafe_allow_html=True)
            st.markdown(f'<li>Experience Match: <strong>{ats_score.experience_match_score:.1f}%</strong></li>', unsafe_allow_html=True)
            st.markdown(f'<li>Keyword Density: <strong>{ats_score.keyword_density_score:.1f}%</strong></li>', unsafe_allow_html=True)
            st.markdown(f'<li>Format Compatibility: <strong>{ats_score.format_compatibility_score:.1f}%</strong></li>', unsafe_allow_html=True)
            st.markdown('</ul>', unsafe_allow_html=True)

            breakdown = getattr(ats_score, 'detailed_breakdown', {}) or {}
            word_count = breakdown.get('resume_word_count', 0)
            job_keywords = breakdown.get('job_keyword_count', 0)
            exp_sections = breakdown.get('experience_sections_found', 0)
            edu_sections = breakdown.get('education_sections_found', 0)

            st.markdown('<strong style="margin-top:0.75rem; display:block;">Content Analysis</strong>', unsafe_allow_html=True)
            st.markdown('<ul style="padding-left:1rem; margin:0;">', unsafe_allow_html=True)
            st.markdown(f'<li>Resume Word Count: <strong>{word_count}</strong></li>', unsafe_allow_html=True)
            st.markdown(f'<li>Job Keywords: <strong>{job_keywords}</strong></li>', unsafe_allow_html=True)
            st.markdown(f'<li>Experience Sections: <strong>{exp_sections}</strong></li>', unsafe_allow_html=True)
            st.markdown(f'<li>Education Sections: <strong>{edu_sections}</strong></li>', unsafe_allow_html=True)
            st.markdown('</ul>', unsafe_allow_html=True)

            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card" style="margin-top:1rem;">', unsafe_allow_html=True)
    st.markdown('<h3 style="margin-bottom:0.75rem;">Scorecard</h3>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(['Resume Quality', 'Hard Skills', 'ATS', 'Career Insights'])

    with tab1:
        render_resume_quality()

    with tab2:
        render_hard_skills_table()

    with tab3:
        render_ats_section(ats_score, matched_keyword_list)
        
    with tab4:
        render_career_insights()

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('---')

    render_ai_recommendations()



def render_career_insights():
    """Provide career path recommendations and job market insights"""
    st.markdown("### Career Path Recommendations")
    
    parsed_resume = st.session_state.get('parsed_resume')
    parsed_job = st.session_state.get('parsed_job')
    resume_text = st.session_state.get('resume_text', '')
    job_text = st.session_state.get('job_text', '')
    ats_score = st.session_state.get('ats_score')
    
    if not parsed_resume or not parsed_job:
        st.info("No data available for career insights")
        return
    
    # Analyze current position and suggest career paths
    analyze_career_trajectory(resume_text, job_text, parsed_resume, parsed_job)
    
    # Job market insights
    provide_market_insights(parsed_job, ats_score)
    
    # Skill development roadmap
    create_skill_roadmap(resume_text, job_text, parsed_resume, parsed_job)

def analyze_career_trajectory(resume_text, job_text, parsed_resume, parsed_job):
    """Analyze career trajectory and provide recommendations"""
    st.markdown("#### Career Trajectory Analysis")
    
    # Extract current role and experience level
    current_roles = []
    for section in parsed_resume.sections:
        if 'experience' in section.title.lower() or 'work' in section.title.lower():
            if hasattr(section, 'content') and section.content:
                lines = section.content.split('\n')
                for line in lines[:3]:  # Check first 3 lines for current role
                    if any(keyword in line.lower() for keyword in ['engineer', 'developer', 'analyst', 'manager', 'lead', 'senior', 'junior']):
                        current_roles.append(line.strip())
    
    # Determine career path based on skills and experience
    resume_skills_lower = resume_text.lower()
    job_skills_lower = job_text.lower()
    
    career_paths = {
        'Software Engineering': {
            'keywords': ['software', 'developer', 'engineer', 'programming', 'coding', 'java', 'python', 'javascript'],
            'next_roles': ['Senior Software Engineer', 'Tech Lead', 'Engineering Manager', 'Principal Engineer'],
            'growth_areas': ['System Architecture', 'Team Leadership', 'DevOps', 'Cloud Computing']
        },
        'Data Science/AI': {
            'keywords': ['data', 'ai', 'machine learning', 'tensorflow', 'pytorch', 'pandas', 'numpy', 'analytics'],
            'next_roles': ['Senior Data Scientist', 'ML Engineer', 'AI Researcher', 'Data Science Manager'],
            'growth_areas': ['Deep Learning', 'MLOps', 'Big Data', 'AI Ethics']
        },
        'Web Development': {
            'keywords': ['web', 'frontend', 'backend', 'full-stack', 'react', 'angular', 'node.js', 'html', 'css'],
            'next_roles': ['Senior Full-Stack Developer', 'Frontend Architect', 'Backend Specialist', 'Web Development Lead'],
            'growth_areas': ['Microservices', 'Progressive Web Apps', 'Web Performance', 'API Design']
        },
        'DevOps/Cloud': {
            'keywords': ['devops', 'cloud', 'aws', 'azure', 'docker', 'kubernetes', 'ci/cd', 'infrastructure'],
            'next_roles': ['DevOps Engineer', 'Cloud Architect', 'Site Reliability Engineer', 'Infrastructure Manager'],
            'growth_areas': ['Kubernetes', 'Serverless', 'Infrastructure as Code', 'Cloud Security']
        }
    }
    
    # Determine best career path
    best_path = None
    best_score = 0
    
    for path, data in career_paths.items():
        score = sum(1 for keyword in data['keywords'] if keyword in resume_skills_lower)
        if score > best_score:
            best_score = score
            best_path = path
    
    if best_path:
        st.markdown(f"**Recommended Career Path**: {best_path}")
        st.markdown(f"**Next Potential Roles**: {', '.join(career_paths[best_path]['next_roles'])}")
        st.markdown(f"**Key Growth Areas**: {', '.join(career_paths[best_path]['growth_areas'])}")
        
        # Progress indicator
        progress_score = min(best_score * 20, 100)
        st.progress(progress_score / 100)
        st.markdown(f"*Career alignment: {progress_score}%*")

def provide_market_insights(parsed_job, ats_score):
    """Provide job market insights and salary expectations"""
    st.markdown("#### Market Insights & Salary Expectations")
    
    # Extract job level and requirements
    job_text_lower = st.session_state.get('job_text', '').lower()
    
    # Determine job level
    if any(keyword in job_text_lower for keyword in ['senior', 'lead', 'principal', 'architect']):
        job_level = 'Senior'
        salary_range = '$120,000 - $180,000'
    elif any(keyword in job_text_lower for keyword in ['mid', 'experienced', '3+', '5+']):
        job_level = 'Mid-Level'
        salary_range = '$80,000 - $120,000'
    else:
        job_level = 'Entry-Level'
        salary_range = '$60,000 - $90,000'
    
    # Market demand indicators
    demand_indicators = []
    
    if ats_score.overall_score >= 80:
        demand_indicators.append("High Demand - Your skills match perfectly!")
    elif ats_score.overall_score >= 60:
        demand_indicators.append("Good Demand - Strong potential with minor improvements")
    else:
        demand_indicators.append("Growing Demand - Skill development needed")
    
    # Display insights in columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Job Level", job_level)
    
    with col2:
        st.metric("Salary Range", salary_range)
    
    with col3:
        st.metric("Market Demand", demand_indicators[0])
    
    # Additional insights
    st.markdown("#### Competitive Analysis")
    
    # Calculate competitive score
    competitive_score = (ats_score.skill_match_score * 0.4 + 
                        ats_score.keyword_density_score * 0.3 + 
                        ats_score.format_compatibility_score * 0.3)
    
    if competitive_score >= 85:
        st.success("**Highly Competitive** - You're in the top tier of candidates!")
    elif competitive_score >= 70:
        st.info("**Competitive** - Strong candidate with good chances")
    elif competitive_score >= 50:
        st.warning("**Moderately Competitive** - Some improvements needed")
    else:
        st.error("**Needs Development** - Focus on skill enhancement")

def create_skill_roadmap(resume_text, job_text, parsed_resume, parsed_job):
    """Create personalized skill development roadmap"""
    st.markdown("#### Skill Development Roadmap")
    
    # Extract skills from both sources with enhanced detection
    resume_skills = set()
    job_skills = set()
    
    # Enhanced skill extraction with variations and patterns
    def extract_skills_comprehensive(text):
        found = set()
        text_lower = text.lower()
        
        # Direct skill matching
        tech_skills = [
            'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'c', 'go', 'rust', 
            'scala', 'ruby', 'php', 'swift', 'kotlin', 'dart', 'perl', 'r', 'matlab',
            'html', 'css', 'react', 'angular', 'vue', 'node.js', 'express', 'django', 
            'flask', 'spring', 'laravel', 'rails', 'asp.net', 'next.js', 'gatsby', 'webpack',
            'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'oracle', 'sqlite', 
            'cassandra', 'elasticsearch', 'dynamodb', 'firebase', 'supabase',
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform', 'jenkins', 
            'gitlab', 'github actions', 'ansible', 'puppet', 'chef', 'nagios', 'prometheus',
            'tensorflow', 'pytorch', 'keras', 'scikit-learn', 'pandas', 'numpy', 
            'opencv', 'nltk', 'spacy', 'hugging face', 'langchain', 'llm', 'machine learning', 
            'deep learning', 'data science', 'computer vision', 'nlp', 'ai', 'ml', 'dl', 'cv',
            'git', 'github', 'gitlab', 'vscode', 'intellij', 'eclipse', 'postman', 
            'jira', 'slack', 'power bi', 'tableau', 'excel', 'linux', 'ubuntu', 'windows',
            'macos', 'jupyter', 'anaconda', 'nginx', 'apache', 'rest', 'graphql', 'api'
        ]
        
        for skill in tech_skills:
            # Check for exact match
            if skill in text_lower:
                found.add(skill)
            # Check for variations and patterns
            else:
                # Check for skill with variations
                variations = [
                    skill.replace('.', ''),
                    skill.replace('.js', 'js'),
                    skill.replace(' ', ''),
                    skill.replace('-', ''),
                    skill.replace('_', '')
                ]
                
                for variation in variations:
                    if variation in text_lower:
                        found.add(skill)
                        break
        
        return found
    
    resume_skills = extract_skills_comprehensive(resume_text)
    job_skills = extract_skills_comprehensive(job_text)
    
    # Categorize skills for roadmap
    missing_critical = job_skills - resume_skills
    existing_skills = resume_skills & job_skills
    bonus_skills = resume_skills - job_skills
    
    # Create roadmap timeline
    st.markdown("##### 3-Month Learning Plan")
    
    if missing_critical:
        st.markdown("**Priority 1: Critical Missing Skills**")
        for i, skill in enumerate(list(missing_critical)[:3], 1):
            st.markdown(f"Month {i}: Master {skill.title()}")
            st.markdown(f"- Online courses and hands-on projects")
            st.markdown(f"- Build portfolio projects using {skill.title()}")
    
    st.markdown("**Priority 2: Strengthen Existing Skills**")
    if existing_skills:
        for skill in list(existing_skills)[:2]:
            st.markdown(f"Advanced {skill.title()} - Best practices and patterns")
    
    st.markdown("**Priority 3: Leverage Bonus Skills**")
    if bonus_skills:
        st.markdown(f"Highlight: {', '.join(list(bonus_skills)[:3])}")
        st.markdown("These differentiate you from other candidates!")
    
    # Learning resources
    st.markdown("##### Recommended Learning Resources")
    
    resources = [
        ("Coursera", "Professional certificates and specializations"),
        ("Udemy", "Practical, project-based courses"),
        ("GitHub", "Open source contributions"),
        ("Stack Overflow", "Community learning"),
        ("LinkedIn Learning", "Industry-specific skills")
    ]
    
    for platform, description in resources:
        st.markdown(f"• **{platform}**: {description}")
    
    # API-like insights for missing skills
    if missing_critical:
        st.markdown("##### Missing Skills Insights")
        
        # Skill difficulty and learning time estimates
        skill_insights = {
            'python': {'difficulty': 'Beginner', 'weeks': 4, 'resources': ['Python.org', 'Real Python', 'Codecademy']},
            'java': {'difficulty': 'Intermediate', 'weeks': 8, 'resources': ['Oracle University', 'Java Brains', 'Coursera Java Course']},
            'javascript': {'difficulty': 'Beginner', 'weeks': 6, 'resources': ['JavaScript.info', 'MDN Web Docs', 'FreeCodeCamp']},
            'react': {'difficulty': 'Intermediate', 'weeks': 10, 'resources': ['React Documentation', 'React Tutorial', 'Scrimba']},
            'node.js': {'difficulty': 'Beginner', 'weeks': 6, 'resources': ['Node.js.org', 'Express.js Guide', 'NodeSchool']},
            'aws': {'difficulty': 'Intermediate', 'weeks': 12, 'resources': ['AWS Training Center', 'Cloud Academy', 'A Cloud Guru']},
            'docker': {'difficulty': 'Intermediate', 'weeks': 8, 'resources': ['Docker Documentation', 'Play with Docker', 'KodeKloud']},
            'kubernetes': {'difficulty': 'Advanced', 'weeks': 16, 'resources': ['Kubernetes Documentation', 'Certified Kubernetes Administrator']},
            'tensorflow': {'difficulty': 'Advanced', 'weeks': 20, 'resources': ['TensorFlow Documentation', 'Fast.ai', 'Coursera Deep Learning']},
            'pytorch': {'difficulty': 'Advanced', 'weeks': 20, 'resources': ['PyTorch Documentation', 'Fast.ai', 'DeepLearning.ai']},
            'sql': {'difficulty': 'Intermediate', 'weeks': 6, 'resources': ['SQLBolt', 'Mode Analytics', 'LeetCode Database']},
            'mongodb': {'difficulty': 'Beginner', 'weeks': 4, 'resources': ['MongoDB University', 'MongoDB Manual', 'DevOps with MongoDB']}
        }
        
        for skill in list(missing_critical)[:5]:
            if skill in skill_insights:
                insight = skill_insights[skill]
                st.markdown(f"**{skill.title()}**")
                st.markdown(f"• **Difficulty**: {insight['difficulty']}")
                st.markdown(f"• **Learning Time**: {insight['weeks']} weeks")
                st.markdown(f"• **Top Resources**: {', '.join(insight['resources'][:3])}")
                st.markdown("---")
    
    # Skill market demand and salary boost analysis
    if missing_critical:
        st.markdown("##### Market Value Analysis")
        
        market_data = {
            'python': {'demand': 'Very High', 'salary_boost': '20-30%', 'market_trend': 'Growing'},
            'java': {'demand': 'High', 'salary_boost': '15-25%', 'market_trend': 'Stable'},
            'javascript': {'demand': 'Very High', 'salary_boost': '20-30%', 'market_trend': 'Growing'},
            'react': {'demand': 'High', 'salary_boost': '15-25%', 'market_trend': 'Growing'},
            'aws': {'demand': 'Very High', 'salary_boost': '25-40%', 'market_trend': 'Explosive'},
            'docker': {'demand': 'High', 'salary_boost': '15-25%', 'market_trend': 'Growing'},
            'kubernetes': {'demand': 'Very High', 'salary_boost': '30-50%', 'market_trend': 'Explosive'},
            'tensorflow': {'demand': 'High', 'salary_boost': '20-35%', 'market_trend': 'Growing'},
            'pytorch': {'demand': 'High', 'salary_boost': '20-35%', 'market_trend': 'Growing'},
            'sql': {'demand': 'High', 'salary_boost': '10-20%', 'market_trend': 'Stable'},
            'mongodb': {'demand': 'Medium', 'salary_boost': '10-15%', 'market_trend': 'Stable'}
        }
        
        st.markdown("**Salary Impact Analysis**")
        for skill in list(missing_critical)[:3]:
            if skill in market_data:
                data = market_data[skill]
                st.markdown(f"• **{skill.title()}**: {data['demand']} demand, {data['salary_boost']} salary increase")
        
        st.markdown("**Learning Priority Recommendations**")
        st.markdown("Based on market demand and salary impact:")
        
        # Sort missing skills by market value
        prioritized_skills = []
        for skill in missing_critical:
            if skill in market_data:
                priority_score = 0
                if market_data[skill]['demand'] == 'Very High':
                    priority_score += 30
                elif market_data[skill]['demand'] == 'High':
                    priority_score += 20
                elif market_data[skill]['demand'] == 'Medium':
                    priority_score += 10
                else:
                    priority_score += 5
                
                if market_data[skill]['salary_boost']:
                    boost = int(market_data[skill]['salary_boost'].split('-')[0])
                    priority_score += boost
                
                prioritized_skills.append((skill, priority_score))
        
        # Sort by priority and display
        prioritized_skills.sort(key=lambda x: x[1], reverse=True)
        
        for i, (skill, score) in enumerate(prioritized_skills[:5], 1):
            st.markdown(f"{i}. **{skill.title()}** (Priority Score: {score})")
    
    # Career acceleration tips
    st.markdown("##### Career Acceleration Strategy")
    st.markdown("**Focus on high-impact skills first:**")
    st.markdown("• Skills with 'Very High' market demand and 25%+ salary boost")
    st.markdown("• Technologies that appear in multiple job postings")
    st.markdown("• Skills that complement your existing expertise")
    
    st.markdown("**Time Investment Strategy:**")
    st.markdown("• Dedicate 20 hours/week to highest priority skill")
    st.markdown("• Practice with real projects, not just tutorials")
    st.markdown("• Join professional communities for each target skill")
    st.markdown("• Consider certifications for quick credibility boost")


if __name__ == "__main__":
    main()
