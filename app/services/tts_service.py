"""
Dịch vụ xử lý tổng hợp giọng nói (TTS)
"""
import logging
import hashlib
import numpy as np
from typing import Dict, Optional, Union, Tuple
import soundfile as sf
import tempfile
import os
from app.models.tts_model import TTSModel
from app.services.cache_service import CacheService
from app.config import SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self, cache_service: Optional[CacheService] = None):
        """
        Khởi tạo dịch vụ TTS
        
        Args:
            cache_service: Dịch vụ cache để tái sử dụng kết quả TTS
        """
        self.tts_model = TTSModel()
        self.cache_service = cache_service
        self.models = {}  # Cache cho các mô hình TTS khác nhau
        logger.info("Đã khởi tạo dịch vụ TTS")
    
    def synthesize(self, text: str, lang_code: str = "en") -> np.ndarray:
        """
        Tổng hợp giọng nói từ văn bản
        
        Args:
            text: Văn bản cần tổng hợp giọng nói
            lang_code: Mã ngôn ngữ
            
        Returns:
            np.ndarray: Dữ liệu âm thanh
        """
        # Tính hash của văn bản để lưu cache
        text_hash = self._compute_text_hash(text)
        
        # Lấy model tương ứng với ngôn ngữ
        model_name = self._get_tts_model_for_language(lang_code)
        
        # Kiểm tra cache trước khi tổng hợp
        if self.cache_service:
            cached_audio = self.cache_service.get_tts_audio(text_hash, model_name)
            if cached_audio is not None:
                logger.info("Đã tìm thấy âm thanh TTS trong cache")
                # Chuyển từ bytes sang numpy array
                return self._bytes_to_audio(cached_audio)
        
        # Tổng hợp giọng nói
        audio_data = self.tts_model.synthesize(text)
        
        # Lưu vào cache
        if self.cache_service:
            # Chuyển từ numpy array sang bytes để lưu cache
            audio_bytes = self._audio_to_bytes(audio_data)
            self.cache_service.store_tts_audio(text_hash, model_name, audio_bytes)
        
        return audio_data
    
    def synthesize_and_save(self, text: str, output_path: str, lang_code: str = "en") -> bool:
        """
        Tổng hợp giọng nói và lưu vào file
        
        Args:
            text: Văn bản cần tổng hợp giọng nói
            output_path: Đường dẫn file đầu ra
            lang_code: Mã ngôn ngữ
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        try:
            # Lấy model tương ứng với ngôn ngữ
            model_name = self._get_tts_model_for_language(lang_code)
            
            # Tính hash của văn bản
            text_hash = self._compute_text_hash(text)
            
            # Kiểm tra cache
            if self.cache_service:
                cached_audio = self.cache_service.get_tts_audio(text_hash, model_name)
                if cached_audio is not None:
                    # Lưu từ cache ra file
                    with open(output_path, 'wb') as f:
                        f.write(cached_audio)
                    return True
            
            # Tổng hợp trực tiếp vào file
            return self.tts_model.synthesize_and_save(text, output_path)
            
        except Exception as e:
            logger.error(f"Lỗi khi tổng hợp giọng nói và lưu file: {e}")
            return False
    
    def _compute_text_hash(self, text: str) -> str:
        """
        Tính hash của văn bản
        
        Args:
            text: Văn bản cần tính hash
            
        Returns:
            str: Chuỗi hash
        """
        hash_obj = hashlib.md5(text.encode('utf-8'))
        return hash_obj.hexdigest()
    
    def _audio_to_bytes(self, audio_data: np.ndarray) -> bytes:
        """
        Chuyển đổi dữ liệu âm thanh từ numpy array sang bytes
        
        Args:
            audio_data: Dữ liệu âm thanh dạng numpy array
            
        Returns:
            bytes: Dữ liệu âm thanh dạng bytes
        """
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            # Lưu vào file tạm
            sf.write(tmp_path, audio_data, self.tts_model.config['sample_rate'])
            
            # Đọc dưới dạng bytes
            with open(tmp_path, 'rb') as f:
                audio_bytes = f.read()
                
            # Xóa file tạm
            os.remove(tmp_path)
            
            return audio_bytes
            
        except Exception as e:
            logger.error(f"Lỗi khi chuyển đổi audio sang bytes: {e}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return b''
    
    def _bytes_to_audio(self, audio_bytes: bytes) -> np.ndarray:
        """
        Chuyển đổi dữ liệu âm thanh từ bytes sang numpy array
        
        Args:
            audio_bytes: Dữ liệu âm thanh dạng bytes
            
        Returns:
            np.ndarray: Dữ liệu âm thanh dạng numpy array
        """
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(audio_bytes)
        
        try:
            # Đọc từ file tạm
            audio_data, _ = sf.read(tmp_path)
            
            # Xóa file tạm
            os.remove(tmp_path)
            
            return audio_data
            
        except Exception as e:
            logger.error(f"Lỗi khi chuyển đổi bytes sang audio: {e}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return np.zeros(1000, dtype=np.float32)
    
    def _get_tts_model_for_language(self, lang_code: str) -> str:
        """
        Lấy tên mô hình TTS phù hợp với ngôn ngữ
        
        Args:
            lang_code: Mã ngôn ngữ
            
        Returns:
            str: Tên mô hình TTS
        """
        if lang_code in SUPPORTED_LANGUAGES and 'tts_model' in SUPPORTED_LANGUAGES[lang_code]:
            return SUPPORTED_LANGUAGES[lang_code]['tts_model']
        else:
            # Mặc định là tiếng Anh
            return SUPPORTED_LANGUAGES['en']['tts_model'] 
