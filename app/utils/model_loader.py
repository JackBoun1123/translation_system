"""
Model loading utilities for the translation system.

This module provides functions for loading, downloading, and verifying
machine learning models used in the translation system.
"""

import os
import json
import hashlib
import requests
import logging
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import torch

# Configure logger
logger = logging.getLogger(__name__)

# Default locations
DEFAULT_MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models")
MODEL_REGISTRY_URL = "https://api.example.org/model-registry/v1"  # Replace with actual registry URL

class ModelNotFoundError(Exception):
    """Exception raised when a model is not found."""
    pass

class ModelVersionError(Exception):
    """Exception raised when there's a version incompatibility."""
    pass

class DownloadError(Exception):
    """Exception raised when model download fails."""
    pass

def get_model_path(model_name: str, model_type: str, version: Optional[str] = None) -> str:
    """
    Get the path to a model on disk.
    
    Args:
        model_name: Name of the model
        model_type: Type of model (asr, tts, translation, context)
        version: Model version, defaults to latest
        
    Returns:
        Path to the model file
    """
    model_dir = os.environ.get("MODEL_DIR", DEFAULT_MODEL_DIR)
    
    # If version is not specified, try to find the latest version
    if version is None:
        version_dirs = []
        base_path = os.path.join(model_dir, model_type, model_name)
        
        if os.path.exists(base_path):
            for item in os.listdir(base_path):
                if os.path.isdir(os.path.join(base_path, item)) and item.startswith('v'):
                    version_dirs.append(item)
        
        if version_dirs:
            # Sort versions and get the latest
            version = sorted(version_dirs, key=lambda x: [int(n) for n in x[1:].split('.')])[-1]
        else:
            raise ModelNotFoundError(
                f"No versions found for model {model_name} of type {model_type}"
            )
    
    model_path = os.path.join(model_dir, model_type, model_name, f"v{version}" if not version.startswith('v') else version)
    
    if not os.path.exists(model_path):
        raise ModelNotFoundError(
            f"Model path not found: {model_path}"
        )
    
    return model_path

def check_model_exists(model_name: str, model_type: str, version: Optional[str] = None) -> bool:
    """
    Check if a model exists on disk.
    
    Args:
        model_name: Name of the model
        model_type: Type of model (asr, tts, translation, context)
        version: Model version, defaults to latest
        
    Returns:
        True if model exists, False otherwise
    """
    try:
        get_model_path(model_name, model_type, version)
        return True
    except ModelNotFoundError:
        return False

def get_model_info(model_name: str, model_type: str, version: Optional[str] = None) -> Dict[str, Any]:
    """
    Get information about a model from its metadata file.
    
    Args:
        model_name: Name of the model
        model_type: Type of model (asr, tts, translation, context)
        version: Model version, defaults to latest
        
    Returns:
        Dictionary containing model metadata
    """
    model_path = get_model_path(model_name, model_type, version)
    metadata_path = os.path.join(model_path, "metadata.json")
    
    if not os.path.exists(metadata_path):
        raise ModelNotFoundError(
            f"Model metadata not found: {metadata_path}"
        )
    
    with open(metadata_path, 'r') as f:
        return json.load(f)

def download_model(
    model_name: str, 
    model_type: str, 
    version: Optional[str] = None,
    force: bool = False
) -> str:
    """
    Download a model from the model registry.
    
    Args:
        model_name: Name of the model
        model_type: Type of model (asr, tts, translation, context)
        version: Model version, defaults to latest
        force: Force download even if model exists
        
    Returns:
        Path to the downloaded model
    """
    # Check if model already exists
    try:
        model_path = get_model_path(model_name, model_type, version)
        if os.path.exists(model_path) and not force:
            logger.info(f"Model already exists at {model_path}")
            return model_path
    except ModelNotFoundError:
        # Model doesn't exist, continue with download
        pass
    
    # Create model directory
    model_dir = os.environ.get("MODEL_DIR", DEFAULT_MODEL_DIR)
    if version is None:
        # Query API for latest version
        response = requests.get(
            f"{MODEL_REGISTRY_URL}/models/{model_type}/{model_name}/latest"
        )
        response.raise_for_status()
        version_info = response.json()
        version = version_info["version"]
    
    # Ensure version format
    if not version.startswith('v'):
        version = f"v{version}"
    
    model_path = os.path.join(model_dir, model_type, model_name, version)
    os.makedirs(model_path, exist_ok=True)
    
    # Download model files
    response = requests.get(
        f"{MODEL_REGISTRY_URL}/models/{model_type}/{model_name}/{version}/files"
    )
    response.raise_for_status()
    file_list = response.json()["files"]
    
    for file_info in file_list:
        file_url = file_info["url"]
        file_path = os.path.join(model_path, file_info["filename"])
        file_hash = file_info["md5"]
        
        # Download file
        logger.info(f"Downloading {file_info['filename']} to {file_path}")
        response = requests.get(file_url, stream=True)
        response.raise_for_status()
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Verify file hash
        with open(file_path, 'rb') as f:
            file_data = f.read()
            calculated_hash = hashlib.md5(file_data).hexdigest()
        
        if calculated_hash != file_hash:
            os.remove(file_path)
            raise DownloadError(
                f"Hash mismatch for {file_path}. Expected {file_hash}, got {calculated_hash}"
            )
    
    # Download metadata
    response = requests.get(
        f"{MODEL_REGISTRY_URL}/models/{model_type}/{model_name}/{version}/metadata"
    )
    response.raise_for_status()
    metadata = response.json()
    
    with open(os.path.join(model_path, "metadata.json"), 'w') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info(f"Model downloaded to {model_path}")
    return model_path

def verify_model_compatibility(model_info: Dict[str, Any], system_version: str) -> bool:
    """
    Verify that a model is compatible with the current system version.
    
    Args:
        model_info: Dictionary containing model metadata
        system_version: Current system version
        
    Returns:
        True if compatible, False otherwise
    """
    model_min_version = model_info.get("min_system_version", "0.0.0")
    model_max_version = model_info.get("max_system_version", "999.999.999")
    
    # Parse versions into tuples for comparison
    def parse_version(v: str) -> tuple:
        return tuple(map(int, v.replace('v', '').split('.')))
    
    sys_version = parse_version(system_version)
    min_version = parse_version(model_min_version)
    max_version = parse_version(model_max_version)
    
    return min_version <= sys_version <= max_version

def load_model(
    model_name: str, 
    model_type: str, 
    version: Optional[str] = None,
    device: Optional[str] = None,
    system_version: Optional[str] = None
) -> Any:
    """
    Load a model for use.
    
    Args:
        model_name: Name of the model
        model_type: Type of model (asr, tts, translation, context)
        version: Model version, defaults to latest
        device: Device to load the model on (cpu, cuda:0, etc.)
        system_version: Current system version for compatibility check
        
    Returns:
        Loaded model object
    """
    # Get model path
    try:
        model_path = get_model_path(model_name, model_type, version)
    except ModelNotFoundError:
        # Try to download the model if not found
        model_path = download_model(model_name, model_type, version)
    
    # Check model compatibility if system version provided
    if system_version is not None:
        model_info = get_model_info(model_name, model_type, version)
        if not verify_model_compatibility(model_info, system_version):
            raise ModelVersionError(
                f"Model {model_name} (version {version}) is not compatible with system version {system_version}"
            )
    
    # Determine device
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    # Load model based on type
    if model_type == "asr":
        return _load_asr_model(model_path, device)
    elif model_type == "translation":
        return _load_translation_model(model_path, device)
    elif model_type == "tts":
        return _load_tts_model(model_path, device)
    elif model_type == "context":
        return _load_context_model(model_path, device)
    else:
        raise ValueError(f"Unknown model type: {model_type}")

def _load_asr_model(model_path: str, device: str) -> Any:
    """Load ASR model logic"""
    # This would be implemented with actual ASR model loading code
    # For example, using transformers, fairseq, ESPnet, etc.
    logger.info(f"Loading ASR model from {model_path} on {device}")
    
    # Placeholder for actual implementation
    model_file = os.path.join(model_path, "model.pt")
    config_file = os.path.join(model_path, "config.json")
    
    # Load model configuration
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Here you would use the appropriate library to load the model
    # Example: model = YourASRLibrary.load_model(model_file, config, device=device)
    model = f"ASR model loaded from {model_path}"  # Placeholder
    
    return model

def _load_translation_model(model_path: str, device: str) -> Any:
    """Load Translation model logic"""
    # Similar placeholder implementation as ASR model loading
    logger.info(f"Loading Translation model from {model_path} on {device}")
    return f"Translation model loaded from {model_path}"

def _load_tts_model(model_path: str, device: str) -> Any:
    """Load TTS model logic"""
    # Similar placeholder implementation as ASR model loading
    logger.info(f"Loading TTS model from {model_path} on {device}")
    return f"TTS model loaded from {model_path}"

def _load_context_model(model_path: str, device: str) -> Any:
    """Load Context model logic"""
    # Similar placeholder implementation as ASR model loading
    logger.info(f"Loading Context model from {model_path} on {device}")
    return f"Context model loaded from {model_path}" 
