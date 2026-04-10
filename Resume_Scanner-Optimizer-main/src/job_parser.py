import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Any
from dataclasses import dataclass
import spacy

@dataclass
class JobRequirements:
    title: str
    required_skills: List[str]
    preferred_skills: List[str]
    experience_level: str
    education_requirements: List[str]
    responsibilities: List[str]
    keywords: List[str]
    company_info: Dict[str, str]
    raw_text: str

class JobDescriptionParser:
    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("spaCy model not found. Please run: python -m spacy download en_core_web_sm")
            self.nlp = None
    
    def parse_job_description(self, job_input: str, is_url: bool = False) -> JobRequirements:
        """Parse job description from text or URL"""
        if is_url:
            text = self._fetch_job_from_url(job_input)
        else:
            text = job_input
        
        return self._parse_job_text(text)
    
    def _fetch_job_from_url(self, url: str) -> str:
        """Fetch job description from URL"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Try to find main job description content
            job_content = ""
            
            # Common selectors for job descriptions
            selectors = [
                '.job-description',
                '.description',
                '[data-testid="job-description"]',
                '.jobsearch-JobComponent-description',
                '#job-description',
                '.job-details'
            ]
            
            for selector in selectors:
                element = soup.select_one(selector)
                if element:
                    job_content = element.get_text(separator='\n', strip=True)
                    break
            
            # Fallback to main content if specific selectors don't work
            if not job_content:
                job_content = soup.get_text(separator='\n', strip=True)
            
            return job_content
            
        except Exception as e:
            raise Exception(f"Error fetching job description from URL: {str(e)}")
    
    def _parse_job_text(self, text: str) -> JobRequirements:
        """Parse job description text into structured data"""
        # Clean the text first
        text = self._clean_text(text)
        
        title = self._extract_job_title(text)
        required_skills = self._extract_required_skills(text)
        preferred_skills = self._extract_preferred_skills(text)
        experience_level = self._extract_experience_level(text)
        education_requirements = self._extract_education_requirements(text)
        responsibilities = self._extract_responsibilities(text)
        keywords = self._extract_keywords(text)
        company_info = self._extract_company_info(text)
        
        return JobRequirements(
            title=title,
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            experience_level=experience_level,
            education_requirements=education_requirements,
            responsibilities=responsibilities,
            keywords=keywords,
            company_info=company_info,
            raw_text=text
        )
    
    def _clean_text(self, text: str) -> str:
        """Clean text by removing bullet points and special characters"""
        import re
        
        # Remove bullet points and list markers
        text = re.sub(r'^[\s]*[•·\-\*]\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[\s]*\d+\.\s*', '', text, flags=re.MULTILINE)
        
        # Remove extra whitespace
        text = re.sub(r'\n\s*\n', '\n', text)
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _extract_job_title(self, text: str) -> str:
        """Extract job title from description"""
        lines = text.split('\n')
        
        # Look for job title in first few lines
        for i, line in enumerate(lines[:10]):
            line = line.strip()
            if len(line) > 5 and len(line) < 100:
                # Common job title patterns
                title_patterns = [
                    r'(?:senior|junior|lead|principal|staff|associate)\s+[\w\s]+',
                    r'[\w\s]+(?:engineer|developer|manager|analyst|specialist|consultant)',
                    r'[\w\s]+(?:director|vp|vice president|head|chief)'
                ]
                
                for pattern in title_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        return line
        
        return "Unknown Position"
    
    def _extract_required_skills(self, text: str) -> List[str]:
        """Extract required skills from job description"""
        required_section = self._extract_section_by_keywords(
            text, 
            ['required', 'must have', 'qualifications', 'requirements']
        )
        
        return self._extract_skills_from_text(required_section)
    
    def _extract_preferred_skills(self, text: str) -> List[str]:
        """Extract preferred/nice-to-have skills"""
        preferred_section = self._extract_section_by_keywords(
            text,
            ['preferred', 'nice to have', 'bonus', 'plus', 'desired']
        )
        
        return self._extract_skills_from_text(preferred_section)
    
    def _extract_section_by_keywords(self, text: str, keywords: List[str]) -> str:
        """Extract specific section based on keywords"""
        lines = text.split('\n')
        section_lines = []
        in_section = False
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Check if we're entering the target section
            for keyword in keywords:
                if keyword in line_lower:
                    in_section = True
                    break
            
            if in_section:
                section_lines.append(line)
                
                # Exit section if we hit another major section
                if any(section_word in line_lower for section_word in 
                      ['responsibilities', 'about', 'company', 'benefits', 'salary']):
                    if len(section_lines) > 1:  # Don't exit immediately
                        break
        
        return '\n'.join(section_lines)
    
    def _extract_skills_from_text(self, text: str) -> List[str]:
        """Extract skills from given text"""
        if not self.nlp:
            return []
        
        doc = self.nlp(text)
        skills = []
        
        # Comprehensive skill keywords
        skill_keywords = {
            'programming': ['python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'go', 'rust', 'php', 'ruby'],
            'web': ['react', 'angular', 'vue', 'node', 'express', 'django', 'flask', 'spring', 'laravel'],
            'databases': ['sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'cassandra'],
            'cloud': ['aws', 'azure', 'gcp', 'google cloud', 'heroku', 'digitalocean'],
            'devops': ['docker', 'kubernetes', 'jenkins', 'gitlab', 'ci/cd', 'terraform', 'ansible'],
            'tools': ['git', 'jira', 'confluence', 'slack', 'vscode', 'intellij'],
            'concepts': ['agile', 'scrum', 'kanban', 'tdd', 'bdd', 'microservices', 'rest api', 'graphql'],
            'data': ['machine learning', 'data science', 'analytics', 'tensorflow', 'pytorch', 'pandas', 'numpy']
        }
        
        text_lower = text.lower()
        
        # Find skill matches
        for category, skill_list in skill_keywords.items():
            for skill in skill_list:
                if skill in text_lower:
                    skills.append(skill)
        
        # Extract entities that might be skills
        for ent in doc.ents:
            if ent.label_ in ['PRODUCT', 'ORG', 'PERSON'] and len(ent.text.split()) <= 3:
                if any(char.isupper() for char in ent.text):  # Likely a proper noun/technology
                    skills.append(ent.text.lower())
        
        return list(set(skills))
    
    def _extract_experience_level(self, text: str) -> str:
        """Extract required experience level"""
        experience_patterns = [
            (r'(\d+)\+?\s*years?', lambda m: f"{m.group(1)}+ years"),
            (r'entry\s*level|junior|associate', lambda _: "Entry Level"),
            (r'mid\s*level|intermediate', lambda _: "Mid Level"),
            (r'senior|lead|principal', lambda _: "Senior Level"),
            (r'director|vp|vice president|head|chief', lambda _: "Executive Level")
        ]
        
        text_lower = text.lower()
        for pattern, extractor in experience_patterns:
            match = re.search(pattern, text_lower)
            if match:
                return extractor(match)
        
        return "Not specified"
    
    def _extract_education_requirements(self, text: str) -> List[str]:
        """Extract education requirements"""
        education_keywords = [
            'bachelor', 'master', 'phd', 'degree', 'diploma', 'certification',
            'computer science', 'engineering', 'business', 'mba'
        ]
        
        text_lower = text.lower()
        education_found = []
        
        for keyword in education_keywords:
            if keyword in text_lower:
                education_found.append(keyword)
        
        return education_found
    
    def _extract_responsibilities(self, text: str) -> List[str]:
        """Extract job responsibilities"""
        responsibilities_section = self._extract_section_by_keywords(
            text,
            ['responsibilities', 'duties', 'what you\'ll do', 'role']
        )
        
        # Extract bullet points
        bullet_points = []
        lines = responsibilities_section.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith(('•', '-', '*', '·')) or line.startswith(('1.', '2.', '3.', '4.', '5.')):
                bullet_points.append(line)
        
        return bullet_points
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract all relevant keywords"""
        if not self.nlp:
            return []
        
        doc = self.nlp(text)
        keywords = []
        
        # Extract important nouns and proper nouns
        for token in doc:
            if (token.pos_ in ['NOUN', 'PROPN'] and 
                not token.is_stop and 
                len(token.text) > 2 and
                token.text.isalpha()):
                keywords.append(token.text.lower())
        
        # Add bigrams and trigrams
        for chunk in doc.noun_chunks:
            if 2 <= len(chunk.text.split()) <= 3:
                keywords.append(chunk.text.lower())
        
        return list(set(keywords))
    
    def _extract_company_info(self, text: str) -> Dict[str, str]:
        """Extract company information"""
        company_info = {}
        
        # Look for company name (simplified)
        lines = text.split('\n')
        for line in lines[:5]:  # Usually in first few lines
            line = line.strip()
            if len(line) > 3 and len(line) < 50:
                if not any(word in line.lower() for word in ['job', 'position', 'title', 'location']):
                    company_info['name'] = line
                    break
        
        return company_info
