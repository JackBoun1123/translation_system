"""
Audio utility functions for processing audio files.

This module provides functions for loading, saving, converting,
and manipulating audio data used in the translation system.
"""

import os
import io
import numpy as np
import librosa
import soundfile as sf
from typing import List, Tuple, Optional, Union, BinaryIO

def load_audio(
    file_path: Union[str, BinaryIO], 
    sample_rate: int = 16000,
    mono: bool = True
) -> Tuple[np.ndarray, int]:
    """
    Load an audio file and convert it to the specified sample rate.
    
    Args:
        file_path: Path to audio file or file-like object
        sample_rate: Target sample rate
        mono: Whether to convert to mono
    
    Returns:
        Tuple of (audio_array, sample_rate)
    """
    audio, sr = librosa.load(file_path, sr=sample_rate, mono=mono)
    return audio, sr

def save_audio(
    audio: np.ndarray,
    file_path: str,
    sample_rate: int = 16000,
    format: str = 'wav'
) -> str:
    """
    Save audio data to a file.
    
    Args:
        audio: Audio data as numpy array
        file_path: Path to save the audio file
        sample_rate: Sample rate of the audio
        format: Audio format to save (wav, mp3, etc.)
    
    Returns:
        Path to the saved file
    """
    sf.write(file_path, audio, sample_rate, format=format)
    return file_path

def convert_sample_rate(
    audio: np.ndarray,
    orig_sample_rate: int,
    target_sample_rate: int
) -> np.ndarray:
    """
    Convert audio from one sample rate to another.
    
    Args:
        audio: Audio data as numpy array
        orig_sample_rate: Original sample rate
        target_sample_rate: Target sample rate
    
    Returns:
        Resampled audio data
    """
    if orig_sample_rate == target_sample_rate:
        return audio
    
    return librosa.resample(
        audio, 
        orig_sr=orig_sample_rate, 
        target_sr=target_sample_rate
    )

def split_audio_chunks(
    audio: np.ndarray,
    sample_rate: int,
    chunk_size_ms: int = 5000,
    overlap_ms: int = 500
) -> List[np.ndarray]:
    """
    Split audio into overlapping chunks.
    
    Args:
        audio: Audio data as numpy array
        sample_rate: Sample rate of the audio
        chunk_size_ms: Size of each chunk in milliseconds
        overlap_ms: Overlap between chunks in milliseconds
    
    Returns:
        List of audio chunks
    """
    samples_per_chunk = int(sample_rate * chunk_size_ms / 1000)
    overlap_samples = int(sample_rate * overlap_ms / 1000)
    stride = samples_per_chunk - overlap_samples
    
    # Calculate number of chunks
    num_chunks = max(1, int(np.ceil((len(audio) - overlap_samples) / stride)))
    
    chunks = []
    for i in range(num_chunks):
        start = i * stride
        end = min(start + samples_per_chunk, len(audio))
        chunks.append(audio[start:end])
        
        # Stop if we've reached the end of the audio
        if end == len(audio):
            break
            
    return chunks

def merge_audio_chunks(
    chunks: List[np.ndarray],
    overlap_ms: int = 500,
    sample_rate: int = 16000,
    crossfade: bool = True
) -> np.ndarray:
    """
    Merge overlapping audio chunks back into a single audio stream.
    
    Args:
        chunks: List of audio chunks
        overlap_ms: Overlap between chunks in milliseconds
        sample_rate: Sample rate of the audio
        crossfade: Whether to apply crossfading at merge points
    
    Returns:
        Merged audio data
    """
    if not chunks:
        return np.array([])
    
    if len(chunks) == 1:
        return chunks[0]
    
    overlap_samples = int(sample_rate * overlap_ms / 1000)
    result_length = sum(len(chunk) for chunk in chunks) - overlap_samples * (len(chunks) - 1)
    result = np.zeros(result_length, dtype=chunks[0].dtype)
    
    position = 0
    for i, chunk in enumerate(chunks):
        if i == 0:
            # First chunk: copy completely
            result[position:position + len(chunk)] = chunk
            position += len(chunk) - overlap_samples
        else:
            # Subsequent chunks: apply crossfade if enabled
            if crossfade and overlap_samples > 0:
                # Create fade-in and fade-out windows
                fade_in = np.linspace(0, 1, overlap_samples)
                fade_out = np.linspace(1, 0, overlap_samples)
                
                # Apply crossfade
                result[position:position + overlap_samples] *= fade_out
                result[position:position + overlap_samples] += chunk[:overlap_samples] * fade_in
                
                # Copy the rest of the chunk
                result[position + overlap_samples:position + len(chunk)] = chunk[overlap_samples:]
            else:
                # Simple concatenation without crossfade
                result[position:position + len(chunk) - overlap_samples] = chunk[overlap_samples:]
            
            position += len(chunk) - overlap_samples
    
    return result

def get_audio_duration(
    file_path: Union[str, BinaryIO]
) -> float:
    """
    Get the duration of an audio file in seconds.
    
    Args:
        file_path: Path to audio file or file-like object
    
    Returns:
        Duration in seconds
    """
    audio, sr = librosa.load(file_path, sr=None)
    return librosa.get_duration(y=audio, sr=sr) 
