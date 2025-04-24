"""
Views package initialization.

This file marks the 'views' directory as a Python package and imports
all view classes for easier access from other parts of the application.
"""

from .cli_view import CLIView
from .api_view import APIView

__all__ = [
    'CLIView',
    'APIView'
] 
