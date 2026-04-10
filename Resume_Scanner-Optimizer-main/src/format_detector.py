import re
from typing import Dict, List, Tuple
from dataclasses import dataclass
from src.resume_parser import ParsedResume

@dataclass
class FormattingIssue:
    issue_type: str
    severity: str  # 'critical', 'warning', 'info'
    description: str
    location: str
    suggestion: str

@dataclass
class FormatAnalysis:
    ats_compatibility_score: float
    issues: List[FormattingIssue]
    recommendations: List[str]
    safe_formatting_practices: List[str]

class ATSFormatDetector:
    def __init__(self):
        self.critical_issues = []
        self.warnings = []
        self.info_messages = []
    
    def analyze_formatting(self, resume: ParsedResume) -> FormatAnalysis:
        """Comprehensive ATS formatting analysis"""
        self.critical_issues = []
        self.warnings = []
        self.info_messages = []
        
        text = resume.full_text
        lines = text.split('\n')
        
        # Run all formatting checks
        self._check_tables_and_columns(text)
        self._check_special_characters(text)
        self._check_bullet_consistency(lines)
        self._check_section_headers(lines)
        self._check_spacing_and_layout(lines)
        self._check_font_and_style_indicators(text)
        self._check_contact_format(resume.contact_info)
        self._check_date_consistency(text)
        self._check_length_and_density(text)
        self._check_file_structure(resume)
        
        # Combine all issues
        all_issues = self.critical_issues + self.warnings + self.info_messages
        
        # Calculate compatibility score
        score = self._calculate_compatibility_score(all_issues)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(all_issues)
        
        # Identify safe practices
        safe_practices = self._identify_safe_practices(text, lines)
        
        return FormatAnalysis(
            ats_compatibility_score=score,
            issues=all_issues,
            recommendations=recommendations,
            safe_formatting_practices=safe_practices
        )
    
    def _check_tables_and_columns(self, text: str):
        """Check for tables and multi-column layouts"""
        lines = text.split('\n')
        
        # Check for table patterns
        consecutive_pipe_lines = 0
        for line in lines:
            if '|' in line and line.count('|') >= 2:
                consecutive_pipe_lines += 1
                if consecutive_pipe_lines >= 2:
                    self.critical_issues.append(FormattingIssue(
                        issue_type="Table Detected",
                        severity="critical",
                        description="Tables are poorly parsed by most ATS systems",
                        location=f"Lines {max(1, len(lines) - consecutive_pipe_lines)}-{len(lines)}",
                        suggestion="Convert table content to bullet points or linear text"
                    ))
                    break
            else:
                consecutive_pipe_lines = 0
        
        # Check for column indicators
        tab_patterns = []
        for i, line in enumerate(lines[:50]):  # Check first 50 lines
            tab_count = line.count('\t')
            if tab_count > 1:
                tab_patterns.append((i, tab_count))
        
        if len(tab_patterns) > 5:
            avg_tabs = sum(count for _, count in tab_patterns) / len(tab_patterns)
            if avg_tabs > 2:
                self.critical_issues.append(FormattingIssue(
                    issue_type="Multi-Column Layout",
                    severity="critical",
                    description="Multi-column layouts confuse ATS parsers",
                    location="Document structure",
                    suggestion="Use single-column layout with clear section headers"
                ))
    
    def _check_special_characters(self, text: str):
        """Check for problematic special characters"""
        problematic_chars = {
            '•': "Bullet dot",
            '→': "Right arrow",
            '←': "Left arrow", 
            '↑': "Up arrow",
            '↓': "Down arrow",
            '★': "Star",
            '◆': "Diamond",
            '●': "Filled circle",
            '■': "Filled square",
            '▲': "Triangle",
            '▼': "Inverted triangle"
        }
        
        found_chars = []
        for char, description in problematic_chars.items():
            if char in text:
                found_chars.append((char, description))
        
        if found_chars:
            self.warnings.append(FormattingIssue(
                issue_type="Special Characters",
                severity="warning",
                description=f"Found {len(found_chars)} problematic special characters: {', '.join([desc for _, desc in found_chars])}",
                location="Throughout document",
                suggestion="Replace with standard hyphens (-) or asterisks (*) for bullet points"
            ))
    
    def _check_bullet_consistency(self, lines: List[str]):
        """Check bullet point formatting consistency"""
        bullet_types = []
        bullet_lines = []
        
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith(('•', '-', '*', '·', '○', '■', '▪', '1.', '2.', '3.', '4.', '5.')):
                bullet_char = stripped[0] if stripped[0].isdigit() else stripped[0]
                bullet_types.append(bullet_char)
                bullet_lines.append(i + 1)
        
        if len(set(bullet_types)) > 2:
            self.warnings.append(FormattingIssue(
                issue_type="Inconsistent Bullets",
                severity="warning",
                description=f"Found {len(set(bullet_types))} different bullet types",
                location=f"Lines {min(bullet_lines)}-{max(bullet_lines)}",
                suggestion="Use consistent bullet points (prefer hyphens - or asterisks *)"
            ))
    
    def _check_section_headers(self, lines: List[str]):
        """Check section header formatting"""
        header_keywords = ['experience', 'education', 'skills', 'projects', 'summary', 'objective']
        found_headers = []
        
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            for keyword in header_keywords:
                if keyword in line_lower and len(line.strip()) < 50:
                    found_headers.append((i + 1, line.strip()))
                    break
        
        if len(found_headers) < 3:
            self.warnings.append(FormattingIssue(
                issue_type="Missing Section Headers",
                severity="warning",
                description="Fewer than 3 clear section headers found",
                location="Document structure",
                suggestion="Add clear section headers: EXPERIENCE, EDUCATION, SKILLS"
            ))
        
        # Check for ALL CAPS headers (good for ATS)
        caps_headers = [h for _, h in found_headers if h.isupper()]
        if len(caps_headers) < len(found_headers) * 0.5:
            self.info_messages.append(FormattingIssue(
                issue_type="Header Case",
                severity="info",
                description="Consider using ALL CAPS for section headers",
                location="Section headers",
                suggestion="ALL CAPS headers are more easily recognized by ATS"
            ))
    
    def _check_spacing_and_layout(self, lines: List[str]):
        """Check for spacing issues"""
        total_lines = len(lines)
        blank_lines = sum(1 for line in lines if not line.strip())
        
        # Too many blank lines
        if blank_lines / total_lines > 0.3:
            self.warnings.append(FormattingIssue(
                issue_type="Excessive Spacing",
                severity="warning",
                description=f"{blank_lines} blank lines out of {total_lines} total",
                location="Document layout",
                suggestion="Reduce excessive blank spacing"
            ))
        
        # Very long lines
        long_lines = [(i + 1, line) for i, line in enumerate(lines) if len(line) > 200]
        if len(long_lines) > total_lines * 0.1:
            self.warnings.append(FormattingIssue(
                issue_type="Long Lines",
                severity="warning",
                description=f"{len(long_lines)} lines exceed 200 characters",
                location=f"Lines {[i for i, _ in long_lines[:5]]}",
                suggestion="Break long lines into shorter, readable segments"
            ))
    
    def _check_font_and_style_indicators(self, text: str):
        """Check for font and styling issues"""
        # These are indicators that might cause parsing issues
        issues = []
        
        # Multiple consecutive spaces might indicate tabs or alignment issues
        if re.search(r' {4,}', text):
            issues.append("Multiple consecutive spaces")
        
        # Non-standard quotes
        if '"' in text or '"' in text or ''' in text or ''' in text:
            issues.append("Curly quotes")
        
        # Non-standard dashes
        if '–' in text or '—' in text:  # en dash, em dash
            issues.append("Non-standard dashes")
        
        if issues:
            self.info_messages.append(FormattingIssue(
                issue_type="Style Indicators",
                severity="info",
                description=f"Potential formatting issues: {', '.join(issues)}",
                location="Throughout document",
                suggestion="Use standard quotes (\") and hyphens (-)"
            ))
    
    def _check_contact_format(self, contact_info: Dict[str, str]):
        """Check contact information formatting"""
        if not contact_info.get('email'):
            self.critical_issues.append(FormattingIssue(
                issue_type="Missing Email",
                severity="critical",
                description="No email address found",
                location="Contact information",
                suggestion="Add professional email address at top of resume"
            ))
        
        if not contact_info.get('phone'):
            self.warnings.append(FormattingIssue(
                issue_type="Missing Phone",
                severity="warning",
                description="No phone number found",
                location="Contact information",
                suggestion="Add phone number for recruiter contact"
            ))
        
        # Check email format
        email = contact_info.get('email', '')
        if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            self.critical_issues.append(FormattingIssue(
                issue_type="Invalid Email Format",
                severity="critical",
                description=f"Email format appears invalid: {email}",
                location="Contact information",
                suggestion="Use standard email format: name@domain.com"
            ))
    
    def _check_date_consistency(self, text: str):
        """Check date format consistency"""
        date_patterns = [
            (r'\b\d{1,2}/\d{1,2}/\d{4}\b', 'MM/DD/YYYY'),
            (r'\b\d{1,2}-\d{1,2}-\d{4}\b', 'MM-DD-YYYY'),
            (r'\b\w{3,9} \d{4}\b', 'Month YYYY'),
            (r'\b\w{3,9} \d{1,2}, \d{4}\b', 'Month DD, YYYY'),
            (r'\b\d{4}\b', 'YYYY')
        ]
        
        found_formats = []
        for pattern, format_name in date_patterns:
            if re.search(pattern, text):
                found_formats.append(format_name)
        
        if len(found_formats) > 2:
            self.info_messages.append(FormattingIssue(
                issue_type="Date Format Inconsistency",
                severity="info",
                description=f"Multiple date formats found: {', '.join(found_formats)}",
                location="Experience section",
                suggestion="Use consistent date format (prefer Month YYYY)"
            ))
    
    def _check_length_and_density(self, text: str):
        """Check resume length and content density"""
        word_count = len(text.split())
        
        if word_count < 200:
            self.critical_issues.append(FormattingIssue(
                issue_type="Resume Too Short",
                severity="critical",
                description=f"Resume appears too short: {word_count} words",
                location="Document length",
                suggestion="Add more detail to experience and skills sections"
            ))
        elif word_count > 1000:
            self.warnings.append(FormattingIssue(
                issue_type="Resume Too Long",
                severity="warning",
                description=f"Resume quite long: {word_count} words",
                location="Document length",
                suggestion="Consider condensing to 1-2 pages maximum"
            ))
    
    def _check_file_structure(self, resume: ParsedResume):
        """Check overall file structure"""
        # Check for essential sections
        section_titles = [section.title.lower() for section in resume.sections]
        
        essential_sections = ['experience', 'education', 'skills']
        missing_sections = [section for section in essential_sections if section not in section_titles]
        
        if missing_sections:
            self.warnings.append(FormattingIssue(
                issue_type="Missing Essential Sections",
                severity="warning",
                description=f"Missing sections: {', '.join(missing_sections)}",
                location="Document structure",
                suggestion="Add missing sections for better ATS parsing"
            ))
    
    def _calculate_compatibility_score(self, issues: List[FormattingIssue]) -> float:
        """Calculate ATS compatibility score"""
        score = 100.0
        
        for issue in issues:
            if issue.severity == 'critical':
                score -= 15
            elif issue.severity == 'warning':
                score -= 8
            elif issue.severity == 'info':
                score -= 3
        
        return max(min(score, 100.0), 0.0)
    
    def _generate_recommendations(self, issues: List[FormattingIssue]) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Group by issue type
        critical_count = sum(1 for issue in issues if issue.severity == 'critical')
        warning_count = sum(1 for issue in issues if issue.severity == 'warning')
        
        if critical_count > 0:
            recommendations.append(f"URGENT: Fix {critical_count} critical formatting issues for ATS compatibility")
        
        if warning_count > 0:
            recommendations.append(f"Address {warning_count} formatting warnings to improve ATS parsing")
        
        # Specific recommendations based on issues
        issue_types = [issue.issue_type for issue in issues]
        
        if 'Table Detected' in issue_types:
            recommendations.append("Convert all tables to bullet points or linear text")
        
        if 'Multi-Column Layout' in issue_types:
            recommendations.append("Switch to single-column layout for better ATS parsing")
        
        if 'Missing Email' in issue_types:
            recommendations.append("Add professional email at the top of your resume")
        
        if len(recommendations) == 0:
            recommendations.append("Resume formatting is ATS-friendly!")
        
        return recommendations
    
    def _identify_safe_practices(self, text: str, lines: List[str]) -> List[str]:
        """Identify good formatting practices already in use"""
        safe_practices = []
        
        # Check for good practices
        if any(line.strip().isupper() and len(line.strip()) < 30 for line in lines):
            safe_practices.append("✓ Uses clear section headers")
        
        if any(line.startswith(('-', '*')) for line in lines):
            safe_practices.append("✓ Uses standard bullet points")
        
        if not re.search(r'[|→←↑↓★◆●■▲▼]', text):
            safe_practices.append("✓ Avoids problematic special characters")
        
        word_count = len(text.split())
        if 300 <= word_count <= 800:
            safe_practices.append("✓ Appropriate resume length")
        
        # Check for standard date format
        if re.search(r'\b\w{3,9} \d{4}\b', text):
            safe_practices.append("✓ Uses standard date format")
        
        if not safe_practices:
            safe_practices.append("Consider implementing more ATS-friendly formatting practices")
        
        return safe_practices
