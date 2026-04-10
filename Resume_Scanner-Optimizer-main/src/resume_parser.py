import pdfplumber
import docx
import re
from typing import Dict, List, Any
from dataclasses import dataclass
import spacy

@dataclass
class ResumeSection:
    title: str
    content: str
    bullet_points: List[str]

@dataclass
class ParsedResume:
    full_text: str
    sections: List[ResumeSection]
    skills: List[str]
    experience: List[str]
    education: List[str]
    contact_info: Dict[str, str]
    name: str = ""

class ResumeParser:
    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("spaCy model not found. Please run: python -m spacy download en_core_web_sm")
            self.nlp = None
    
    def parse_file(self, file_path: str, file_type: str) -> ParsedResume:
        """Parse resume file based on type"""
        if file_type.lower() == 'pdf':
            text = self._parse_pdf(file_path)
        elif file_type.lower() == 'docx':
            text = self._parse_docx(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        
        return self._parse_text(text)
    
    def _parse_pdf(self, file_path: str) -> str:
        """Extract text from PDF file"""
        text = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            raise Exception(f"Error parsing PDF: {str(e)}")
        return text
    
    def _parse_docx(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        try:
            doc = docx.Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
        except Exception as e:
            raise Exception(f"Error parsing DOCX: {str(e)}")
        return text
    
    def _parse_text(self, text: str) -> ParsedResume:
        """Parse extracted text into structured resume data"""
        sections = self._extract_sections(text)
        skills = self._extract_skills(text)
        experience = self._extract_experience(sections)
        education = self._extract_education(sections)
        contact_info = self._extract_contact_info(text)
        name = self._extract_name(text)
        
        return ParsedResume(
            full_text=text,
            sections=sections,
            skills=skills,
            experience=experience,
            education=education,
            contact_info=contact_info,
            name=name
        )
    
    def _extract_sections(self, text: str) -> List[ResumeSection]:
        """Extract different sections from resume - Enhanced to capture ALL sections"""
        section_patterns = {
            'experience': r'(?:experience|work|employment|professional|career)',
            'education': r'(?:education|academic|qualification|degree)',
            'skills': r'(?:skills|technical|technologies|competencies|abilities)',
            'projects': r'(?:projects|portfolio|work)',
            'summary': r'(?:summary|objective|profile|about)',
            'certifications': r'(?:certifications|certificates|credentials)',
            'achievements': r'(?:achievements|awards|honors)',
            'internship': r'(?:internship|intern|trainee)',
            'coding platforms': r'(?:coding|platforms|leetcode|hackerrank|codeforces|geeksforgeeks)',
            'leadership': r'(?:leadership|leadership roles|positions)',
            'publications': r'(?:publications|papers|research)',
            'volunteer': r'(?:volunteer|volunteering|community service)',
            'languages': r'(?:languages|spoken languages|language proficiency)',
            'interests': r'(?:interests|hobbies|activities)',
            'references': r'(?:references|referees)'
        }
        
        sections = []
        lines = text.split('\n')
        current_section = None
        current_content = []
        current_bullets = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Handle combined section headers like "CERTIFICATIONS & ACHIEVEMENTS" or "CERTIFICATIONS AND ACHIEVEMENTS"
            if any(sep in line for sep in ['&', '/', ' and ']):
                parts = re.split(r'\s*(?:&|/| and )\s*', line)
                for part in parts:
                    part = part.strip()
                    for section_name, pattern in section_patterns.items():
                        if re.match(pattern, part, re.IGNORECASE) and len(part) < 50:
                            if current_section:
                                sections.append(ResumeSection(
                                    title=current_section,
                                    content='\n'.join(current_content),
                                    bullet_points=current_bullets
                                ))
                            current_section = section_name
                            current_content = []
                            current_bullets = []
                            break
                continue

            # Check if this is a section header - Enhanced detection
            is_section = False
            for section_name, pattern in section_patterns.items():
                if re.match(pattern, line, re.IGNORECASE) and len(line) < 50:
                    if current_section:
                        sections.append(ResumeSection(
                            title=current_section,
                            content='\n'.join(current_content),
                            bullet_points=current_bullets
                        ))
                    current_section = section_name
                    current_content = []
                    current_bullets = []
                    is_section = True
                    break
            
            if not is_section and current_section:
                current_content.append(line)
                # Extract bullet points - Enhanced detection
                if line.startswith(('•', '-', '*', '·', '▪', '■', '○', '●')):
                    current_bullets.append(line)
                elif re.match(r'^\d+\.\s+', line):  # Numbered lists
                    current_bullets.append(line)
        
        # Add the last section
        if current_section:
            sections.append(ResumeSection(
                title=current_section,
                content='\n'.join(current_content),
                bullet_points=current_bullets
            ))
        
        # DEBUG: Print all extracted sections
        print(f"🔍 Extracted {len(sections)} sections:")
        for i, section in enumerate(sections):
            print(f"  {i+1}. {section.title}: {len(section.content)} chars, {len(section.bullet_points)} bullets")
        
        return sections
    
    def _extract_skills(self, text: str) -> List[str]:
        """Extract skills from resume text - Enhanced with comprehensive skill detection"""
        if not self.nlp:
            return self._extract_skills_fallback(text)
        
        doc = self.nlp(text)
        skills = []
        
        # Comprehensive technical skills keywords
        tech_keywords = [
            # Programming Languages
            'python', 'java', 'javascript', 'typescript', 'c++', 'c', 'c#', 'ruby', 'go', 'rust', 'swift', 'kotlin', 'scala', 'perl', 'php', 'r', 'matlab',
            # Web Technologies
            'html', 'css', 'react', 'angular', 'vue', 'node', 'express', 'django', 'flask', 'spring', 'laravel', 'rails', 'next.js', 'gatsby',
            # Databases
            'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'sqlite', 'oracle', 'cassandra', 'dynamodb', 'elasticsearch',
            # Cloud & DevOps
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'gitlab', 'terraform', 'ansible', 'ci/cd', 'devops',
            # AI/ML
            'tensorflow', 'pytorch', 'keras', 'scikit-learn', 'pandas', 'numpy', 'opencv', 'nlp', 'machine learning', 'deep learning', 'ai', 'yolo', 'tesseract',
            # Tools & Frameworks
            'git', 'github', 'gitlab', 'vscode', 'intellij', 'eclipse', 'postman', 'jira', 'slack', 'power bi', 'tableau', 'excel',
            # Mobile
            'android', 'ios', 'react native', 'flutter', 'swift', 'kotlin',
            # Testing
            'jest', 'mocha', 'selenium', 'junit', 'pytest', 'cypress',
            # Other
            'linux', 'ubuntu', 'windows', 'macos', 'agile', 'scrum', 'rest', 'graphql', 'microservices', 'api', 'json', 'xml'
        ]
        
        # Extract from text using multiple methods
        text_lower = text.lower()
        
        # Method 1: Direct keyword matching
        for keyword in tech_keywords:
            if keyword in text_lower:
                skills.append(keyword)
        
        # Method 2: NLP entity extraction
        for token in doc:
            if token.text.lower() in tech_keywords:
                skills.append(token.text.lower())
        
        # Method 3: Extract noun phrases that might be skills
        for chunk in doc.noun_chunks:
            chunk_text = chunk.text.lower()
            if len(chunk_text.split()) <= 3 and any(keyword in chunk_text for keyword in tech_keywords):
                skills.append(chunk.text.lower())
        
        # Method 4: Pattern-based extraction for common skill formats
        skill_patterns = [
            r'\b(?:experienced?|skilled?|proficient?|knowledge(?: of)?|familiar with)\s+in\s+([a-zA-Z\s]{2,30})\b',
            r'\b([a-zA-Z\s]{2,30})\s+(?:experience|skills?|knowledge|expertise)\b',
            r'\b(?:using|with|utilizing)\s+([a-zA-Z\s]{2,30})\b'
        ]
        
        for pattern in skill_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                match_skills = [skill.strip().lower() for skill in match.split() if skill.strip().lower() in tech_keywords]
                skills.extend(match_skills)
        
        return list(set(skills))
    
    def _extract_skills_fallback(self, text: str) -> List[str]:
        """Fallback skill extraction without NLP"""
        tech_keywords = [
            'python', 'java', 'javascript', 'react', 'node', 'sql', 'aws', 'docker',
            'kubernetes', 'git', 'linux', 'html', 'css', 'angular', 'vue', 'mongodb',
            'postgresql', 'mysql', 'tensorflow', 'pytorch', 'machine learning', 'ai',
            'data science', 'analytics', 'devops', 'ci/cd', 'agile', 'scrum',
            'c++', 'c#', 'ruby', 'go', 'php', 'typescript', 'django', 'flask',
            'express', 'mongodb', 'redis', 'opencv', 'pandas', 'numpy', 'scikit-learn'
        ]
        
        text_lower = text.lower()
        skills = []
        
        for keyword in tech_keywords:
            if keyword in text_lower:
                skills.append(keyword)
        
        return list(set(skills))
    
    def _extract_experience(self, sections: List[ResumeSection]) -> List[str]:
        """Extract experience information"""
        experience_texts = []
        for section in sections:
            if section.title.lower() in ['experience', 'work', 'employment', 'professional']:
                experience_texts.append(section.content)
        return experience_texts
    
    def _extract_education(self, sections: List[ResumeSection]) -> List[str]:
        """Extract education information"""
        education_texts = []
        for section in sections:
            if section.title.lower() in ['education', 'academic', 'qualification']:
                education_texts.append(section.content)
        return education_texts
    
    def _extract_contact_info(self, text: str) -> Dict[str, str]:
        """Extract contact information"""
        contact_info = {}
        
        # Email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        if emails:
            contact_info['email'] = emails[0]
        
        # Phone
        phone_pattern = r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        phones = re.findall(phone_pattern, text)
        if phones:
            contact_info['phone'] = phones[0]
        
        # LinkedIn
        linkedin_pattern = r'linkedin\.com/in/[\w-]+'
        linkedin = re.findall(linkedin_pattern, text)
        if linkedin:
            contact_info['linkedin'] = linkedin[0]
        
        return contact_info
    
    def _extract_name(self, text: str) -> str:
        """Extract the candidate's name from the resume."""
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        # Ignore lines that are very likely contact info or headers
        ignore_patterns = re.compile(r'(resume|cv|curriculum|vitae|email|phone|address|linkedin|http|www\.|\d)', re.IGNORECASE)

        # Restrict to first 5 lines (where name usually appears)
        for line in lines[:5]:
            if ignore_patterns.search(line):
                continue

            # Prefer all-uppercase names (common in resumes)
            if line.isupper() and 1 < len(line.split()) <= 5:
                return line

            # Prefer proper noun style names (e.g., "Abhirami T")
            words = line.split()
            if 1 < len(words) <= 5 and all(re.match(r'^[A-Z][a-zA-Z\-\.]+$', w) for w in words):
                return line

        # Fallback: first plausible line in the first 5
        for line in lines[:5]:
            if ignore_patterns.search(line):
                continue
            words = line.split()
            if 1 < len(words) <= 6:
                return line

        return ""  # Return empty if no candidate name is found
