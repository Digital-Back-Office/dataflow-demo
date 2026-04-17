import os

class Config:
    """Configuration class that prioritizes environment variables (Dataflow secrets)"""

    def __init__(self):
        # Load API Keys from environment (Dataflow secrets)
        self.GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
        self.OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

        # Validate keys
        if not self.GROQ_API_KEY and not self.OPENROUTER_API_KEY:
            raise ValueError(
                "No API keys found. Please set GROQ_API_KEY or OPENROUTER_API_KEY in environment variables (Dataflow secrets)."
            )

        # AI Model Configuration
        self.PREFERRED_AI_PROVIDER = os.environ.get("PREFERRED_AI_PROVIDER", "groq")
        self.GROQ_MODEL = os.environ.get("GROQ_MODEL", "mixtral-8x7b-32768")
        self.OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-3-haiku")

        # ATS Scoring Weights
        self.SKILL_MATCH_WEIGHT = 0.4
        self.EXPERIENCE_MATCH_WEIGHT = 0.3
        self.KEYWORD_DENSITY_WEIGHT = 0.2
        self.FORMAT_COMPATIBILITY_WEIGHT = 0.1

        # File Upload Limits
        self.MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
        self.ALLOWED_EXTENSIONS = ['pdf', 'docx']

        # LaTeX Template Path
        self.LATEX_TEMPLATE_DIR = "templates/latex"

        # Output Directory
        self.OUTPUT_DIR = "output"