"""
Dịch vụ bộ nhớ đệm (cache) để lưu trữ và tái sử dụng kết quả
"""
import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from collections import OrderedDict
from app.config import CACHE_CONFIG

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self, config: Dict = None):
        """
        Khởi tạo dịch vụ bộ nhớ đệm
        
        Args:
            config: Cấu hình cho dịch vụ bộ nhớ đệm, nếu None sẽ dùng mặc định
        """
        self.config = config or CACHE_CONFIG
        
        # Khởi tạo các bộ nhớ đệm
        self.translation_cache = OrderedDict()
        self.asr_cache = OrderedDict()
        self.tts_cache = OrderedDict()
        
        # Thống kê
        self.hits = 0
        self.misses = 0
        
        logger.info("Đã khởi tạo dịch vụ bộ nhớ đệm")
    
    def get_translation(self, text: str, source_lang: str, 
                      target_lang: str, context_id: Optional[str] = None) -> Optional[str]:
        """
        Lấy bản dịch từ bộ nhớ đệm
        
        Args:
            text: Văn bản cần dịch
            source_lang: Mã ngôn ngữ nguồn
            target_lang: Mã ngôn ngữ đích
            context_id: ID ngữ cảnh (nếu có)
            
        Returns:
            Optional[str]: Bản dịch nếu có trong cache, None nếu không
        """
        cache_key = self._make_translation_key(text, source_lang, target_lang, context_id)
        
        result = self.translation_cache.get(cache_key)
        if result:
            self.hits += 1
            # Di chuyển item lên đầu cache (LRU)
            self.translation_cache.move_to_end(cache_key)
            logger.debug(f"Tìm thấy bản dịch trong cache: {text[:30]}...")
            return result
        else:
            self.misses += 1
            logger.debug(f"Không tìm thấy bản dịch trong cache: {text[:30]}...")
            return None
    
    def store_translation(self, text: str, translation: str, source_lang: str,
                        target_lang: str, context_id: Optional[str] = None) -> None:
        """
        Lưu bản dịch vào bộ nhớ đệm
        
        Args:
            text: Văn bản gốc
            translation: Bản dịch
            source_lang: Mã ngôn ngữ nguồn
            target_lang: Mã ngôn ngữ đích
            context_id: ID ngữ cảnh (nếu có)
        """
        cache_key = self._make_translation_key(text, source_lang, target_lang, context_id)
        
        # Thêm vào cache
        self.translation_cache[cache_key] = translation
        
        # Di chuyển item mới thêm lên đầu (LRU)
        self.translation_cache.move_to_end(cache_key)
        
        # Kiểm tra và cắt bớt cache nếu cần
        if len(self.translation_cache) > self.config['translation_cache_size']:
            self.translation_cache.popitem(last=False)  # Xóa item ít sử dụng nhất
            
        logger.debug(f"Đã lưu bản dịch vào cache: {text[:30]}...")
    
    def get_asr_result(self, audio_hash: str, language: str) -> Optional[Dict]:
        """
        Lấy kết quả nhận dạng giọng nói từ cache
        
        Args:
            audio_hash: Hash của dữ liệu âm thanh
            language: Mã ngôn ngữ
            
        Returns:
            Optional[Dict]: Kết quả nhận dạng nếu có trong cache, None nếu không
        """
        cache_key = f"asr:{audio_hash}:{language}"
        
        result = self.asr_cache.get(cache_key)
        if result:
            self.hits += 1
            # Di chuyển item lên đầu cache (LRU)
            self.asr_cache.move_to_end(cache_key)
            logger.debug(f"Tìm thấy kết quả ASR trong cache: {audio_hash}")
            return result
        else:
            self.misses += 1
            logger.debug(f"Không tìm thấy kết quả ASR trong cache: {audio_hash}")
            return None
    
    def store_asr_result(self, audio_hash: str, language: str, result: Dict) -> None:
        """
        Lưu kết quả nhận dạng giọng nói vào cache
        
        Args:
            audio_hash: Hash của dữ liệu âm thanh
            language: Mã ngôn ngữ
            result: Kết quả nhận dạng
        """
        cache_key = f"asr:{audio_hash}:{language}"
        
        # Thêm vào cache
        self.asr_cache[cache_key] = result
        
        # Di chuyển item mới thêm lên đầu (LRU)
        self.asr_cache.move_to_end(cache_key)
        
        # Kiểm tra và cắt bớt cache nếu cần
        if len(self.asr_cache) > self.config['asr_cache_size']:
            self.asr_cache.popitem(last=False)  # Xóa item ít sử dụng nhất
            
        logger.debug(f"Đã lưu kết quả ASR vào cache: {audio_hash}")
    
    def get_tts_audio(self, text_hash: str, voice: str) -> Optional[bytes]:
        """
        Lấy dữ liệu âm thanh TTS từ cache
        
        Args:
            text_hash: Hash của văn bản
            voice: Mã giọng nói
            
        Returns:
            Optional[bytes]: Dữ liệu âm thanh nếu có trong cache, None nếu không
        """
        cache_key = f"tts:{text_hash}:{voice}"
        
        result = self.tts_cache.get(cache_key)
        if result:
            self.hits += 1
            # Di chuyển item lên đầu cache (LRU)
            self.tts_cache.move_to_end(cache_key)
            logger.debug(f"Tìm thấy audio TTS trong cache: {text_hash}")
            return result
        else:
            self.misses += 1
            logger.debug(f"Không tìm thấy audio TTS trong cache: {text_hash}")
            return None
    
    def store_tts_audio(self, text_hash: str, voice: str, audio_data: bytes) -> None:
        """
        Lưu dữ liệu âm thanh TTS vào cache
        
        Args:
            text_hash: Hash của văn bản
            voice: Mã giọng nói
            audio_data: Dữ liệu âm thanh
        """
        cache_key = f"tts:{text_hash}:{voice}"
        
        # Thêm vào cache
        self.tts_cache[cache_key] = audio_data
        
        # Di chuyển item mới thêm lên đầu (LRU)
        self.tts_cache.move_to_end(cache_key)
        
        # Kiểm tra và cắt bớt cache nếu cần
        if len(self.tts_cache) > self.config['tts_cache_size']:
            self.tts_cache.popitem(last=False)  # Xóa item ít sử dụng nhất
            
        logger.debug(f"Đã lưu audio TTS vào cache: {text_hash}")
    
    def clear_cache(self, cache_type: Optional[str] = None) -> None:
        """
        Xóa dữ liệu trong cache
        
        Args:
            cache_type: Loại cache cần xóa ('translation', 'asr', 'tts', hoặc None để xóa tất cả)
        """
        if cache_type is None or cache_type == 'translation':
            self.translation_cache.clear()
            logger.info("Đã xóa cache dịch")
            
        if cache_type is None or cache_type == 'asr':
            self.asr_cache.clear()
            logger.info("Đã xóa cache ASR")
            
        if cache_type is None or cache_type == 'tts':
            self.tts_cache.clear()
            logger.info("Đã xóa cache TTS")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Lấy thống kê về cache
        
        Returns:
            Dict[str, Any]: Thông tin thống kê về cache
        """
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_ratio': self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0,
            'translation_cache_size': len(self.translation_cache),
            'asr_cache_size': len(self.asr_cache),
            'tts_cache_size': len(self.tts_cache),
            'translation_cache_limit': self.config['translation_cache_size'],
            'asr_cache_limit': self.config['asr_cache_size'],
            'tts_cache_limit': self.config['tts_cache_size']
        }
    
    def _make_translation_key(self, text: str, source_lang: str, 
                            target_lang: str, context_id: Optional[str] = None) -> str:
        """
        Tạo khóa cache cho bản dịch
        
        Args:
            text: Văn bản cần dịch
            source_lang: Mã ngôn ngữ nguồn
            target_lang: Mã ngôn ngữ đích
            context_id: ID ngữ cảnh (nếu có)
            
        Returns:
            str: Khóa cache
        """
        context_part = f":{context_id}" if context_id else ""
        return f"translate:{source_lang}:{target_lang}{context_part}:{text}"