from typing import Dict, List, Tuple
from dataclasses import dataclass
import re
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np
from src.resume_parser import ParsedResume
from src.job_parser import JobRequirements

@dataclass
class KeywordGap:
    missing_critical: List[str]
    missing_important: List[str]
    weak_keywords: List[str]
    overused_keywords: List[str]
    suggested_additions: List[Tuple[str, str]]  # (keyword, context)
    keyword_density_map: Dict[str, float]

class KeywordAnalyzer:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=500,
            stop_words='english',
            ngram_range=(1, 2),
            lowercase=True
        )
    
    def analyze_keyword_gaps(self, resume: ParsedResume, job: JobRequirements) -> KeywordGap:
        """Comprehensive keyword gap analysis"""
        
        # Extract all keywords from both sources
        resume_keywords = self._extract_resume_keywords(resume)
        job_keywords = self._extract_job_keywords(job)
        
        # Categorize job keywords by importance
        critical_keywords, important_keywords = self._categorize_keywords(job)
        
        # Find gaps
        missing_critical = self._find_missing_keywords(resume_keywords, critical_keywords)
        missing_important = self._find_missing_keywords(resume_keywords, important_keywords)
        
        # Analyze keyword density
        density_map = self._calculate_keyword_density(resume, job_keywords)
        weak_keywords = self._identify_weak_keywords(density_map)
        overused_keywords = self._identify_overused_keywords(density_map)
        
        # Suggest additions with context
        suggested_additions = self._suggest_keyword_additions(
            missing_critical + missing_important, job
        )
        
        return KeywordGap(
            missing_critical=missing_critical,
            missing_important=missing_important,
            weak_keywords=weak_keywords,
            overused_keywords=overused_keywords,
            suggested_additions=suggested_additions,
            keyword_density_map=density_map
        )
    
    def _extract_resume_keywords(self, resume: ParsedResume) -> List[str]:
        """Extract keywords from resume"""
        # Combine all text sources
        all_text = resume.full_text + ' ' + ' '.join(resume.skills) + ' ' + ' '.join(resume.experience)
        
        # Use TF-IDF to extract important terms
        try:
            tfidf_matrix = self.vectorizer.fit_transform([all_text])
            feature_names = self.vectorizer.get_feature_names_out()
            tfidf_scores = tfidf_matrix.toarray()[0]
            
            # Get top keywords by TF-IDF score
            keyword_scores = list(zip(feature_names, tfidf_scores))
            keyword_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Filter meaningful keywords
            meaningful_keywords = []
            for keyword, score in keyword_scores:
                if self._is_meaningful_keyword(keyword):
                    meaningful_keywords.append(keyword.lower())
            
            return meaningful_keywords[:50]  # Top 50 keywords
            
        except:
            # Fallback to simple extraction
            return self._simple_keyword_extraction(all_text)
    
    def _extract_job_keywords(self, job: JobRequirements) -> List[str]:
        """Extract keywords from job description"""
        all_text = (
            job.raw_text + ' ' +
            ' '.join(job.required_skills) + ' ' +
            ' '.join(job.preferred_skills) + ' ' +
            ' '.join(job.responsibilities) + ' ' +
            ' '.join(job.keywords)
        )
        
        return self._simple_keyword_extraction(all_text)
    
    def _simple_keyword_extraction(self, text: str) -> List[str]:
        """Simple keyword extraction as fallback"""
        # Extract words and clean them
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Remove common stop words
        stop_words = {
            'the', 'and', 'for', 'are', 'with', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 
            'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 
            'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'use', 'her', 'let', 'put', 
            'say', 'she', 'too', 'job', 'work', 'will', 'from', 'they', 'know', 'want', 'been', 
            'good', 'much', 'some', 'time', 'very', 'when', 'come', 'here', 'just', 'like', 
            'long', 'make', 'many', 'over', 'such', 'take', 'than', 'them', 'well', 'were'
        }
        
        filtered_words = [word for word in words if word not in stop_words]
        
        # Count frequency and return most common
        word_counts = Counter(filtered_words)
        return [word for word, count in word_counts.most_common(50)]
    
    def _is_meaningful_keyword(self, keyword: str) -> bool:
        """Check if keyword is meaningful for professional context"""
        # Technical and professional indicators
        tech_indicators = [
            'python', 'java', 'javascript', 'sql', 'aws', 'docker', 'kubernetes', 'git',
            'react', 'node', 'angular', 'vue', 'mongodb', 'postgresql', 'mysql', 'linux',
            'azure', 'gcp', 'terraform', 'jenkins', 'ci', 'cd', 'api', 'rest', 'graphql',
            'machine', 'learning', 'data', 'science', 'analytics', 'ai', 'ml', 'dl'
        ]
        
        professional_indicators = [
            'management', 'leadership', 'development', 'design', 'analysis', 'strategy',
            'marketing', 'sales', 'finance', 'accounting', 'operations', 'project',
            'product', 'engineering', 'research', 'consulting', 'business', 'technical'
        ]
        
        keyword_lower = keyword.lower().strip()

        # Filter out recruiter-focused phrases and generic placeholders
        blacklist = {
            'the software engineer',
            'a software engineer',
            'our ideal candidates',
            'ideal candidate',
            'candidate',
            'candidates'
        }
        if keyword_lower in blacklist:
            return False

        # Check if it contains tech or professional terms
        has_tech = any(indicator in keyword_lower for indicator in tech_indicators)
        has_professional = any(indicator in keyword_lower for indicator in professional_indicators)
        
        # Check for common professional suffixes/prefixes
        professional_patterns = [
            r'.*ing$', r'.*ment$', r'.*tion$', r'.*sion$', r'.*ity$', r'.*ness$',
            r'.*er$', r'.*or$', r'.*ist$', r'.*ism$', r'.*ify$', r'.*ize$'
        ]
        
        has_professional_pattern = any(re.match(pattern, keyword_lower) for pattern in professional_patterns)
        
        # Length check (avoid very short or very long)
        appropriate_length = 3 <= len(keyword) <= 20
        
        return (has_tech or has_professional or has_professional_pattern) and appropriate_length
    
    def _categorize_keywords(self, job: JobRequirements) -> Tuple[List[str], List[str]]:
        """Categorize job keywords by importance"""
        critical_keywords = []
        important_keywords = []
        
        # Required skills are critical
        critical_keywords.extend(job.required_skills)
        
        # Add keywords from responsibilities (often critical)
        for resp in job.responsibilities:
            resp_keywords = self._simple_keyword_extraction(resp)
            critical_keywords.extend(resp_keywords[:5])  # Top 5 from each responsibility
        
        # Preferred skills are important but not critical
        important_keywords.extend(job.preferred_skills)
        
        # Add remaining keywords from general keyword list
        for keyword in job.keywords:
            keyword_lower = keyword.lower()
            if keyword_lower not in [k.lower() for k in critical_keywords + important_keywords]:
                if self._is_meaningful_keyword(keyword):
                    important_keywords.append(keyword)
        
        # Remove duplicates and clean
        critical_keywords = list(set(k.lower() for k in critical_keywords if k.strip()))
        important_keywords = list(set(k.lower() for k in important_keywords if k.strip()))
        
        # Remove any important keywords that are already in critical
        important_keywords = [k for k in important_keywords if k not in critical_keywords]
        
        return critical_keywords[:20], important_keywords[:30]  # Limit counts
    
    def _find_missing_keywords(self, resume_keywords: List[str], job_keywords: List[str]) -> List[str]:
        """Find keywords missing from resume"""
        resume_set = set(resume_keywords)
        job_set = set(job_keywords)
        
        missing = list(job_set - resume_set)
        
        # Sort by importance (you could add more sophisticated ranking here)
        return sorted(missing, key=lambda x: len(x), reverse=True)
    
    def _calculate_keyword_density(self, resume: ParsedResume, job_keywords: List[str]) -> Dict[str, float]:
        """Calculate keyword density in resume"""
        resume_text = resume.full_text.lower()
        total_words = len(resume_text.split())
        
        if total_words == 0:
            return {}
        
        density_map = {}
        
        for keyword in job_keywords:
            keyword_lower = keyword.lower()
            # Count occurrences (handle multi-word keywords)
            occurrences = len(re.findall(rf'\b{re.escape(keyword_lower)}\b', resume_text))
            density = (occurrences / total_words) * 100
            density_map[keyword_lower] = density
        
        return density_map
    
    def _identify_weak_keywords(self, density_map: Dict[str, float]) -> List[str]:
        """Identify keywords with low density"""
        weak_keywords = []
        
        for keyword, density in density_map.items():
            if 0 < density < 0.5:  # Present but very low density
                weak_keywords.append(keyword)
        
        return sorted(weak_keywords, key=lambda k: density_map[k])[:10]
    
    def _identify_overused_keywords(self, density_map: Dict[str, float]) -> List[str]:
        """Identify potentially overused keywords"""
        overused_keywords = []
        
        for keyword, density in density_map.items():
            if density > 5.0:  # More than 5% density might be keyword stuffing
                overused_keywords.append(keyword)
        
        return sorted(overused_keywords, key=lambda k: density_map[k], reverse=True)[:5]
    
    def _suggest_keyword_additions(self, missing_keywords: List[str], job: JobRequirements) -> List[Tuple[str, str]]:
        """Suggest where to add missing keywords"""
        suggestions = []
        
        for keyword in missing_keywords[:10]:  # Top 10 suggestions
            context = self._find_best_context(keyword, job)
            suggestions.append((keyword, context))
        
        return suggestions
    
    def _find_best_context(self, keyword: str, job: JobRequirements) -> str:
        """Find the best context to add a keyword"""
        keyword_lower = keyword.lower()
        
        # Check if it's mentioned in responsibilities
        for resp in job.responsibilities:
            if keyword_lower in resp.lower():
                return f"Add to experience section: {resp[:100]}..."
        
        # Check if it's in required skills
        for skill in job.required_skills:
            if keyword_lower in skill.lower():
                return f"Add to skills section as: {skill}"
        
        # Check if it's in preferred skills
        for skill in job.preferred_skills:
            if keyword_lower in skill.lower():
                return f"Add to skills section as: {skill}"
        
        # Default suggestion
        return "Add to relevant experience or skills section"
