"""
Dịch vụ xử lý nhận dạng giọng nói (ASR)
"""
import logging
import hashlib
import numpy as np 
from typing import Dict, Optional, Union, List
import soundfile as sf
import tempfile
import os
from app.models.asr_model import ASRModel
from app.services.cache_service import CacheService
from app.models.context_model import ContextModel

logger = logging.getLogger(__name__)

class ASRService:
    def __init__(self, cache_service: Optional[CacheService] = None, 
                 context_model: Optional[ContextModel] = None):
        """
        Khởi tạo dịch vụ ASR
        
        Args:
            cache_service: Dịch vụ cache để tái sử dụng kết quả
            context_model: Mô hình ngữ cảnh để cải thiện kết quả nhận dạng
        """
        self.asr_model = ASRModel()
        self.cache_service = cache_service
        self.context_model = context_model
        logger.info("Đã khởi tạo dịch vụ ASR")
    
    def transcribe_audio(self, audio_data: Union[np.ndarray, str], 
                        language: str, 
                        context_id: Optional[str] = None) -> Dict:
        """
        Nhận dạng văn bản từ dữ liệu âm thanh
        
        Args:
            audio_data: Dữ liệu âm thanh hoặc đường dẫn đến file âm thanh
            language: Mã ngôn ngữ
            context_id: ID ngữ cảnh để cải thiện kết quả nhận dạng
            
        Returns:
            Dict: Kết quả nhận dạng văn bản
        """
        # Xử lý đầu vào audio
        audio_array = self._load_audio(audio_data)
        
        # Tính hash của audio để lưu cache
        audio_hash = self._compute_audio_hash(audio_array)
        
        # Kiểm tra cache trước khi nhận dạng
        if self.cache_service:
            cached_result = self.cache_service.get_asr_result(audio_hash, language)
            if cached_result:
                logger.info("Đã tìm thấy kết quả ASR trong cache")
                return cached_result
        
        # Lấy ngữ cảnh nếu có
        context_terms = []
        if self.context_model and context_id:
            context_terms = self.context_model.extract_key_terms(context_id)
            logger.info(f"Đã lấy {len(context_terms)} thuật ngữ từ ngữ cảnh")
        
        # Thực hiện nhận dạng
        if context_terms:
            result = self.asr_model.transcribe_with_context(
                audio_data=audio_array,
                context_terms=context_terms,
                language=language
            )
        else:
            result = self.asr_model.transcribe(
                audio_data=audio_array,
                language=language
            )
        
        # Lưu kết quả vào cache
        if self.cache_service:
            self.cache_service.store_asr_result(audio_hash, language, result)
            
        return result
    
    def transcribe_segments(self, audio_data: Union[np.ndarray, str], 
                           language: str,
                           context_id: Optional[str] = None,
                           sample_rate: int = 16000) -> List[Dict]:
        """
        Phân đoạn và nhận dạng từng đoạn audio
        
        Args:
            audio_data: Dữ liệu âm thanh
            language: Mã ngôn ngữ
            context_id: ID ngữ cảnh
            sample_rate: Tần số lấy mẫu
            
        Returns:
            List[Dict]: Danh sách các đoạn đã nhận dạng
        """
        # Xử lý đầu vào audio
        audio_array = self._load_audio(audio_data)
        
        # Phân đoạn audio
        segments = self.asr_model.segment_audio(audio_array, sample_rate)
        logger.info(f"Đã phân đoạn thành {len(segments)} đoạn audio")
        
        # Lấy ngữ cảnh nếu có
        context_terms = []
        if self.context_model and context_id:
            context_terms = self.context_model.extract_key_terms(context_id)
            logger.info(f"Đã lấy {len(context_terms)} thuật ngữ từ ngữ cảnh")
        
        # Kết quả
        results = []
        
        # Nhận dạng từng đoạn
        for i, segment in enumerate(segments):
            segment_audio = segment['data']
            segment_hash = self._compute_audio_hash(segment_audio)
            
            # Kiểm tra cache
            cached_result = None
            if self.cache_service:
                cached_result = self.cache_service.get_asr_result(segment_hash, language)
            
            if cached_result:
                segment_result = cached_result
            else:
                # Thực hiện nhận dạng đoạn
                if context_terms:
                    segment_result = self.asr_model.transcribe_with_context(
                        audio_data=segment_audio, 
                        context_terms=context_terms,
                        language=language
                    )
                else:
                    segment_result = self.asr_model.transcribe(
                        audio_data=segment_audio,
                        language=language
                    )
                
                # Lưu vào cache
                if self.cache_service:
                    self.cache_service.store_asr_result(segment_hash, language, segment_result)
            
            # Thêm thông tin thời gian
            segment_result['start'] = segment['start']
            segment_result['end'] = segment['end']
            results.append(segment_result)
        
        return results
    
    def _load_audio(self, audio_data: Union[np.ndarray, str]) -> np.ndarray:
        """
        Đọc dữ liệu âm thanh từ array hoặc file
        
        Args:
            audio_data: Dữ liệu âm thanh hoặc đường dẫn
            
        Returns:
            np.ndarray: Dữ liệu âm thanh dạng numpy array
        """
        if isinstance(audio_data, np.ndarray):
            return audio_data
        
        elif isinstance(audio_data, str):
            # Đọc file âm thanh
            audio_array, _ = sf.read(audio_data)
            return audio_array
        
        else:
            raise ValueError("Định dạng âm thanh không được hỗ trợ")
    
    def _compute_audio_hash(self, audio_array: np.ndarray) -> str:
        """
        Tính hash của dữ liệu âm thanh
        
        Args:
            audio_array: Dữ liệu âm thanh
            
        Returns:
            str: Chuỗi hash
        """
        # Chuyển audio thành bytes để tính hash
        audio_bytes = audio_array.tobytes()
        
        # Tính hash
        hash_obj = hashlib.md5(audio_bytes)
        return hash_obj.hexdigest() 
