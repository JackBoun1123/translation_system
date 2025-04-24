"""
Text utility functions for processing text data.

This module provides functions for normalizing, segmenting, and processing
text data used in the translation system.
"""

import re
import unicodedata
import string
from typing import List, Dict, Optional, Tuple, Union
import nltk
from nltk.tokenize import sent_tokenize
import langid
import pycountry

# Initialize NLTK resources if not already downloaded
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

def normalize_text(text: str, lowercase: bool = True, remove_punctuation: bool = False) -> str:
    """
    Normalize text by converting to lowercase, removing extra spaces,
    and optionally removing punctuation.
    
    Args:
        text: Input text to normalize
        lowercase: Whether to convert text to lowercase
        remove_punctuation: Whether to remove punctuation
    
    Returns:
        Normalized text
    """
    # Convert to lowercase if requested
    if lowercase:
        text = text.lower()
    
    # Remove punctuation if requested
    if remove_punctuation:
        text = text.translate(str.maketrans('', '', string.punctuation))
    
    # Normalize unicode characters
    text = unicodedata.normalize('NFKC', text)
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def segment_text(
    text: str, 
    max_length: int = 100, 
    respect_sentences: bool = True,
    lang: Optional[str] = None
) -> List[str]:
    """
    Segment text into chunks, respecting sentence boundaries when possible.
    
    Args:
        text: Input text to segment
        max_length: Maximum length of each segment
        respect_sentences: Whether to respect sentence boundaries
        lang: Language code for sentence tokenization (auto-detect if None)
    
    Returns:
        List of text segments
    """
    if not text:
        return []
    
    # If text is shorter than max_length, return as is
    if len(text) <= max_length:
        return [text]
    
    # Detect language if not provided
    if lang is None:
        lang, _ = detect_language(text)
    
    if respect_sentences:
        # Split by sentences first
        sentences = sent_tokenize(text, language=lang[:2] if lang else 'english')
        
        segments = []
        current_segment = ""
        
        for sentence in sentences:
            # If single sentence is longer than max_length, split it
            if len(sentence) > max_length:
                if current_segment:
                    segments.append(current_segment.strip())
                    current_segment = ""
                
                # Split long sentence by punctuation or just by characters
                words = sentence.split()
                temp_segment = ""
                
                for word in words:
                    if len(temp_segment) + len(word) + 1 <= max_length:
                        if temp_segment:
                            temp_segment += " "
                        temp_segment += word
                    else:
                        segments.append(temp_segment.strip())
                        temp_segment = word
                
                if temp_segment:
                    segments.append(temp_segment.strip())
            else:
                # Normal case: try to add sentence to current segment
                if len(current_segment) + len(sentence) + 1 <= max_length:
                    if current_segment:
                        current_segment += " "
                    current_segment += sentence
                else:
                    segments.append(current_segment.strip())
                    current_segment = sentence
        
        if current_segment:
            segments.append(current_segment.strip())
    else:
        # Simple splitting by max_length
        segments = [text[i:i+max_length] for i in range(0, len(text), max_length)]
    
    return segments

def clean_transcript(text: str, remove_hesitations: bool = True, fix_common_errors: bool = True) -> str:
    """
    Clean ASR transcript text by removing hesitations, fixing common errors, etc.
    
    Args:
        text: Input transcript text
        remove_hesitations: Whether to remove hesitation markers (um, uh, etc.)
        fix_common_errors: Whether to correct common ASR errors
    
    Returns:
        Cleaned transcript text
    """
    # Remove speaker labels/timestamps if present
    text = re.sub(r'\[.*?\]', '', text)
    
    if remove_hesitations:
        # Remove common hesitation markers
        hesitation_patterns = [
            r'\b(um|uh|er|mm|hmm|huh)\b',
            r'\b(like|you know|i mean)\b',
            r'\.\.\.',
        ]
        for pattern in hesitation_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    if fix_common_errors:
        # Fix common ASR errors (example replacements)
        common_fixes = {
            r'\bi\s+m\b': "I'm",
            r'\byou\s+re\b': "you're",
            r'\bwe\s+re\b': "we're",
            r'\bthey\s+re\b': "they're",
            r'\bit\s+s\b': "it's",
            r'\bdon\s+t\b': "don't",
            r'\bcan\s+t\b': "can't",
            r'\bwon\s+t\b': "won't",
            r'\blet\s+s\b': "let's",
        }
        
        for pattern, replacement in common_fixes.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Fix capitalization at the beginning of sentences
    text = re.sub(r'(?<=[.!?]\s)([a-z])', lambda m: m.group(1).upper(), text)
    text = text[0].upper() + text[1:] if text else text
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def detect_language(text: str) -> Tuple[str, float]:
    """
    Detect the language of a text.
    
    Args:
        text: Input text
    
    Returns:
        Tuple of (language_code, confidence)
    """
    lang, confidence = langid.classify(text)
    
    # Convert to full language name if possible
    try:
        language = pycountry.languages.get(alpha_2=lang)
        lang_name = language.name if language else lang
    except:
        lang_name = lang
    
    return lang, confidence

def format_subtitles(
    segments: List[Dict[str, Union[str, float, int]]],
    format: str = 'srt'
) -> str:
    """
    Format time-aligned text segments as subtitles.
    
    Args:
        segments: List of segment dictionaries with text, start_time, and end_time
        format: Subtitle format (srt, vtt)
    
    Returns:
        Formatted subtitle string
    """
    if format.lower() == 'srt':
        output = []
        for i, segment in enumerate(segments):
            # Format timestamps as HH:MM:SS,mmm
            start = _format_time_srt(segment['start_time'])
            end = _format_time_srt(segment['end_time'])
            
            output.append(f"{i+1}")
            output.append(f"{start} --> {end}")
            output.append(segment['text'])
            output.append("")  # Empty line between entries
        
        return "\n".join(output)
    
    elif format.lower() == 'vtt':
        output = ["WEBVTT", ""]
        for i, segment in enumerate(segments):
            # Format timestamps as HH:MM:SS.mmm
            start = _format_time_vtt(segment['start_time'])
            end = _format_time_vtt(segment['end_time'])
            
            output.append(f"{start} --> {end}")
            output.append(segment['text'])
            output.append("")  # Empty line between entries
        
        return "\n".join(output)
    
    else:
        raise ValueError(f"Unsupported subtitle format: {format}")

def _format_time_srt(seconds: float) -> str:
    """Format time in seconds to SRT timestamp format: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{int((seconds % 1) * 1000):03d}"

def _format_time_vtt(seconds: float) -> str:
    """Format time in seconds to VTT timestamp format: HH:MM:SS.mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{int(seconds):02d}.{int((seconds % 1) * 1000):03d}" 
