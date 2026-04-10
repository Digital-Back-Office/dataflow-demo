import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import Dict, List, Tuple, Optional
import re
from collections import Counter

class DashboardComponents:
    """Modern ATS Dashboard UI Components"""
    
    @staticmethod
    def inject_dashboard_css():
        """Inject professional dark dashboard CSS"""
        st.markdown("""
        <style>
        /* Professional Dark Dashboard Theme */
        :root {
            --primary-bg: #0f172a;
            --secondary-bg: #1e293b;
            --accent-color: #3b82f6;
            --accent-hover: #2563eb;
            --text-primary: #ffffff;
            --text-secondary: #cbd5e1;
            --border-color: #334155;
            --success-color: #10b981;
            --warning-color: #f59e0b;
            --error-color: #ef4444;
            --card-bg: #1e293b;
            --card-border: #334155;
        }

        /* Global Styles */
        .stApp {
            background-color: var(--primary-bg);
            color: var(--text-primary);
        }

        .main .block-container {
            background-color: var(--primary-bg);
            color: var(--text-primary);
            padding: 2rem;
            max-width: 1400px;
        }

        /* Dashboard Cards */
        .dashboard-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 1.5rem;
            margin: 1rem 0;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: all 0.3s ease;
        }

        .dashboard-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 12px rgba(0, 0, 0, 0.15);
            border-color: var(--accent-color);
        }

        /* Match Score Cards */
        .match-score-card {
            background: linear-gradient(135deg, var(--card-bg) 0%, var(--secondary-bg) 100%);
            border: 1px solid var(--card-border);
            border-radius: 16px;
            padding: 2rem;
            text-align: center;
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .match-score-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--accent-color) 0%, var(--accent-hover) 100%);
        }

        .match-score-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.3);
        }

        .score-value {
            font-size: 3rem;
            font-weight: 700;
            color: var(--accent-color);
            margin-bottom: 0.5rem;
            line-height: 1;
        }

        .score-label {
            font-size: 1rem;
            color: var(--text-secondary);
            font-weight: 500;
            margin-top: 0.5rem;
        }

        /* Section Headers */
        .section-header {
            background: var(--secondary-bg);
            border-left: 4px solid var(--accent-color);
            padding: 1rem 1.5rem;
            margin: 2rem 0 1rem 0;
            border-radius: 8px;
            font-weight: 600;
            font-size: 1.3rem;
            color: var(--text-primary);
        }

        /* Tabs */
        .stTabs [data-baseweb="tab1"] {
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 0.5rem 1rem;
            margin: 0.25rem;
            color: var(--text-primary);
        }

        .stTabs [data-baseweb="tab1"][aria-selected="true"] {
            background-color: var(--accent-color);
            color: white;
        }

        /* Keyword Tags */
        .keyword-tag {
            display: inline-block;
            background: var(--accent-color);
            color: white;
            padding: 0.25rem 0.75rem;
            margin: 0.25rem;
            border-radius: 1rem;
            font-size: 0.85rem;
            font-weight: 500;
        }

        /* Skill Tables */
        .skill-table {
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
        }

        .skill-table th,
        .skill-table td {
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-primary);
        }

        .skill-table th {
            background-color: var(--secondary-bg);
            font-weight: 600;
        }

        .skill-present {
            color: var(--success-color);
            font-weight: 600;
        }

        .skill-missing {
            color: var(--error-color);
            font-weight: 600;
        }

        /* Checklist Items */
        .checklist-item {
            display: flex;
            align-items: center;
            padding: 0.5rem 0;
            color: var(--text-primary);
        }

        .checklist-icon {
            margin-right: 0.75rem;
            font-weight: bold;
        }

        /* ATS Parsing Preview */
        .ats-preview {
            background: var(--secondary-bg);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 1.5rem;
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
            color: var(--text-primary);
        }

        .ats-preview-section {
            margin-bottom: 1rem;
        }

        .ats-preview-title {
            color: var(--accent-color);
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        </style>
        """, unsafe_allow_html=True)

    @staticmethod
    def create_match_score_card(score: int, title: str) -> str:
        """Create match score card with donut chart"""
        # Create donut chart
        fig = go.Figure(data=[go.Pie(
            values=[score, 100-score],
            hole=0.7,
            showlegend=False,
            textinfo='none',
            hoverinfo='none'
        )])
        
        fig.update_traces(
            marker=dict(colors=['#3b82f6', '#1e293b'])
        )
        
        fig.update_layout(
            margin=dict(t=0, b=0, l=0, r=0),
            height=200,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        
        # Add score text in center
        fig.add_annotation(
            text=f'{score}%',
            x=0.5, y=0.5,
            font_size=24,
            font_color='white',
            showarrow=False
        )
        
        return fig

    @staticmethod
    def create_readiness_assessment(score: int) -> str:
        """Generate readiness assessment text"""
        if score >= 80:
            status = "Excellent match"
            message = f"Your resume is very well-aligned with the job requirements. With a score of {score}%, you have a strong chance of getting past ATS filters."
        elif score >= 60:
            status = "Decent match"
            message = f"Consider updating your resume to improve your chances. Your overall score is {score}%. Some improvements are recommended for a stronger application."
        else:
            status = "Needs improvement"
            message = f"Your resume needs significant updates to match job requirements. With a score of {score}%, we recommend major improvements before applying."
        
        return status, message

    @staticmethod
    def create_skill_radar_chart(resume_skills: Dict, job_skills: Dict) -> go.Figure:
        """Create radar chart comparing skills"""
        categories = list(set(list(resume_skills.keys()) + list(job_skills.keys())))
        
        # Normalize scores (0-100)
        resume_values = []
        job_values = []
        
        for category in categories:
            resume_score = resume_skills.get(category, 0)
            job_score = job_skills.get(category, 0)
            
            # Normalize to percentage
            max_score = max(resume_score, job_score, 1)
            resume_values.append((resume_score / max_score) * 100 if max_score > 0 else 0)
            job_values.append((job_score / max_score) * 100 if max_score > 0 else 0)
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatterpolar(
            r=resume_values,
            theta=categories,
            fill='toself',
            name='Your Resume',
            line_color='#3b82f6',
            fillcolor='rgba(59, 130, 246, 0.25)'
        ))
        
        fig.add_trace(go.Scatterpolar(
            r=job_values,
            theta=categories,
            fill='toself',
            name='Job Requirements',
            line_color='#ef4444',
            fillcolor='rgba(239, 68, 68, 0.25)'
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    color='white'
                ),
                angularaxis=dict(
                    color='white',
                    gridcolor='#334155'
                )
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        return fig

    @staticmethod
    def create_keyword_density_chart(keywords: List[str], frequencies: List[int]) -> go.Figure:
        """Create keyword density bar chart"""
        fig = go.Figure(data=[
            go.Bar(
                x=keywords,
                y=frequencies,
                marker_color='#3b82f6',
                text=frequencies,
                textposition='auto',
            )
        ])
        
        fig.update_layout(
            xaxis=dict(
                title='Keywords',
                color='white',
                gridcolor='#334155'
            ),
            yaxis=dict(
                title='Frequency in Resume',
                color='white',
                gridcolor='#334155'
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            margin=dict(l=50, r=50, t=50, b=50)
        )
        
        return fig

    @staticmethod
    def create_skill_comparison_table(resume_skills: List[str], job_skills: List[str], skill_type: str) -> pd.DataFrame:
        """Create skill comparison table"""
        data = []
        
        all_skills = list(set(resume_skills + job_skills))
        
        for skill in all_skills:
            in_resume = skill in resume_skills
            in_job = skill in job_skills
            
            data.append({
                'Skill': skill,
                'Your Resume': '✓' if in_resume else '✗',
                'Job Description': '✓' if in_job else '✗'
            })
        
        df = pd.DataFrame(data)
        return df

    @staticmethod
    def extract_skills_from_text(text: str, skill_categories: Dict[str, List[str]]) -> Dict[str, int]:
        """Extract and categorize skills from text"""
        text_lower = text.lower()
        skill_counts = {}
        
        for category, skills in skill_categories.items():
            count = 0
            for skill in skills:
                # Count occurrences of each skill
                pattern = r'\b' + re.escape(skill.lower()) + r'\b'
                matches = re.findall(pattern, text_lower)
                count += len(matches)
            
            skill_counts[category] = count
        
        return skill_counts

    @staticmethod
    def create_ats_parsing_preview(resume_data: Dict) -> str:
        """Create ATS parsing preview"""
        preview_html = """
        <div class="ats-preview">
            <div class="ats-preview-section">
                <div class="ats-preview-title">📋 CONTACT INFORMATION</div>
                <div class="ats-preview-content">
        """
        
        if resume_data.get('contact'):
            contact = resume_data['contact']
            preview_html += f"""
                    Name: {contact.get('name', 'Not detected')}<br>
                    Email: {contact.get('email', 'Not detected')}<br>
                    Phone: {contact.get('phone', 'Not detected')}
            """
        
        preview_html += """
                </div>
            </div>
            <div class="ats-preview-section">
                <div class="ats-preview-title">💼 SKILLS DETECTED</div>
                <div class="ats-preview-content">
        """
        
        if resume_data.get('skills'):
            skills = resume_data['skills']
            for skill in skills[:10]:  # Limit to first 10 skills
                preview_html += f"• {skill}<br>"
        
        preview_html += """
                </div>
            </div>
            <div class="ats-preview-section">
                <div class="ats-preview-title">🎓 EXPERIENCE DETECTED</div>
                <div class="ats-preview-content">
        """
        
        if resume_data.get('experience'):
            for exp in resume_data['experience'][:3]:  # Limit to first 3 experiences
                preview_html += f"• {exp}<br>"
        
        preview_html += """
                </div>
            </div>
            <div class="ats-preview-section">
                <div class="ats-preview-title">📚 EDUCATION DETECTED</div>
                <div class="ats-preview-content">
        """
        
        if resume_data.get('education'):
            for edu in resume_data['education'][:2]:  # Limit to first 2 education entries
                preview_html += f"• {edu}<br>"
        
        preview_html += """
                </div>
            </div>
        </div>
        """
        
        return preview_html

    @staticmethod
    def create_keyword_tags(keywords: List[str]) -> str:
        """Create keyword tags from list"""
        tags = []
        for keyword in keywords:
            tags.append(f'<span class="keyword-tag">{keyword}</span>')
        return ' '.join(tags)

    @staticmethod
    def create_checklist(items: List[Tuple[str, bool]]) -> str:
        """Create checklist HTML"""
        checklist_html = ""
        for item, checked in items:
            icon = "✓" if checked else "✗"
            color = "#10b981" if checked else "#ef4444"
            checklist_html += f"""
            <div class="checklist-item">
                <span class="checklist-icon" style="color: {color};">{icon}</span>
                {item}
            </div>
            """
        return checklist_html
