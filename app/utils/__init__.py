"""
Utils package initialization.

This file marks the 'utils' directory as a Python package and imports
all utility functions for easier access from other parts of the application.
"""

from .audio_utils import (
    load_audio,
    save_audio,
    convert_sample_rate,
    split_audio_chunks,
    merge_audio_chunks,
    get_audio_duration
)

from .text_utils import (
    normalize_text,
    segment_text,
    clean_transcript,
    detect_language,
    format_subtitles
)

from .model_loader import (
    load_model,
    download_model,
    check_model_exists,
    get_model_info,
    verify_model_compatibility
)

__all__ = [
    # Audio utilities
    'load_audio',
    'save_audio',
    'convert_sample_rate',
    'split_audio_chunks',
    'merge_audio_chunks',
    'get_audio_duration',
    
    # Text utilities
    'normalize_text',
    'segment_text',
    'clean_transcript',
    'detect_language',
    'format_subtitles',
    
    # Model loading utilities
    'load_model',
    'download_model',
    'check_model_exists',
    'get_model_info',
    'verify_model_compatibility'
] 
