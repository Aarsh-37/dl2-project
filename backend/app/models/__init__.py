"""Model registry. env.py imports Base from here for autogenerate."""
from app.models.base import Base
from app.models.core import (  # noqa: F401
    Analysis,
    AuthUser,
    DocumentChunk,
    JdSkill,
    JobDescription,
    Profile,
    Resume,
    ResumeSkill,
    ResumeVersion,
    Skill,
    SkillGap,
)
from app.models.kb import KbChunk, LearningResource, QuestionBank  # noqa: F401

__all__ = [
    "Base", "Analysis", "AuthUser", "DocumentChunk", "JdSkill", "JobDescription",
    "Profile", "Resume", "ResumeSkill", "ResumeVersion", "Skill", "SkillGap",
    "LearningResource", "QuestionBank", "KbChunk",
]
