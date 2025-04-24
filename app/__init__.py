"""
Hệ thống dịch thuật đa ngôn ngữ với các tính năng nhận dạng giọng nói, dịch thuật và tổng hợp giọng nói.

Mô-đun này khởi tạo gói ứng dụng và cung cấp các thành phần cần thiết cho 
hệ thống dịch thuật. Nó cũng cung cấp cấu hình mặc định và các hàm tiện ích.
"""

import os
import json
import logging
from typing import Dict, Any

# Thiết lập logger
logger = logging.getLogger(__name__)

# Thông tin phiên bản
__version__ = "1.0.0"

# Đường dẫn mặc định
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
DEFAULT_MODELS_DIR = os.path.join(os.path.dirname(__file__), 'static', 'models')
DEFAULT_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
DEFAULT_CONTEXT_DIR = os.path.join(DEFAULT_DATA_DIR, 'context')
DEFAULT_CACHE_DIR = os.path.join(DEFAULT_DATA_DIR, 'cache')

# Đảm bảo các thư mục tồn tại
for directory in [DEFAULT_MODELS_DIR, DEFAULT_DATA_DIR, DEFAULT_CONTEXT_DIR, DEFAULT_CACHE_DIR]:
    os.makedirs(directory, exist_ok=True)

def load_config(config_path: str = None) -> Dict[str, Any]:
    """
    Tải cấu hình từ tệp JSON.
    
    Args:
        config_path: Đường dẫn tới tệp cấu hình. Nếu None, sử dụng đường dẫn mặc định.
    
    Returns:
        Từ điển cấu hình.
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH
    
    # Kiểm tra nếu tệp cấu hình tồn tại
    if not os.path.exists(config_path):
        logger.warning(f"Không tìm thấy tệp cấu hình tại {config_path}. Sử dụng cấu hình mặc định.")
        return get_default_config()
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            logger.info(f"Đã tải cấu hình từ {config_path}")
            return config
    except Exception as e:
        logger.error(f"Lỗi khi tải cấu hình: {str(e)}")
        return get_default_config()

def get_default_config() -> Dict[str, Any]:
    """
    Tạo cấu hình mặc định.
    
    Returns:
        Từ điển cấu hình mặc định.
    """
    return {
        "version": __version__,
        "audio": {
            "sample_rate": 16000,
            "channels": 1
        },
        "models": {
            "asr": {
                "default": "whisper-base",
                "languages": ["vi", "en", "fr", "zh"]
            },
            "translation": {
                "default": "m2m100",
                "languages": ["vi", "en", "fr", "zh"]
            },
            "tts": {
                "default": "espeak",
                "voices": {
                    "vi": "vi",
                    "en": "en",
                    "fr": "fr"
                }
            }
        },
        "paths": {
            "models_dir": DEFAULT_MODELS_DIR,
            "data_dir": DEFAULT_DATA_DIR,
            "context_dir": DEFAULT_CONTEXT_DIR,
            "cache_dir": DEFAULT_CACHE_DIR
        }
    }

def save_config(config: Dict[str, Any], config_path: str = None) -> bool:
    """
    Lưu cấu hình vào tệp JSON.
    
    Args:
        config: Từ điển cấu hình cần lưu.
        config_path: Đường dẫn tới tệp cấu hình. Nếu None, sử dụng đường dẫn mặc định.
    
    Returns:
        True nếu lưu thành công, False nếu thất bại.
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info(f"Đã lưu cấu hình vào {config_path}")
            return True
    except Exception as e:
        logger.error(f"Lỗi khi lưu cấu hình: {str(e)}")
        return False

# Các ngôn ngữ được hỗ trợ
SUPPORTED_LANGUAGES = {
    "vi": "Tiếng Việt",
    "en": "Tiếng Anh",
    "fr": "Tiếng Pháp",
    "de": "Tiếng Đức",
    "ja": "Tiếng Nhật",
    "ko": "Tiếng Hàn",
    "zh": "Tiếng Trung",
    "es": "Tiếng Tây Ban Nha",
    "ru": "Tiếng Nga"
} 
