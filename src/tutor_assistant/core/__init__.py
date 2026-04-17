"""Shared core utilities and integrations."""

from .auth import GOOGLE_ONBOARDING_SCOPES, load_google_credentials
from .utils import slugify

__all__ = ["GOOGLE_ONBOARDING_SCOPES", "load_google_credentials", "slugify"]
