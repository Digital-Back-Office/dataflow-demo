import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from src.resume_parser import ParsedResume, ResumeSection
from src.ai_suggestions import SectionSuggestion
from src.ats_scorer import ATSScorer
from src.keyword_analyzer import KeywordAnalyzer
from src.job_parser import JobRequirements

@dataclass
class OptimizedResumeSection:
    title: str
    content: str
    bullet_points: List[str]
    keywords_added: List[str]
    improvements_made: List[str]

@dataclass
class OptimizedResume:
    name: str
    contact_info: str
    sections: List[OptimizedResumeSection]
    skills: Dict[str, List[str]]
    ats_score_improvement: float
    optimization_summary: str

class ResumeOptimizer:
    """Advanced resume optimizer that preserves structure while maximizing ATS score"""
    
    def __init__(self):
        self.ats_scorer = ATSScorer()
        self.keyword_analyzer = KeywordAnalyzer()
    
    def optimize_resume(self, resume: ParsedResume, job_requirements: JobRequirements, 
                      suggestions: Optional[List[SectionSuggestion]] = None) -> OptimizedResume:
        """Optimize resume while preserving ALL original content"""
        
        # Get original ATS score
        original_score = self.ats_scorer.calculate_ats_score(resume, job_requirements)
        
        print(f"🔍 Original ATS Score: {original_score.overall_score}%")
        print(f"🔍 Job requirements: {job_requirements.required_skills}")
        print(f"🔍 Job keywords: {job_requirements.keywords}")
        
        # Optimize each section with PRESERVATION focus - never remove original content
        optimized_sections = []
        
        for section in resume.sections:
            print(f"🔍 Processing section: {section.title}")
            optimized_section = self._optimize_section_preserve_content(section, job_requirements, suggestions)
            optimized_sections.append(optimized_section)
            print(f"🔍 Optimized section: {section.title} -> {len(optimized_section.keywords_added)} keywords added")
        
        # Optimize skills section by MERGING original skills with missing JD skills
        optimized_skills = self._merge_skills_clean(resume, job_requirements)
        
        # Keep original contact info - don't modify
        optimized_contact = resume.contact_info.copy() if resume.contact_info else {}
        
        print(f"🔍 Optimized contact name: {optimized_contact.get('name', 'NOT SET')}")
        print(f"🔍 Optimized contact phone: {optimized_contact.get('phone', 'NOT SET')}")
        print(f"🔍 Optimized contact email: {optimized_contact.get('email', 'NOT SET')}")
        
        # Reconstruct full_text with all optimizations - preserve original structure
        full_text = self._build_optimized_full_text(optimized_contact, optimized_sections, optimized_skills)
        
        print(f"🔍 Optimized contact: {optimized_contact}")
        print(f"🔍 Optimized skills: {optimized_skills}")
        
        optimized_resume = ParsedResume(
            full_text=full_text,
            sections=[self._convert_to_parsed_section(s) for s in optimized_sections],
            skills=self._flatten_skills(optimized_skills),
            experience=resume.experience,
            education=resume.education,
            contact_info=optimized_contact
        )
        
        # Calculate new ATS score using the OPTIMIZED resume
        print(f"🔍 Calculating ATS score using optimized resume...")
        new_score = self.ats_scorer.calculate_ats_score(optimized_resume, job_requirements)
        score_improvement = new_score.overall_score - original_score.overall_score
        
        print(f"🚀 OPTIMIZED RESUME ATS SCORE: {new_score.overall_score}%")
        print(f"🚀 SCORE IMPROVEMENT: +{score_improvement:.1f}%")
        
        # Create optimization summary
        optimization_summary = self._create_optimization_summary(
            optimized_sections, optimized_skills, score_improvement
        )
        
        return OptimizedResume(
            name=optimized_contact.get('name', 'ABHIRAMI T'),
            contact_info=self._format_contact_info(optimized_contact),
            sections=optimized_sections,
            skills=optimized_skills,
            ats_score_improvement=score_improvement,
            optimization_summary=optimization_summary
        )
    
    def _optimize_section_preserve_content(self, section: ResumeSection, job_requirements: JobRequirements,
                               suggestions: Optional[List[SectionSuggestion]]) -> OptimizedResumeSection:
        """Optimize section while PRESERVING ALL original content"""
        
        section_title_lower = section.title.lower()
        
        if 'experience' in section_title_lower:
            return self._optimize_experience_preserve(section, job_requirements)
        elif 'education' in section_title_lower:
            return self._optimize_education_preserve(section, job_requirements)
        elif 'skills' in section_title_lower:
            return self._optimize_skills_section_content_preserve(section, job_requirements)
        elif 'summary' in section_title_lower or 'objective' in section_title_lower:
            return self._optimize_summary_preserve(section, job_requirements)
        elif 'projects' in section_title_lower:
            return self._optimize_projects_preserve(section, job_requirements)
        else:
            return self._optimize_generic_section_preserve(section, job_requirements)
    
    def _optimize_experience_preserve(self, section: ResumeSection, job_requirements: JobRequirements) -> OptimizedResumeSection:
        """Optimize experience section while PRESERVING ALL original content"""
        
        # Get missing keywords that are relevant to experience
        all_keywords = job_requirements.required_skills + job_requirements.keywords
        
        print(f"🔧 Optimizing experience section with keywords: {all_keywords}")
        
        # PRESERVE ALL original bullets - never remove any
        enhanced_bullets = section.bullet_points.copy()  # Keep all original bullets
        keywords_added = []
        
        # Only enhance existing bullets by adding missing keywords naturally
        for i, bullet in enumerate(enhanced_bullets):
            enhanced_bullet = bullet
            
            # Find missing keywords that could fit naturally
            for keyword in all_keywords:
                if keyword.lower() not in enhanced_bullet.lower():
                    # Only add if it fits the context naturally
                    bullet_lower = enhanced_bullet.lower()
                    
                    # Check if bullet mentions development/programming
                    if any(tech in bullet_lower for tech in ['developed', 'built', 'created', 'implemented', 'designed', 'coded', 'programmed']):
                        if any(lang in keyword.lower() for lang in ['python', 'java', 'javascript', 'c++', 'go', 'rust', 'typescript']):
                            enhanced_bullets[i] = enhanced_bullet.rstrip('.') + f" using {keyword}."
                            keywords_added.append(keyword)
                            break
                    
                    # Check if bullet mentions data/cloud
                    elif any(data in bullet_lower for data in ['data', 'database', 'cloud', 'aws', 'azure', 'gcp']):
                        if any(cloud in keyword.lower() for cloud in ['aws', 'azure', 'gcp', 'docker', 'kubernetes']):
                            enhanced_bullets[i] = enhanced_bullet.rstrip('.') + f" with {keyword}."
                            keywords_added.append(keyword)
                            break
                    
                    # Check if bullet mentions analysis/ML
                    elif any(ml in bullet_lower for ml in ['machine learning', 'ml', 'ai', 'analysis', 'analytics']):
                        if any(ml_tech in keyword.lower() for ml_tech in ['tensorflow', 'pytorch', 'scikit-learn', 'pandas', 'numpy']):
                            enhanced_bullets[i] = enhanced_bullet.rstrip('.') + f" using {keyword}."
                            keywords_added.append(keyword)
                            break
        
        improvements = []
        if keywords_added:
            improvements.append(f"Enhanced existing bullets with keywords: {', '.join(set(keywords_added[:3]))}")

        print(f"🔧 Preserved {len(enhanced_bullets)} bullets, added keywords: {keywords_added}")

        return OptimizedResumeSection(
            title=section.title,
            content=section.content,
            bullet_points=enhanced_bullets,  # All original bullets preserved
            keywords_added=list(set(keywords_added)),
            improvements_made=improvements
        )
    
    def _merge_skills_clean(self, resume: ParsedResume, job_requirements: JobRequirements) -> Dict[str, List[str]]:
        """Merge original skills with missing JD skills - CLEAN approach"""
        
        def _is_clean_technical_skill(skill: str) -> bool:
            """Check if skill is a clean technical term"""
            if not skill or not isinstance(skill, str):
                return False
            sk = skill.strip().lower()
            
            # Block non-technical or sentence-like skills
            blocked = {
                'the software engineer', 'a software engineer', 'our ideal candidates',
                'software engineer', 'candidate', 'candidates', 'experience',
                'responsibilities', 'requirements', 'qualifications', 'skills',
                'ability', 'knowledge', 'understanding', 'familiarity',
                'strong', 'excellent', 'good', 'proven', 'demonstrated'
            }
            
            if sk in blocked or len(sk) > 30:
                return False
            
            # Only allow clean technical terms
            clean_tech = [
                # Programming Languages
                'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'go', 'rust',
                'scala', 'ruby', 'php', 'swift', 'kotlin', 'dart', 'r', 'matlab',
                
                # Web Technologies
                'html', 'css', 'react', 'angular', 'vue', 'node.js', 'express',
                'django', 'flask', 'spring', 'asp.net', 'jquery', 'bootstrap',
                
                # Databases
                'sql', 'mysql', 'postgresql', 'mongodb', 'oracle', 'sqlite',
                'redis', 'cassandra', 'elasticsearch',
                
                # Cloud & DevOps
                'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform',
                'jenkins', 'gitlab', 'github', 'bitbucket', 'ansible',
                
                # Data Science & ML
                'tensorflow', 'pytorch', 'scikit-learn', 'pandas', 'numpy',
                'matplotlib', 'seaborn', 'jupyter', 'spark', 'hadoop',
                
                # Tools & Frameworks
                'git', 'linux', 'ubuntu', 'windows', 'macos', 'bash', 'powershell',
                'vscode', 'intellij', 'eclipse', 'pycharm', 'vim', 'emacs',
                
                # Methodologies
                'agile', 'scrum', 'kanban', 'tdd', 'bdd', 'ci/cd', 'devops'
            ]
            
            return any(tech in sk for tech in clean_tech)
        
        # Get original skills from resume
        original_skills = resume.skills.copy()
        
        # Identify missing required skills that are clean technical terms
        all_required_skills = job_requirements.required_skills + job_requirements.keywords
        missing_clean_skills = [
            skill for skill in all_required_skills 
            if skill and _is_clean_technical_skill(skill) and 
            skill.lower() not in [s.lower() for s in original_skills]
        ]
        
        # Merge: Original skills + Missing clean skills
        merged_skills = original_skills + missing_clean_skills
        
        # Categorize the merged skills
        categorized = self._categorize_skills_comprehensive(merged_skills, job_requirements)
        
        print(f"🚀 Original skills: {len(original_skills)}")
        print(f"🚀 Added clean skills: {len(missing_clean_skills)} -> {missing_clean_skills}")
        print(f"🚀 Final merged skills: {len(merged_skills)}")
        
        return categorized
    
    def _optimize_contact_info(self, resume: ParsedResume) -> Dict[str, str]:
        """Optimize contact info to ensure completeness"""
        
        contact = resume.contact_info.copy() if resume.contact_info else {}
        
        # Extract name from contact info properly - check multiple sources
        name = None
        
        # First try direct name field
        if 'name' in contact and contact['name'] and contact['name'] not in ['YOUR NAME', 'Unknown']:
            name = contact['name']
        # Try to extract from full_text
        elif hasattr(resume, 'full_text') and resume.full_text:
            first_line = resume.full_text.strip().split('\n')[0].strip()
            if first_line and len(first_line.split()) <= 4 and first_line not in ['YOUR NAME', 'Unknown']:
                name = first_line
        
        # Fallback to known name if nothing found
        if not name:
            name = 'ABHIRAMI T'
        
        contact['name'] = name
        
        # Add missing phone if not present or incomplete
        if not contact.get('phone') or contact.get('phone') == '+91-' or len(str(contact.get('phone', ''))) < 5:
            contact['phone'] = '+91-9025817343'  # From your resume
        
        # Add missing email if not present
        if not contact.get('email') or '@' not in str(contact.get('email', '')):
            contact['email'] = 'abhiramitamil2006@gmail.com'  # From your resume
        
        # Add LinkedIn if not present
        if not contact.get('linkedin'):
            contact['linkedin'] = 'LinkedIn'  # From your resume
        
        # Add GitHub if not present
        if not contact.get('github'):
            contact['github'] = 'GitHub'  # From your resume
        
        print(f"🔧 FINAL OPTIMIZED CONTACT INFO: {contact}")
        return contact
    
    def _optimize_education_preserve(self, section: ResumeSection, job_requirements: JobRequirements) -> OptimizedResumeSection:
        """Preserve education section - no changes needed"""
        return OptimizedResumeSection(
            title=section.title,
            content=section.content,
            bullet_points=section.bullet_points,
            keywords_added=[],
            improvements_made=[]
        )
    
    def _optimize_skills_section_content_preserve(self, section: ResumeSection, job_requirements: JobRequirements) -> OptimizedResumeSection:
        """Preserve skills section content - skills are handled separately"""
        return OptimizedResumeSection(
            title=section.title,
            content=section.content,
            bullet_points=section.bullet_points,
            keywords_added=[],
            improvements_made=[]
        )
    
    def _optimize_summary_preserve(self, section: ResumeSection, job_requirements: JobRequirements) -> OptimizedResumeSection:
        """Preserve summary section - add keywords if they fit naturally"""
        enhanced_content = section.content
        keywords_added = []
        
        if section.content:
            # Add relevant keywords to summary if they fit
            summary_lower = section.content.lower()
            for keyword in job_requirements.required_skills[:3]:  # Limit to 3
                if keyword.lower() not in summary_lower and len(keyword) < 20:
                    # Add to end of summary
                    enhanced_content = enhanced_content.rstrip('.') + f" with expertise in {keyword}."
                    keywords_added.append(keyword)
                    break
        
        return OptimizedResumeSection(
            title=section.title,
            content=enhanced_content,
            bullet_points=section.bullet_points,
            keywords_added=keywords_added,
            improvements_made=["Enhanced with relevant keywords"] if keywords_added else []
        )
    
    def _optimize_projects_preserve(self, section: ResumeSection, job_requirements: JobRequirements) -> OptimizedResumeSection:
        """Preserve ALL projects - never remove any"""
        # Keep all original project bullets
        enhanced_bullets = section.bullet_points.copy()
        keywords_added = []
        
        # Enhance existing projects with relevant keywords
        for i, bullet in enumerate(enhanced_bullets):
            enhanced_bullet = bullet
            bullet_lower = bullet.lower()
            
            for keyword in job_requirements.required_skills:
                if keyword.lower() not in bullet_lower and len(keyword) < 20:
                    if any(tech in bullet_lower for tech in ['developed', 'built', 'created', 'implemented']):
                        enhanced_bullets[i] = enhanced_bullet.rstrip('.') + f" using {keyword}."
                        keywords_added.append(keyword)
                        break
        
        return OptimizedResumeSection(
            title=section.title,
            content=section.content,
            bullet_points=enhanced_bullets,  # All original projects preserved
            keywords_added=list(set(keywords_added)),
            improvements_made=["Enhanced existing projects with keywords"] if keywords_added else []
        )
    
    def _optimize_generic_section_preserve(self, section: ResumeSection, job_requirements: JobRequirements) -> OptimizedResumeSection:
        """Preserve generic sections like internships, certifications, achievements"""
        # For sections like internships, certifications, achievements - preserve everything
        return OptimizedResumeSection(
            title=section.title,
            content=section.content,
            bullet_points=section.bullet_points,
            keywords_added=[],
            improvements_made=[]
        )
    
    def _build_optimized_full_text(self, contact_info: Dict, sections: List[OptimizedResumeSection], 
                                 skills: Dict[str, List[str]]) -> str:
        """Build comprehensive full_text with all optimizations"""
        
        full_text = contact_info.get('name', '') + '\n'
        
        # Add contact info
        for key, value in contact_info.items():
            if key != 'name' and value:
                full_text += f"{key}: {value}\n"
        
        # Add all sections with enhanced content
        for section in sections:
            full_text += f"\n{section.title}\n"
            if section.content:
                full_text += f"{section.content}\n"
            for bullet in section.bullet_points:
                full_text += f"• {bullet}\n"
        
        # Add skills section
        if skills:
            full_text += "\nSKILLS\n"
            for category, skill_list in skills.items():
                if skill_list:
                    full_text += f"{category}: {', '.join(skill_list)}\n"
        
        return full_text
    
    def _categorize_skills_comprehensive(self, all_skills: List[str], job_requirements: JobRequirements) -> Dict[str, List[str]]:
        """Comprehensive skill categorization for maximum ATS score"""
        
        categories = {
            'Programming Languages': [],
            'Web Technologies': [],
            'Databases': [],
            'Cloud & DevOps': [],
            'Machine Learning & AI': [],
            'Data Science': [],
            'Tools & Frameworks': [],
            'Other Skills': []
        }
        
        # Enhanced categorization with more keywords
        ml_ai_keywords = ['tensorflow', 'pytorch', 'machine learning', 'nlp', 'ai', 'artificial intelligence', 
                        'deep learning', 'neural networks', 'computer vision', 'data science']
        
        web_keywords = ['react', 'angular', 'vue', 'node', 'javascript', 'html', 'css', 'typescript', 
                       'django', 'flask', 'express', 'mongodb', 'mysql', 'postgresql']
        
        cloud_keywords = ['aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform', 'ci/cd', 'devops']
        
        programming_keywords = ['python', 'java', 'javascript', 'c++', 'c#', 'go', 'rust', 'scala', 'ruby']
        
        for skill in all_skills:
            skill_lower = skill.lower()
            
            if any(keyword in skill_lower for keyword in ml_ai_keywords):
                categories['Machine Learning & AI'].append(skill)
            elif any(keyword in skill_lower for keyword in web_keywords):
                categories['Web Technologies'].append(skill)
            elif any(keyword in skill_lower for keyword in cloud_keywords):
                categories['Cloud & DevOps'].append(skill)
            elif any(keyword in skill_lower for keyword in programming_keywords):
                categories['Programming Languages'].append(skill)
            else:
                categories['Other Skills'].append(skill)
        
        # Remove empty categories
        return {k: v for k, v in categories.items() if v}
    
    def _optimize_projects_section_aggressive(self, section: ResumeSection, job_requirements: JobRequirements) -> OptimizedResumeSection:
        """Aggressively optimize projects section with relevant technologies"""
        
        enhanced_bullets = []
        keywords_added = []
        
        # Get relevant technologies from job requirements
        tech_keywords = job_requirements.required_skills + job_requirements.keywords
        
        for bullet in section.bullet_points:
            enhanced_bullet = bullet
            
            # Add relevant technologies to each project
            for tech in tech_keywords:
                if tech.lower() not in enhanced_bullet.lower():
                    if len(enhanced_bullets) < 5:  # Limit to avoid over-optimization
                        enhanced_bullet += f" using {tech}"
                        keywords_added.append(tech)
                        break
            
            enhanced_bullets.append(enhanced_bullet)
        
        improvements = []
        if keywords_added:
            improvements.append(f"Added relevant technologies: {', '.join(set(keywords_added))}")
        
        return OptimizedResumeSection(
            title=section.title,
            content=section.content,
            bullet_points=enhanced_bullets,
            keywords_added=list(set(keywords_added)),
            improvements_made=improvements
        )
    
    def _optimize_summary_section_aggressive(self, section: ResumeSection, job_requirements: JobRequirements) -> OptimizedResumeSection:
        """Aggressively optimize summary with all key requirements"""
        
        # Get all requirements
        all_requirements = job_requirements.required_skills + job_requirements.keywords
        key_requirements = all_requirements[:15]  # Top 15 keywords
        
        # Create enhanced summary with all key requirements
        enhanced_summary = section.content
        
        # Add missing key requirements
        for req in key_requirements:
            if req.lower() not in enhanced_summary.lower():
                if len(enhanced_summary.split()) < 150:  # Keep summary reasonable length
                    enhanced_summary += f" Proficient in {req}"
        
        added_keywords = [kw for kw in key_requirements if kw.lower() in enhanced_summary.lower() 
                         and kw.lower() not in section.content.lower()]
        
        improvements = []
        if added_keywords:
            improvements.append(f"Integrated key requirements: {', '.join(added_keywords[:8])}")
        
        return OptimizedResumeSection(
            title=section.title,
            content=enhanced_summary,
            bullet_points=section.bullet_points,
            keywords_added=added_keywords,
            improvements_made=improvements
        )
    
    def _optimize_education_section_aggressive(self, section: ResumeSection, job_requirements: JobRequirements) -> OptimizedResumeSection:
        """Aggressively optimize education section with relevant coursework"""
        
        enhanced_content = section.content
        improvements = []
        
        # Add comprehensive relevant coursework
        all_requirements = job_requirements.required_skills + job_requirements.keywords
        relevant_coursework = []
        
        tech_skills = [skill for skill in all_requirements if any(tech in skill.lower() 
                     for tech in ['python', 'java', 'machine learning', 'ai', 'data science', 'web'])]
        
        if tech_skills:
            coursework_text = f"Relevant Coursework: Data Structures, Algorithms, {', '.join(tech_skills[:5])}"
            if coursework_text not in enhanced_content:
                enhanced_content += f"\n• {coursework_text}"
                improvements.append(f"Added relevant coursework: {', '.join(tech_skills[:3])}")
        
        return OptimizedResumeSection(
            title=section.title,
            content=enhanced_content,
            bullet_points=section.bullet_points,
            keywords_added=tech_skills[:3],
            improvements_made=improvements
        )
    
    def _optimize_generic_section_aggressive(self, section: ResumeSection, job_requirements: JobRequirements) -> OptimizedResumeSection:
        """Aggressively optimize generic sections"""
        
        # Add relevant keywords to content
        enhanced_content = section.content
        keywords_added = []
        
        all_requirements = job_requirements.required_skills + job_requirements.keywords
        
        for keyword in all_requirements[:10]:  # Top 10 keywords
            if keyword.lower() not in enhanced_content.lower() and len(enhanced_content) < 300:
                enhanced_content += f" Experience with {keyword}"
                keywords_added.append(keyword)
                break
        
        improvements = []
        if keywords_added:
            improvements.append(f"Added relevant keywords: {', '.join(keywords_added)}")
        
        return OptimizedResumeSection(
            title=section.title,
            content=enhanced_content,
            bullet_points=section.bullet_points,
            keywords_added=keywords_added,
            improvements_made=improvements
        )
        
        # Get AI suggestions for this section
        section_suggestion = None
        if suggestions:
            section_suggestion = next((s for s in suggestions if s.section_name.lower() == section.title.lower()), None)
        
        # Apply optimizations based on section type
        if section.title.lower() in ['experience', 'work', 'employment']:
            return self._optimize_experience_section(section, job_requirements, section_suggestion)
        elif section.title.lower() in ['education', 'academic']:
            return self._optimize_education_section(section, job_requirements)
        elif section.title.lower() in ['projects', 'project']:
            return self._optimize_projects_section(section, job_requirements, section_suggestion)
        elif section.title.lower() in ['skills', 'technical skills']:
            return self._optimize_skills_section_content(section, job_requirements)
        elif section.title.lower() in ['summary', 'objective', 'profile']:
            return self._optimize_summary_section(section, job_requirements)
        elif section.title.lower() in ['certifications', 'certificates']:
            return self._optimize_certifications_section(section, job_requirements)
        elif section.title.lower() in ['achievements', 'awards']:
            return self._optimize_achievements_section(section, job_requirements)
        else:
            # Generic optimization
            return self._optimize_generic_section_aggressive(section, job_requirements)
    
    def _optimize_experience_section(self, section: ResumeSection, job_requirements: JobRequirements,
                                  section_suggestion: Optional[SectionSuggestion]) -> OptimizedResumeSection:
        """Aggressively optimize experience section with job-specific keywords"""
        
        # Use the aggressive version
        return self._optimize_experience_section_aggressive(section, job_requirements)
    
    def _optimize_education_section(self, section: ResumeSection, job_requirements: JobRequirements) -> OptimizedResumeSection:
        """Aggressively optimize education section"""
        
        # Use the aggressive version
        return self._optimize_education_section_aggressive(section, job_requirements)
    
    def _optimize_projects_section(self, section: ResumeSection, job_requirements: JobRequirements,
                               section_suggestion: Optional[SectionSuggestion]) -> OptimizedResumeSection:
        """Aggressively optimize projects section"""
        
        # Use the aggressive version
        return self._optimize_projects_section_aggressive(section, job_requirements)
    
    def _optimize_generic_section(self, section: ResumeSection, job_requirements: JobRequirements) -> OptimizedResumeSection:
        """Aggressively optimize generic sections"""
        
        # Use the aggressive version
        return self._optimize_generic_section_aggressive(section, job_requirements)
    
    def _optimize_skills_section_content_aggressive(self, section: ResumeSection, job_requirements: JobRequirements) -> OptimizedResumeSection:
        """Optimize skills section by grouping and limiting injected keywords."""

        def _is_technical_keyword(keyword: str) -> bool:
            # Filter out recruiter-friendly phrases and generic words
            if not keyword or not isinstance(keyword, str):
                return False
            kw = keyword.strip().lower()
            blacklist = {
                'the software engineer',
                'a software engineer',
                'our ideal candidates',
                'software engineer',
                'candidate',
                'candidates',
                'experience',
                'responsibilities',
                'skills',
                'best'
            }
            if kw in blacklist:
                return False

            tech_indicators = [
                'python', 'java', 'javascript', 'sql', 'aws', 'docker', 'kubernetes',
                'react', 'node', 'django', 'flask', 'azure', 'gcp', 'tensorflow',
                'pytorch', 'html', 'css', 'typescript', 'c++', 'c#', 'go', 'rust',
                'git', 'rest', 'graphql', 'api', 'linux', 'cloud', 'devops', 'ci/cd',
                'microservices', 'machine learning', 'data science', 'analytics'
            ]
            return any(indicator in kw for indicator in tech_indicators)

        # Extract skills already present in the resume section
        current_skills = self._extract_skills_from_content(
            section.content + '\n' + '\n'.join(section.bullet_points)
        )

        # Determine missing required keywords (deduplicated)
        all_required = job_requirements.required_skills + job_requirements.keywords
        unique_required = list(dict.fromkeys([s for s in all_required if s and isinstance(s, str)]))
        missing_skills = [skill for skill in unique_required
                          if skill.lower() not in [s.lower() for s in current_skills]]

        # Keep only technical keywords and limit to 5-10 additions
        missing_tech = [kw for kw in missing_skills if _is_technical_keyword(kw)]
        missing_tech = missing_tech[:8]  # Limit to 8 maximum to avoid over-optimization

        # Build unique skill list and create bullet points grouped by category
        combined_skills = list(dict.fromkeys(current_skills + missing_tech))
        categorized = self._categorize_skills_comprehensive(combined_skills, job_requirements)

        bullet_points = []
        for category, skills in categorized.items():
            # Remove duplicates within each category and limit to reasonable number
            unique_skills = list(dict.fromkeys(skills))
            if len(unique_skills) > 8:
                unique_skills = unique_skills[:8]
            bullet_points.append(f"{category}: {', '.join(unique_skills)}")

        improvements = []
        if missing_tech:
            improvements.append(f"Added {len(missing_tech)} high-impact technical keywords")
            print(f"🚀 SKILLS INJECTION: Added missing skills: {missing_tech}")

        # Keep content minimal and rely on bullet list for structured skills
        return OptimizedResumeSection(
            title=section.title,
            content="",
            bullet_points=bullet_points,
            keywords_added=missing_tech,
            improvements_made=improvements
        )
    
    def _optimize_summary_section(self, section: ResumeSection, job_requirements: JobRequirements) -> OptimizedResumeSection:
        """Aggressively optimize professional summary with job keywords"""
        
        # Get ALL requirements (not just top 10)
        all_requirements = job_requirements.required_skills + job_requirements.keywords
        key_requirements = all_requirements[:15]  # Top 15 keywords for maximum impact
        
        # Create enhanced summary with all key requirements
        enhanced_summary = section.content.strip()
        
        # Add missing key requirements aggressively
        added_keywords = []
        for req in key_requirements:
            if req.lower() not in enhanced_summary.lower():
                # Add keyword naturally
                if len(enhanced_summary.split()) < 200:  # Allow longer summary for more keywords
                    enhanced_summary += f" Proficient in {req} with hands-on experience"
                    added_keywords.append(req)
        
        improvements = []
        if added_keywords:
            improvements.append(f"Integrated key job requirements: {', '.join(added_keywords[:8])}")
        
        return OptimizedResumeSection(
            title=section.title,
            content=enhanced_summary,
            bullet_points=section.bullet_points,
            keywords_added=added_keywords,
            improvements_made=improvements
        )
    
    def _optimize_certifications_section(self, section: ResumeSection, job_requirements: JobRequirements) -> OptimizedResumeSection:
        """Optimize certifications section"""
        # Certifications usually don't need optimization
        return OptimizedResumeSection(
            title=section.title,
            content=section.content,
            bullet_points=section.bullet_points,
            keywords_added=[],
            improvements_made=[]
        )
    
    def _optimize_achievements_section(self, section: ResumeSection, job_requirements: JobRequirements) -> OptimizedResumeSection:
        """Optimize achievements section"""
        # Enhance achievement descriptions with quantifiable results
        optimized_bullets = []
        improvements = []
        
        for bullet in section.bullet_points:
            enhanced_bullet = self._enhance_achievement_bullet(bullet)
            if enhanced_bullet != bullet:
                optimized_bullets.append(enhanced_bullet)
                improvements.append("Enhanced with quantifiable metrics")
            else:
                optimized_bullets.append(bullet)
        
        return OptimizedResumeSection(
            title=section.title,
            content=section.content,
            bullet_points=optimized_bullets,
            keywords_added=[],
            improvements_made=improvements
        )
    
    def _optimize_generic_section(self, section: ResumeSection, job_requirements: JobRequirements) -> OptimizedResumeSection:
        """Generic optimization for other sections"""
        missing_keywords = self._get_missing_keywords(job_requirements, section.content)
        enhanced_content = self._enhance_content_with_keywords(section.content, missing_keywords)
        
        return OptimizedResumeSection(
            title=section.title,
            content=enhanced_content,
            bullet_points=section.bullet_points,
            keywords_added=missing_keywords,
            improvements_made=[f"Added relevant keywords: {', '.join(missing_keywords[:3])}"]
        )
    
    def _optimize_skills_section(self, resume: ParsedResume, job_requirements: JobRequirements) -> Dict[str, List[str]]:
        """Create optimized skills section"""
        
        # Get all current skills
        all_skills = resume.skills.copy()
        
        # Add missing required skills
        all_required_skills = job_requirements.required_skills + job_requirements.keywords
        for skill in all_required_skills:
            if skill.lower() not in [s.lower() for s in all_skills]:
                all_skills.append(skill)
        
        # Categorize skills
        categorized = self._categorize_skills(all_skills, job_requirements)
        
        return categorized
    
    def _get_missing_keywords(self, job_requirements: JobRequirements, content: str) -> List[str]:
        """Find keywords missing from content"""
        content_lower = content.lower()
        missing = []
        
        # Check both required_skills and keywords
        all_required = job_requirements.required_skills + job_requirements.keywords
        
        for keyword in all_required:
            if keyword.lower() not in content_lower:
                missing.append(keyword)
        
        return missing[:10]  # Limit to top 10 missing keywords
    
    def _enhance_bullet_with_keywords(self, bullet: str, keywords: List[str]) -> str:
        """Enhance bullet point with relevant keywords"""
        enhanced = bullet
        
        # Add relevant keywords naturally
        for keyword in keywords[:3]:  # Limit to avoid keyword stuffing
            if keyword.lower() not in enhanced.lower():
                # Try to add keyword naturally
                if 'developed' in enhanced.lower() and any(tech in keyword.lower() for tech in ['javascript', 'react', 'node']):
                    enhanced = enhanced.replace('developed', f'developed using {keyword}')
                elif 'built' in enhanced.lower() and any(tech in keyword.lower() for tech in ['javascript', 'react', 'node']):
                    enhanced = enhanced.replace('built', f'built with {keyword}')
                elif 'implemented' in enhanced.lower():
                    enhanced = enhanced.replace('implemented', f'implemented {keyword} solutions')
        
        return enhanced
    
    def _enhance_project_bullet(self, bullet: str, keywords: List[str]) -> str:
        """Enhance project bullet with relevant technologies"""
        enhanced = bullet
        
        # Add relevant technologies
        tech_keywords = [kw for kw in keywords if any(tech in kw.lower() for tech in 
                       ['javascript', 'react', 'node', 'angular', 'jquery', 'aws', 'docker'])]
        
        for tech in tech_keywords[:2]:
            if tech.lower() not in enhanced.lower():
                if 'using' in enhanced.lower():
                    enhanced = enhanced.replace('using', f'using {tech} and')
                elif 'with' in enhanced.lower():
                    enhanced = enhanced.replace('with', f'with {tech},')
                else:
                    enhanced += f" using {tech}"
        
        return enhanced
    
    def _enhance_achievement_bullet(self, bullet: str) -> str:
        """Enhance achievement with quantifiable metrics"""
        enhanced = bullet
        
        # Add quantifiable metrics if missing
        if not any(char.isdigit() for char in enhanced):
            if 'first' in enhanced.lower() or '1st' in enhanced.lower():
                enhanced += " (out of 200+ participants)"
            elif 'second' in enhanced.lower() or '2nd' in enhanced.lower():
                enhanced += " (out of 200+ participants)"
            elif 'top' in enhanced.lower():
                enhanced += " (top 15% percentile)"
        
        return enhanced
    
    def _enhance_content_with_keywords(self, content: str, keywords: List[str]) -> str:
        """Enhance content with missing keywords"""
        enhanced = content
        
        # Add keywords naturally without stuffing
        for keyword in keywords[:5]:
            if keyword.lower() not in enhanced.lower():
                # Add keyword in a natural way
                if 'experience' in enhanced.lower():
                    enhanced = enhanced.replace('experience', f'experience with {keyword}')
                elif 'skills' in enhanced.lower():
                    enhanced = enhanced.replace('skills', f'skills in {keyword}')
        
        return enhanced
    
    def _create_enhanced_summary(self, original_summary: str, keywords: List[str]) -> str:
        """Create enhanced professional summary"""
        if not original_summary.strip():
            # Create new summary from scratch
            relevant_keywords = [kw for kw in keywords if len(kw) > 2][:8]
            summary = f"Results-oriented Full Stack Developer with expertise in {', '.join(relevant_keywords[:5])}. "
            summary += f"Proven track record of delivering scalable software solutions and working effectively with development teams. "
            summary += f"Strong analytical skills combined with excellent communication and collaboration abilities."
            return summary
        
        # Enhance existing summary
        enhanced = original_summary
        relevant_keywords = [kw for kw in keywords if kw.lower() not in enhanced.lower()][:5]
        
        if relevant_keywords:
            enhanced += f" Skilled in {', '.join(relevant_keywords)}."
        
        return enhanced
    
    def _extract_skills_from_content(self, content: str) -> List[str]:
        """Extract skills from content"""
        # Simple skill extraction - can be enhanced
        skills = []
        
        # Common programming languages and technologies
        tech_patterns = [
            r'\b(Python|Java|JavaScript|React|Node\.js|Angular|Vue\.js|HTML|CSS|SQL|MongoDB|MySQL|AWS|Docker|Git)\b',
            r'\b(C\+\+|C#|Go|Ruby|PHP|TypeScript|Express\.js|Django|Flask|Spring)\b',
            r'\b(Azure|GCP|Kubernetes|Jenkins|Terraform|Ansible|Linux|Windows)\b'
        ]
        
        for pattern in tech_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            skills.extend(matches)
        
        return list(set(skills))
    
    def _categorize_skills(self, skills: List[str], job_requirements: JobRequirements) -> Dict[str, List[str]]:
        """Categorize skills by type"""
        categories = {
            'Programming Languages': [],
            'Web Technologies': [],
            'Databases': [],
            'Cloud & DevOps': [],
            'Tools & Frameworks': [],
            'Other Skills': []
        }
        
        for skill in skills:
            skill_lower = skill.lower()
            
            if any(lang in skill_lower for lang in ['python', 'java', 'javascript', 'c#', 'c++', 'go', 'ruby', 'php', 'typescript']):
                categories['Programming Languages'].append(skill)
            elif any(web in skill_lower for web in ['react', 'angular', 'vue', 'html', 'css', 'node.js', 'express.js', 'django', 'flask']):
                categories['Web Technologies'].append(skill)
            elif any(db in skill_lower for db in ['mysql', 'mongodb', 'postgresql', 'sql', 'redis', 'cassandra']):
                categories['Databases'].append(skill)
            elif any(cloud in skill_lower for cloud in ['aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'terraform']):
                categories['Cloud & DevOps'].append(skill)
            else:
                categories['Other Skills'].append(skill)
        
        # Remove empty categories
        return {k: v for k, v in categories.items() if v}
    
    def _build_skills_content(self, categorized_skills: Dict[str, List[str]]) -> str:
        """Build skills section content"""
        content_parts = []
        
        for category, skills in categorized_skills.items():
            if skills:
                skills_str = ' | '.join(skills)
                content_parts.append(f"{category}: {skills_str}")
        
        return '\n'.join(content_parts)
    
    def _format_contact_info(self, contact_info: Dict[str, str]) -> str:
        """Format contact information"""
        parts = []
        
        if contact_info.get('name'):
            parts.append(contact_info['name'])
        
        contact_line_parts = []
        if contact_info.get('email'):
            contact_line_parts.append(contact_info['email'])
        if contact_info.get('phone'):
            contact_line_parts.append(contact_info['phone'])
        if contact_info.get('linkedin'):
            contact_line_parts.append(f"LinkedIn: {contact_info['linkedin']}")
        if contact_info.get('github'):
            contact_line_parts.append(f"GitHub: {contact_info['github']}")
        
        if contact_line_parts:
            parts.append(' | '.join(contact_line_parts))
        
        return '\n'.join(parts)
    
    def _convert_to_parsed_section(self, optimized_section: OptimizedResumeSection) -> ResumeSection:
        """Convert optimized section back to ResumeSection"""
        return ResumeSection(
            title=optimized_section.title,
            content=optimized_section.content,
            bullet_points=optimized_section.bullet_points
        )
    
    def _flatten_skills(self, categorized_skills: Dict[str, List[str]]) -> List[str]:
        """Flatten categorized skills back to list"""
        all_skills = []
        for skills in categorized_skills.values():
            all_skills.extend(skills)
        return all_skills
    
    def _find_added_keywords(self, original: str, enhanced: str) -> List[str]:
        """Find keywords that were added during enhancement"""
        original_words = set(original.lower().split())
        enhanced_words = set(enhanced.lower().split())
        added = enhanced_words - original_words
        return list(added)[:5]  # Limit to 5 most relevant
    
    def _create_optimization_summary(self, sections: List[OptimizedResumeSection], 
                                 skills: Dict[str, List[str]], score_improvement: float) -> str:
        """Create summary of optimizations made"""
        summary_parts = []
        
        summary_parts.append(f"ATS Score Improvement: +{score_improvement:.1f}%")
        
        total_keywords_added = sum(len(s.keywords_added) for s in sections)
        if total_keywords_added > 0:
            summary_parts.append(f"Keywords Added: {total_keywords_added}")
        
        total_improvements = sum(len(s.improvements_made) for s in sections)
        if total_improvements > 0:
            summary_parts.append(f"Sections Optimized: {len([s for s in sections if s.improvements_made])}")
        
        if skills:
            summary_parts.append(f"Skills Categories: {len(skills)}")
        
        return " | ".join(summary_parts)
