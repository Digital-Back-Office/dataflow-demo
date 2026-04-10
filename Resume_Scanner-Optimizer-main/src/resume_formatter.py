import re
from typing import Dict, List, Optional
from dataclasses import dataclass
from src.resume_parser import ParsedResume, ResumeSection
from src.ai_suggestions import SectionSuggestion

@dataclass
class FormattedResume:
    name: str
    contact_info: str
    summary: str
    experience: List[Dict]
    education: List[Dict]
    skills: Dict[str, List[str]]
    projects: Optional[List[str]]
    certifications: Optional[List[str]]

class ResumeFormatter:
    """Professional resume formatter that creates ATS-friendly content"""
    
    def __init__(self):
        pass
    
    def format_resume_content(self, resume: ParsedResume, job_title: str, 
                             suggestions: Optional[List[SectionSuggestion]] = None) -> FormattedResume:
        """Format resume content into professional structure"""
        
        # Extract and format contact information
        name, contact_info = self._format_contact_info(resume.contact_info)
        
        # Create professional summary
        summary = self._create_professional_summary(resume, job_title)
        
        # Format experience section
        experience = self._format_experience_section(resume, suggestions)
        
        # Format education section
        education = self._format_education_section(resume)
        
        # Format skills section
        skills = self._format_skills_section(resume)
        
        # Extract projects and certifications
        projects = self._extract_projects(resume)
        certifications = self._extract_certifications(resume)
        
        return FormattedResume(
            name=name,
            contact_info=contact_info,
            summary=summary,
            experience=experience,
            education=education,
            skills=skills,
            projects=projects,
            certifications=certifications
        )
    
    def _format_contact_info(self, contact_info: Dict[str, str]) -> tuple:
        """Format contact information"""
        # Extract name from resume content or use default
        name = contact_info.get('name', 'YOUR NAME')
        
        # Build contact line
        contact_parts = []
        
        email = contact_info.get('email', '')
        if email:
            contact_parts.append(email)
        
        phone = contact_info.get('phone', '')
        if phone:
            contact_parts.append(phone)
        
        linkedin = contact_info.get('linkedin', '')
        if linkedin:
            contact_parts.append(f"LinkedIn: {linkedin}")
        
        # Add location if available
        location = contact_info.get('location', '')
        if location:
            contact_parts.append(location)
        
        contact_info_str = ' | '.join(contact_parts) if contact_parts else 'email@example.com | +1 (555) 123-4567'
        
        return name, contact_info_str
    
    def _create_professional_summary(self, resume: ParsedResume, job_title: str) -> str:
        """Create a compelling professional summary"""
        # Extract existing summary if available
        summary_section = next((s for s in resume.sections if s.title.lower() in ['summary', 'objective', 'profile']), None)
        
        if summary_section and summary_section.content.strip():
            return summary_section.content.strip()[:300]  # Limit length
        
        # Create summary from skills and experience
        top_skills = ', '.join(resume.skills[:8])
        
        summary_templates = [
            f"Results-oriented {job_title.lower()} with expertise in {top_skills}. "
            f"Proven track record of delivering innovative solutions and driving project success. "
            f"Strong analytical skills combined with excellent communication and collaboration abilities.",
            
            f"Accomplished professional with comprehensive experience in {top_skills}. "
            f"Demonstrated success in implementing complex solutions and optimizing processes. "
            f"Seeking to leverage technical expertise and leadership skills in a challenging role.",
            
            f"Dynamic {job_title.lower()} specializing in {top_skills}. "
            f"Consistently recognized for problem-solving abilities and commitment to excellence. "
            f"Eager to contribute technical skills and innovative thinking to drive organizational success."
        ]
        
        # Choose the best template based on experience
        if resume.experience:
            return summary_templates[0]
        else:
            return summary_templates[1]
    
    def _format_experience_section(self, resume: ParsedResume, 
                                  suggestions: Optional[List[SectionSuggestion]]) -> List[Dict]:
        """Format experience section with professional bullet points"""
        experience_sections = []
        
        # Get experience sections from resume
        exp_sections = [s for s in resume.sections if s.title.lower() in ['experience', 'work', 'employment']]
        
        for section in exp_sections:
            # Parse experience entries (simplified parsing)
            entries = self._parse_experience_entries(section.content, section.bullet_points)
            
            # Apply AI suggestions if available
            if suggestions:
                section_suggestion = next((s for s in suggestions if s.section_name.lower() == section.title.lower()), None)
                if section_suggestion:
                    # Use AI-improved bullets
                    for i, entry in enumerate(entries):
                        if i < len(section_suggestion.suggestions):
                            entry['bullets'] = [section_suggestion.suggestions[i].improved_bullet]
            
            experience_sections.extend(entries)
        
        return experience_sections
    
    def _parse_experience_entries(self, content: str, bullets: List[str]) -> List[Dict]:
        """Parse experience entries from content"""
        entries = []
        
        # Try to extract structured information
        lines = content.split('\n')
        current_entry = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Look for patterns that indicate a new job entry
            if self._is_job_title_line(line):
                if current_entry:
                    entries.append(current_entry)
                
                # Parse job title, company, dates
                title, company, dates, location = self._parse_job_line(line)
                current_entry = {
                    'title': title,
                    'company': company,
                    'dates': dates,
                    'location': location,
                    'bullets': []
                }
            elif current_entry and line.startswith(('•', '-', '*', '·')):
                # Clean bullet point
                clean_bullet = line.lstrip('•-*· ').strip()
                if clean_bullet:
                    current_entry['bullets'].append(clean_bullet)
        
        # Add the last entry
        if current_entry:
            entries.append(current_entry)
        
        # If no structured entries found, create a generic one
        if not entries and bullets:
            entries.append({
                'title': 'Professional Experience',
                'company': 'Company Name',
                'dates': 'Present',
                'location': 'Location',
                'bullets': [bullet.lstrip('•-*· ').strip() for bullet in bullets if bullet.strip()]
            })
        
        return entries
    
    def _is_job_title_line(self, line: str) -> bool:
        """Check if line looks like a job title entry"""
        # Look for patterns like: "Title at Company (Dates)" or "Title - Company Dates"
        patterns = [
            r'.*\s+(at|@|–|-)\s+.*\d{4}',
            r'.*\s+(at|@|–|-)\s+.*\d{2}\/\d{4}',
            r'.*\s+\d{4}\s*-\s*\d{4}',
            r'.*\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)',
        ]
        
        return any(re.search(pattern, line, re.IGNORECASE) for pattern in patterns)
    
    def _parse_job_line(self, line: str) -> tuple:
        """Parse job title, company, dates, location from a line"""
        # Default values
        title = line
        company = 'Company Name'
        dates = 'Present'
        location = 'Location'
        
        # Try to extract components
        # Pattern: Title at Company Dates
        match = re.search(r'(.+?)\s+(at|@|–|-)\s+(.+?)\s+(\d{4}.*)', line, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            company = match.group(3).strip()
            dates = match.group(4).strip()
        else:
            # Pattern: Title - Company Dates
            match = re.search(r'(.+?)\s*–\s*(.+?)\s+(\d{4}.*)', line)
            if match:
                title = match.group(1).strip()
                company = match.group(2).strip()
                dates = match.group(3).strip()
        
        return title, company, dates, location
    
    def _format_education_section(self, resume: ParsedResume) -> List[Dict]:
        """Format education section"""
        education_entries = []
        
        edu_sections = [s for s in resume.sections if s.title.lower() in ['education', 'academic', 'qualification']]
        
        for section in edu_sections:
            # Parse education entries
            entries = self._parse_education_entries(section.content)
            education_entries.extend(entries)
        
        return education_entries
    
    def _parse_education_entries(self, content: str) -> List[Dict]:
        """Parse education entries from content"""
        entries = []
        
        lines = content.split('\n')
        current_entry = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Look for degree patterns
            if self._is_degree_line(line):
                if current_entry:
                    entries.append(current_entry)
                
                degree, institution, dates, gpa = self._parse_education_line(line)
                current_entry = {
                    'degree': degree,
                    'institution': institution,
                    'dates': dates,
                    'gpa': gpa,
                    'details': []
                }
            elif current_entry:
                # Add details
                current_entry['details'].append(line)
        
        # Add the last entry
        if current_entry:
            entries.append(current_entry)
        
        return entries
    
    def _is_degree_line(self, line: str) -> bool:
        """Check if line looks like a degree entry"""
        degree_keywords = ['bachelor', 'master', 'phd', 'btech', 'mtech', 'b.s.', 'm.s.', 'b.eng', 'm.eng', 'diploma']
        line_lower = line.lower()
        return any(keyword in line_lower for keyword in degree_keywords)
    
    def _parse_education_line(self, line: str) -> tuple:
        """Parse degree, institution, dates, GPA from a line"""
        degree = line
        institution = 'Institution'
        dates = 'Dates'
        gpa = ''
        
        # Try to extract GPA
        gpa_match = re.search(r'gpa[:\s]*([\d.]+)', line, re.IGNORECASE)
        if gpa_match:
            gpa = gpa_match.group(1)
        
        # Try to extract dates
        date_match = re.search(r'(\d{4}\s*[-–]\s*\d{4}|\d{4})', line)
        if date_match:
            dates = date_match.group(1)
        
        return degree, institution, dates, gpa
    
    def _format_skills_section(self, resume: ParsedResume) -> Dict[str, List[str]]:
        """Format skills into categories"""
        skills = resume.skills
        
        # Categorize skills
        categories = {
            'Technical Skills': [],
            'Programming Languages': [],
            'Cloud & DevOps': [],
            'Databases': [],
            'Web Technologies': [],
            'AI & Machine Learning': [],
            'Soft Skills': [],
            'Tools & Frameworks': []
        }
        
        for skill in skills:
            skill_lower = skill.lower()
            
            # Programming languages
            if any(lang in skill_lower for lang in ['python', 'java', 'javascript', 'c++', 'c#', 'go', 'rust', 'php', 'ruby', 'typescript']):
                categories['Programming Languages'].append(skill)
            
            # Cloud & DevOps
            elif any(cloud in skill_lower for cloud in ['aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'terraform', 'ansible', 'ci/cd', 'devops']):
                categories['Cloud & DevOps'].append(skill)
            
            # Databases
            elif any(db in skill_lower for db in ['sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'cassandra', 'oracle']):
                categories['Databases'].append(skill)
            
            # Web technologies
            elif any(web in skill_lower for web in ['react', 'angular', 'vue', 'node', 'express', 'django', 'flask', 'html', 'css', 'sass']):
                categories['Web Technologies'].append(skill)
            
            # AI & ML
            elif any(ai in skill_lower for ai in ['tensorflow', 'pytorch', 'machine learning', 'deep learning', 'nlp', 'computer vision', 'ai', 'ml', 'data science']):
                categories['AI & Machine Learning'].append(skill)
            
            # Soft skills
            elif any(soft in skill_lower for soft in ['communication', 'leadership', 'teamwork', 'management', 'analytical', 'problem solving', 'agile', 'scrum']):
                categories['Soft Skills'].append(skill)
            
            # Tools & Frameworks
            else:
                categories['Tools & Frameworks'].append(skill)
        
        # Remove empty categories
        return {k: v for k, v in categories.items() if v}
    
    def _extract_projects(self, resume: ParsedResume) -> Optional[List[str]]:
        """Extract projects section"""
        projects_section = next((s for s in resume.sections if s.title.lower() == 'projects'), None)
        
        if projects_section and projects_section.bullet_points:
            return [bullet.lstrip('•-*· ').strip() for bullet in projects_section.bullet_points if bullet.strip()]
        
        return None
    
    def _extract_certifications(self, resume: ParsedResume) -> Optional[List[str]]:
        """Extract certifications section"""
        cert_section = next((s for s in resume.sections if s.title.lower() in ['certifications', 'certificates', 'credentials']), None)
        
        if cert_section and cert_section.bullet_points:
            return [bullet.lstrip('•-*· ').strip() for bullet in cert_section.bullet_points if bullet.strip()]
        
        return None
