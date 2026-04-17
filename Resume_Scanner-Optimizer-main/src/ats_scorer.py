from typing import Dict, List, Tuple
from dataclasses import dataclass
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from src.resume_parser import ParsedResume
from src.job_parser import JobRequirements
from src.config import Config

@dataclass
class ATSScore:
    overall_score: float
    skill_match_score: float
    experience_match_score: float
    keyword_density_score: float
    format_compatibility_score: float
    detailed_breakdown: Dict[str, any]
    recommendations: List[str]

class ATSScorer:
    def __init__(self):
        self.config = Config()
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
    
    def calculate_ats_score(self, resume: ParsedResume, job: JobRequirements) -> ATSScore:
        """Calculate comprehensive ATS score"""
        
        # Calculate individual components
        skill_score = self._calculate_skill_match_score(resume, job)
        experience_score = self._calculate_experience_match_score(resume, job)
        keyword_score = self._calculate_keyword_density_score(resume, job)
        format_score = self._calculate_format_compatibility_score(resume)
        
        # Calculate weighted overall score
        overall_score = (
            skill_score * self.config.SKILL_MATCH_WEIGHT +
            experience_score * self.config.EXPERIENCE_MATCH_WEIGHT +
            keyword_score * self.config.KEYWORD_DENSITY_WEIGHT +
            format_score * self.config.FORMAT_COMPATIBILITY_WEIGHT
        )
        
        # Generate detailed breakdown
        breakdown = self._generate_detailed_breakdown(resume, job)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(resume, job, breakdown)
        
        return ATSScore(
            overall_score=round(overall_score, 2),
            skill_match_score=round(skill_score, 2),
            experience_match_score=round(experience_score, 2),
            keyword_density_score=round(keyword_score, 2),
            format_compatibility_score=round(format_score, 2),
            detailed_breakdown=breakdown,
            recommendations=recommendations
        )
    
    def _calculate_skill_match_score(self, resume: ParsedResume, job: JobRequirements) -> float:
        """Calculate skill matching score"""
        resume_skills = set(skill.lower() for skill in resume.skills)
        required_skills = set(skill.lower() for skill in job.required_skills)
        preferred_skills = set(skill.lower() for skill in job.preferred_skills)
        
        if not required_skills and not preferred_skills:
            return 50.0  # Neutral score if no skills found
        
        # Calculate matches
        required_matches = len(resume_skills & required_skills)
        preferred_matches = len(resume_skills & preferred_skills)
        
        # Weighted scoring (required skills more important)
        required_score = (required_matches / len(required_skills)) * 70 if required_skills else 35
        preferred_score = (preferred_matches / len(preferred_skills)) * 30 if preferred_skills else 15
        
        return min(required_score + preferred_score, 100.0)
    
    def _calculate_experience_match_score(self, resume: ParsedResume, job: JobRequirements) -> float:
        """Calculate experience relevance score"""
        if not resume.experience:
            return 20.0  # Low score if no experience found
        
        # Extract experience keywords from job
        job_experience_keywords = set()
        for resp in job.responsibilities:
            job_experience_keywords.update(self._extract_keywords_from_text(resp.lower()))
        
        # Calculate relevance of resume experience
        experience_text = ' '.join(resume.experience).lower()
        resume_experience_keywords = self._extract_keywords_from_text(experience_text)
        
        if not job_experience_keywords:
            return 60.0  # Neutral score
        
        matches = len(set(resume_experience_keywords) & job_experience_keywords)
        total_job_keywords = len(job_experience_keywords)
        
        return min((matches / total_job_keywords) * 100, 100.0) if total_job_keywords > 0 else 50.0
    
    def _calculate_keyword_density_score(self, resume: ParsedResume, job: JobRequirements) -> float:
        """Calculate keyword density and relevance score"""
        resume_text = resume.full_text.lower()
        job_keywords = set(keyword.lower() for keyword in job.keywords)
        
        if not job_keywords:
            return 50.0
        
        # Count keyword occurrences
        keyword_counts = {}
        total_words = len(resume_text.split())
        
        for keyword in job_keywords:
            keyword_counts[keyword] = len(re.findall(rf'\b{re.escape(keyword)}\b', resume_text))
        
        # Calculate density score
        if total_words == 0:
            return 20.0
        
        total_keyword_occurrences = sum(keyword_counts.values())
        keyword_density = (total_keyword_occurrences / total_words) * 100
        
        # Optimal density is around 2-5%
        if 2 <= keyword_density <= 5:
            density_score = 100.0
        elif keyword_density < 2:
            density_score = (keyword_density / 2) * 100
        else:
            density_score = max(100 - (keyword_density - 5) * 20, 20)
        
        # Bonus for covering diverse keywords
        keyword_coverage = len([k for k, v in keyword_counts.items() if v > 0])
        coverage_score = (keyword_coverage / len(job_keywords)) * 100
        
        return (density_score * 0.6 + coverage_score * 0.4)
    
    def _calculate_format_compatibility_score(self, resume: ParsedResume) -> float:
        """Check ATS formatting compatibility"""
        score = 100.0
        issues = []
        
        text = resume.full_text
        
        # Check for formatting issues
        if self._has_tables(text):
            score -= 20
            issues.append("Tables detected - may not parse well in ATS")
        
        if self._has_columns(text):
            score -= 15
            issues.append("Multi-column layout detected")
        
        if self._has_special_characters(text):
            score -= 10
            issues.append("Special characters that may cause parsing issues")
        
        if self._has_inconsistent_bullets(text):
            score -= 10
            issues.append("Inconsistent bullet point formatting")
        
        if self._has_headers_footers(text):
            score -= 5
            issues.append("Headers/footers detected")
        
        # Check for good practices
        if self._has_clear_sections(text):
            score += 5
        
        if self._has_proper_spacing(text):
            score += 5
        
        return max(min(score, 100.0), 0.0)
    
    def _extract_keywords_from_text(self, text: str) -> List[str]:
        """Extract keywords from text"""
        # Simple keyword extraction
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Filter out common words
        stop_words = {'the', 'and', 'for', 'are', 'with', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'use', 'her', 'let', 'put', 'say', 'she', 'too'}
        
        keywords = [word for word in words if word not in stop_words and len(word) > 3]
        
        # Return most common keywords
        from collections import Counter
        keyword_counts = Counter(keywords)
        return [kw for kw, count in keyword_counts.most_common(20)]
    
    def _has_tables(self, text: str) -> bool:
        """Check if text contains table-like structures"""
        lines = text.split('\n')
        consecutive_pipe_lines = 0
        
        for line in lines:
            if '|' in line and line.count('|') >= 2:
                consecutive_pipe_lines += 1
                if consecutive_pipe_lines >= 2:
                    return True
            else:
                consecutive_pipe_lines = 0
        
        return False
    
    def _has_columns(self, text: str) -> bool:
        """Check for multi-column layout indicators"""
        lines = text.split('\n')
        tab_counts = []
        
        for line in lines[:20]:  # Check first 20 lines
            tab_count = line.count('\t')
            if tab_count > 0:
                tab_counts.append(tab_count)
        
        if tab_counts:
            avg_tabs = sum(tab_counts) / len(tab_counts)
            return avg_tabs > 1  # Multiple tabs suggest columns
        
        return False
    
    def _has_special_characters(self, text: str) -> bool:
        """Check for problematic special characters"""
        problematic_chars = ['•', '→', '←', '↑', '↓', '★', '◆', '●', '■', '▲', '▼']
        return any(char in text for char in problematic_chars)
    
    def _has_inconsistent_bullets(self, text: str) -> bool:
        """Check for inconsistent bullet point formatting"""
        bullet_types = []
        lines = text.split('\n')
        
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith(('•', '-', '*', '·', '○', '■', '▪')):
                bullet_type = stripped[0]
                bullet_types.append(bullet_type)
        
        if len(set(bullet_types)) > 2:
            return True
        
        return False
    
    def _has_headers_footers(self, text: str) -> bool:
        """Check for potential headers/footers"""
        lines = text.split('\n')
        
        # Check for repeated patterns at top/bottom
        if len(lines) > 10:
            first_3 = lines[:3]
            last_3 = lines[-3:]
            
            # Simple check for similar content
            first_text = ' '.join(first_3).lower()
            last_text = ' '.join(last_3).lower()
            
            if len(first_text) > 20 and len(last_text) > 20:
                similarity = len(set(first_text.split()) & set(last_text.split())) / len(set(first_text.split()) | set(last_text.split()))
                if similarity > 0.5:
                    return True
        
        return False
    
    def _has_clear_sections(self, text: str) -> bool:
        """Check for clear section headers"""
        section_indicators = ['experience', 'education', 'skills', 'projects', 'summary']
        text_lower = text.lower()
        
        found_sections = sum(1 for indicator in section_indicators if indicator in text_lower)
        return found_sections >= 3
    
    def _has_proper_spacing(self, text: str) -> bool:
        """Check for proper spacing and formatting"""
        # Check for excessive blank lines
        lines = text.split('\n')
        blank_lines = sum(1 for line in lines if not line.strip())
        
        if blank_lines / len(lines) > 0.3:  # More than 30% blank lines
            return False
        
        # Check for very long lines (potential formatting issues)
        long_lines = sum(1 for line in lines if len(line) > 200)
        if long_lines / len(lines) > 0.1:  # More than 10% very long lines
            return False
        
        return True
    
    def _generate_detailed_breakdown(self, resume: ParsedResume, job: JobRequirements) -> Dict[str, any]:
        """Generate detailed breakdown analysis"""
        resume_skills = set(skill.lower() for skill in resume.skills)
        required_skills = set(skill.lower() for skill in job.required_skills)
        preferred_skills = set(skill.lower() for skill in job.preferred_skills)
        
        missing_required = list(required_skills - resume_skills)
        missing_preferred = list(preferred_skills - resume_skills)
        matched_required = list(resume_skills & required_skills)
        matched_preferred = list(resume_skills & preferred_skills)
        
        return {
            'total_resume_skills': len(resume.skills),
            'total_required_skills': len(required_skills),
            'total_preferred_skills': len(preferred_skills),
            'matched_required_skills': matched_required,
            'matched_preferred_skills': matched_preferred,
            'missing_required_skills': missing_required,
            'missing_preferred_skills': missing_preferred,
            'skill_match_percentage': len(matched_required) / len(required_skills) * 100 if required_skills else 0,
            'experience_sections_found': len(resume.experience),
            'education_sections_found': len(resume.education),
            'resume_word_count': len(resume.full_text.split()),
            'job_keyword_count': len(job.keywords)
        }
    
    def _generate_recommendations(self, resume: ParsedResume, job: JobRequirements, breakdown: Dict) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Skill-based recommendations
        if breakdown['missing_required_skills']:
            recommendations.append(
                f"Add these required skills: {', '.join(breakdown['missing_required_skills'][:5])}"
            )
        
        if breakdown['missing_preferred_skills']:
            recommendations.append(
                f"Consider adding these preferred skills: {', '.join(breakdown['missing_preferred_skills'][:3])}"
            )
        
        # Experience recommendations
        if breakdown['experience_sections_found'] == 0:
            recommendations.append("Add a clear experience section with detailed bullet points")
        
        # Keyword density recommendations
        if breakdown['resume_word_count'] < 300:
            recommendations.append("Resume appears too short - add more detail to experience and skills")
        elif breakdown['resume_word_count'] > 1000:
            recommendations.append("Resume is quite long - consider condensing to focus on most relevant experience")
        
        # Format recommendations
        if self._has_tables(resume.full_text):
            recommendations.append("Remove tables and convert to bullet points for better ATS parsing")
        
        if self._has_columns(resume.full_text):
            recommendations.append("Use single-column layout instead of multi-column format")
        
        return recommendations
