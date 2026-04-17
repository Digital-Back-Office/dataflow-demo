import re
from typing import Dict, List, Tuple, Set
from collections import Counter
from dataclasses import dataclass

@dataclass
class SkillAnalysis:
    soft_skills: Dict[str, int]
    hard_skills: Dict[str, int]
    missing_soft_skills: List[str]
    missing_hard_skills: List[str]
    skill_categories: Dict[str, int]

class ResumeAnalyzer:
    """Enhanced resume analyzer for ATS dashboard"""
    
    # Soft skills dictionary
    SOFT_SKILLS = {
        'communication': ['communication', 'communicating', 'presenting', 'public speaking', 'writing', 'listening'],
        'teamwork': ['teamwork', 'collaboration', 'collaborative', 'team player', 'cooperation', 'partnership'],
        'leadership': ['leadership', 'leading', 'managing', 'management', 'supervision', 'mentoring', 'coaching'],
        'problem_solving': ['problem solving', 'analytical', 'analysis', 'critical thinking', 'troubleshooting', 'debugging'],
        'creativity': ['creative', 'innovation', 'innovative', 'designing', 'ideation', 'brainstorming'],
        'adaptability': ['adaptable', 'flexible', 'versatile', 'agile', 'quick learner', 'fast learning'],
        'time_management': ['time management', 'organization', 'prioritization', 'planning', 'scheduling', 'deadline'],
        'attention_to_detail': ['detail oriented', 'meticulous', 'thorough', 'precise', 'accurate', 'quality focused']
    }
    
    # Hard skills categories
    HARD_SKILL_CATEGORIES = {
        'Programming': ['python', 'java', 'javascript', 'c++', 'c#', 'go', 'rust', 'swift', 'kotlin', 'php', 'ruby'],
        'Web Development': ['react', 'angular', 'vue', 'nodejs', 'express', 'django', 'flask', 'spring', 'laravel'],
        'Databases': ['sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'oracle', 'cassandra'],
        'Cloud & DevOps': ['aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'gitlab', 'terraform', 'ansible'],
        'AI/ML': ['tensorflow', 'pytorch', 'keras', 'scikit-learn', 'nlp', 'computer vision', 'deep learning', 'machine learning'],
        'Mobile': ['ios', 'android', 'react native', 'flutter', 'swiftui', 'kotlin', 'java', 'cordova'],
        'Tools & Others': ['git', 'github', 'gitlab', 'jira', 'confluence', 'slack', 'excel', 'linux', 'agile', 'scrum']
    }
    
    def __init__(self):
        self.soft_skill_patterns = self._create_skill_patterns(self.SOFT_SKILLS)
        self.hard_skill_patterns = self._create_skill_patterns(self.HARD_SKILL_CATEGORIES)
    
    def _create_skill_patterns(self, skill_dict: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Create regex patterns for skills"""
        patterns = {}
        for category, skills in skill_dict.items():
            patterns[category] = [r'\b' + re.escape(skill) + r'\b' for skill in skills]
        return patterns
    
    def extract_soft_skills(self, text: str) -> Dict[str, int]:
        """Extract soft skills from text"""
        text_lower = text.lower()
        found_skills = {}
        
        for category, patterns in self.soft_skill_patterns.items():
            count = 0
            for pattern in patterns:
                matches = re.findall(pattern, text_lower)
                count += len(matches)
            
            if count > 0:
                found_skills[category] = count
        
        return found_skills
    
    def extract_hard_skills(self, text: str) -> Dict[str, int]:
        """Extract hard skills from text"""
        text_lower = text.lower()
        found_skills = {}
        
        for category, patterns in self.hard_skill_patterns.items():
            count = 0
            for pattern in patterns:
                matches = re.findall(pattern, text_lower)
                count += len(matches)
            
            if count > 0:
                found_skills[category] = count
        
        return found_skills
    
    def compare_skills(self, resume_skills: Dict[str, int], job_skills: Dict[str, int]) -> Tuple[List[str], List[str]]:
        """Compare skills between resume and job description"""
        resume_skill_set = set(resume_skills.keys())
        job_skill_set = set(job_skills.keys())
        
        missing_skills = list(job_skill_set - resume_skill_set)
        present_skills = list(resume_skill_set & job_skill_set)
        
        return missing_skills, present_skills
    
    def analyze_resume_quality(self, resume_text: str) -> Dict[str, bool]:
        """Analyze resume quality metrics"""
        quality_checks = {}
        
        # Word count
        words = resume_text.split()
        quality_checks['word_count'] = len(words) >= 300
        
        # Contact information
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        quality_checks['has_email'] = bool(re.search(email_pattern, resume_text))
        quality_checks['has_phone'] = bool(re.search(phone_pattern, resume_text))
        
        # Section headers
        quality_checks['has_experience'] = bool(re.search(r'\b(experience|work|employment|career)\b', resume_text.lower()))
        quality_checks['has_education'] = bool(re.search(r'\b(education|academic|degree|university|college)\b', resume_text.lower()))
        quality_checks['has_skills'] = bool(re.search(r'\b(skills|technical|expertise|competencies)\b', resume_text.lower()))
        
        return quality_checks
    
    def extract_keywords_from_jd(self, job_text: str) -> List[str]:
        """Extract important keywords from job description"""
        # Common technical and business keywords
        keyword_patterns = [
            r'\b(applications?|software|systems?|platforms?|solutions?)\b',
            r'\b(development|programming|coding|engineering|design)\b',
            r'\b(full.?stack|frontend|backend|database|cloud)\b',
            r'\b(management|leadership|coordination|planning)\b',
            r'\b(analytics?|analysis|reporting|insights?)\b',
            r'\b(automation|optimization|performance|efficiency)\b',
            r'\b(integration|deployment|maintenance|support)\b',
            r'\b(collaboration|communication|teamwork|partnership)\b',
            r'\b(innovation|research|strategy|architecture)\b'
        ]
        
        keywords = set()
        text_lower = job_text.lower()
        
        for pattern in keyword_patterns:
            matches = re.findall(pattern, text_lower)
            keywords.update(matches)
        
        # Also extract individual technical terms
        technical_terms = self._extract_technical_terms(job_text)
        keywords.update(technical_terms)
        
        return list(keywords)[:20]  # Limit to top 20 keywords
    
    def _extract_technical_terms(self, text: str) -> List[str]:
        """Extract technical terms from text"""
        technical_patterns = [
            r'\b[A-Za-z]+(?:\.js|\.py|\.java|\.cpp|\.cs|\.go|\.rs)\b',  # File extensions
            r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b',  # CamelCase terms
            r'\b\w+(?:[-_]\w+)+\b',  # Kebab-case or snake_case terms
            r'\b[A-Z]{2,}\b'  # Acronyms
        ]
        
        terms = set()
        text_lower = text.lower()
        
        for pattern in technical_patterns:
            matches = re.findall(pattern, text)
            terms.update([match.lower() for match in matches if len(match) > 2])
        
        return list(terms)
    
    def calculate_keyword_density(self, resume_text: str, keywords: List[str]) -> Dict[str, int]:
        """Calculate keyword density in resume"""
        text_lower = resume_text.lower()
        density = {}
        
        for keyword in keywords:
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            matches = re.findall(pattern, text_lower)
            density[keyword] = len(matches)
        
        return density
    
    def analyze_ats_compatibility(self, resume_text: str) -> Dict[str, bool]:
        """Analyze ATS compatibility factors"""
        compatibility_checks = {}
        
        # Complex formatting issues
        compatibility_checks['no_tables'] = not bool(re.search(r'\|.*\|', resume_text))
        compatibility_checks['no_special_chars'] = not bool(re.search(r'[^\w\s\-\.\,\;\:\(\)\[\]\/]', resume_text))
        compatibility_checks['standard_headers'] = bool(re.search(r'^(experience|skills|education|projects)', resume_text, re.MULTILINE | re.IGNORECASE))
        
        # Length check
        words = resume_text.split()
        compatibility_checks['appropriate_length'] = 300 <= len(words) <= 700
        
        # Keyword optimization
        compatibility_checks['keyword_optimization'] = True  # Would be calculated based on job keywords
        
        return compatibility_checks
    
    def simulate_ats_parsing(self, resume_text: str, parsed_resume: Dict) -> Dict[str, List[str]]:
        """Simulate how ATS parses resume"""
        parsed_data = {
            'contact': [],
            'skills': [],
            'experience': [],
            'education': []
        }
        
        # Extract contact information
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', resume_text)
        phone_match = re.search(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', resume_text)
        name_match = re.search(r'^([A-Z][a-z]+ [A-Z][a-z]+)', resume_text, re.MULTILINE)
        
        if name_match:
            parsed_data['contact'].append(f"Name detected: {name_match.group(1)}")
        if email_match:
            parsed_data['contact'].append(f"Email detected: {email_match.group(0)}")
        if phone_match:
            parsed_data['contact'].append(f"Phone detected: {phone_match.group(0)}")
        
        # Extract skills (from parsed resume if available)
        if parsed_resume and hasattr(parsed_resume, 'skills'):
            parsed_data['skills'] = parsed_resume.skills[:10]  # Limit to first 10
        
        # Extract experience
        if parsed_resume and hasattr(parsed_resume, 'sections'):
            for section in parsed_resume.sections:
                if 'experience' in section.title.lower():
                    for item in section.content[:3]:  # Limit to first 3
                        if hasattr(item, 'title') and hasattr(item, 'organization'):
                            parsed_data['experience'].append(f"{item.title} – {item.organization}")
        
        # Extract education
        if parsed_resume and hasattr(parsed_resume, 'sections'):
            for section in parsed_resume.sections:
                if 'education' in section.title.lower():
                    for item in section.content[:2]:  # Limit to first 2
                        if hasattr(item, 'title'):
                            parsed_data['education'].append(item.title)
        
        return parsed_data
