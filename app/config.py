"""
Cấu hình cho ứng dụng dịch thuật theo thời gian thực
"""
import os
from pathlib import Path

# Đường dẫn cơ bản
BASE_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
CONTEXT_DIR = DATA_DIR / "context"
CACHE_DIR = DATA_DIR / "cache"
MODEL_DIR = STATIC_DIR / "models"

# Tạo thư mục nếu chưa tồn tại
for dir_path in [STATIC_DIR, DATA_DIR, CONTEXT_DIR, CACHE_DIR, MODEL_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# Cấu hình ASR (Whisper)
ASR_CONFIG = {
    "model_size": "small",  # Có thể là: "tiny", "base", "small", "medium", "large"
    "device": "cuda" if os.environ.get("USE_CUDA", "0") == "1" else "cpu",
    "compute_type": "int8", # Quantization: "float16", "int8"
    "language": "vi",  # Ngôn ngữ mặc định đầu vào
    "download_root": MODEL_DIR / "whisper"
}

# Cấu hình dịch thuật (NLLB)
TRANSLATION_CONFIG = {
    "model_name": "facebook/nllb-200-distilled-600M",  # Mô hình dịch
    "target_language": "eng_Latn",  # Ngôn ngữ mặc định đầu ra
    "source_language": "vie_Latn",  # Ngôn ngữ mặc định đầu vào
    "device": "cuda" if os.environ.get("USE_CUDA", "0") == "1" else "cpu",
    "compute_type": "int8",
    "download_root": MODEL_DIR / "nllb"
}

# Cấu hình TTS (Piper)
TTS_CONFIG = {
    "model_name": "en_US-lessac-medium",
    "download_root": MODEL_DIR / "tts",
    "sample_rate": 22050
}

# Cấu hình Context Vector DB (ChromaDB)
CONTEXT_DB_CONFIG = {
    "persist_directory": CACHE_DIR / "chroma",
    "embedding_model": "all-MiniLM-L6-v2",
    "embedding_dimension": 384
}

# Cấu hình bộ nhớ đệm
CACHE_CONFIG = {
    "translation_cache_size": 10000,
    "asr_cache_size": 1000,
    "tts_cache_size": 1000
}

# Cấu hình API
API_CONFIG = {
    "host": "0.0.0.0",
    "port": 8000,
    "debug": True,
    "reload": True
}

# Cấu hình âm thanh
AUDIO_CONFIG = {
    "sample_rate": 16000,
    "channels": 1,
    "chunk_size": 4096,
    "silence_threshold": 300,  # Ngưỡng im lặng để phân đoạn
    "min_silence_duration": 0.5  # Thời gian im lặng tối thiểu (giây)
}

# Ngôn ngữ hỗ trợ
SUPPORTED_LANGUAGES = {
    "vi": {
        "name": "Vietnamese",
        "code": "vie_Latn",
        "tts_model": "vi_VN-prosody-medium"
    },
    "en": {
        "name": "English",
        "code": "eng_Latn",
        "tts_model": "en_US-lessac-medium"
    },
    # Thêm nhiều ngôn ngữ khác tại đây
}