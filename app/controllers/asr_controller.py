"""
Bộ điều khiển nhận dạng giọng nói (ASR)
"""
import logging
import os
from typing import Dict, Any, Optional, List, BinaryIO
import hashlib

from app.services.asr_service import ASRService
from app.services.cache_service import CacheService
from app.utils.audio_utils import validate_audio_format, get_audio_duration

logger = logging.getLogger(__name__)

class ASRController:
    def __init__(self, asr_service: ASRService, cache_service: CacheService):
        """
        Khởi tạo bộ điều khiển ASR
        
        Args:
            asr_service: Dịch vụ nhận dạng giọng nói
            cache_service: Dịch vụ bộ nhớ đệm
        """
        self.asr_service = asr_service
        self.cache_service = cache_service
        logger.info("Đã khởi tạo bộ điều khiển ASR")
    
    def transcribe_audio_file(self, audio_file: BinaryIO, language: str, 
                             use_cache: bool = True) -> Dict[str, Any]:
        """
        Nhận dạng văn bản từ file âm thanh
        
        Args:
            audio_file: File âm thanh cần nhận dạng
            language: Mã ngôn ngữ âm thanh
            use_cache: Sử dụng cache hay không
            
        Returns:
            Dict[str, Any]: Kết quả nhận dạng
        """
        try:
            # Kiểm tra định dạng âm thanh
            if not validate_audio_format(audio_file):
                return {
                    "error": "Định dạng file không được hỗ trợ. Vui lòng sử dụng WAV, MP3, OGG hoặc FLAC.",
                    "success": False
                }
            
            # Reset con trỏ file
            audio_file.seek(0)
            
            # Đọc dữ liệu âm thanh
            audio_data = audio_file.read()
            
            # Tạo hash cho audio để làm key cache
            audio_hash = hashlib.md5(audio_data).hexdigest()
            
            # Kiểm tra cache nếu bật
            if use_cache:
                cached_result = self.cache_service.get_asr_result(audio_hash, language)
                if cached_result:
                    logger.info(f"Sử dụng kết quả ASR từ cache cho ngôn ngữ: {language}")
                    return {
                        "text": cached_result["text"],
                        "confidence": cached_result["confidence"],
                        "duration": cached_result["duration"],
                        "cached": True,
                        "success": True
                    }
            
            # Reset con trỏ file
            audio_file.seek(0)
            
            # Lấy thông tin độ dài âm thanh
            duration = get_audio_duration(audio_file)
            
            # Reset con trỏ file
            audio_file.seek(0)
            
            # Thực hiện ASR
            result = self.asr_service.recognize_speech(audio_file, language)
            
            if not result["success"]:
                return result
            
            # Lưu vào cache nếu bật
            if use_cache:
                cache_data = {
                    "text": result["text"],
                    "confidence": result["confidence"],
                    "duration": duration
                }
                self.cache_service.store_asr_result(audio_hash, language, cache_data)
            
            # Trả về kết quả
            result["duration"] = duration
            result["cached"] = False
            
            return result
            
        except Exception as e:
            logger.error(f"Lỗi khi nhận dạng âm thanh: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
    
    def start_streaming_recognition(self, language: str, settings: Dict = None) -> Dict[str, Any]:
        """
        Bắt đầu nhận dạng giọng nói trực tuyến
        
        Args:
            language: Mã ngôn ngữ
            settings: Cài đặt bổ sung
            
        Returns:
            Dict[str, Any]: Thông tin phiên nhận dạng
        """
        try:
            session_info = self.asr_service.start_streaming_session(language, settings)
            return {
                "session_id": session_info["session_id"],
                "status": "started",
                "success": True
            }
        except Exception as e:
            logger.error(f"Lỗi khi bắt đầu nhận dạng trực tuyến: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
    
    def process_audio_chunk(self, session_id: str, audio_chunk: bytes) -> Dict[str, Any]:
        """
        Xử lý một đoạn âm thanh trong phiên nhận dạng trực tuyến
        
        Args:
            session_id: ID phiên nhận dạng
            audio_chunk: Đoạn dữ liệu âm thanh
            
        Returns:
            Dict[str, Any]: Kết quả nhận dạng tạm thời
        """
        try:
            result = self.asr_service.process_streaming_chunk(session_id, audio_chunk)
            return {
                "text": result["text"],
                "is_final": result["is_final"],
                "success": True
            }
        except Exception as e:
            logger.error(f"Lỗi khi xử lý đoạn âm thanh: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
    
    def stop_streaming_recognition(self, session_id: str) -> Dict[str, Any]:
        """
        Kết thúc phiên nhận dạng trực tuyến
        
        Args:
            session_id: ID phiên nhận dạng
            
        Returns:
            Dict[str, Any]: Kết quả nhận dạng cuối cùng
        """
        try:
            result = self.asr_service.stop_streaming_session(session_id)
            return {
                "text": result["text"],
                "confidence": result["confidence"],
                "duration": result["duration"],
                "success": True
            }
        except Exception as e:
            logger.error(f"Lỗi khi kết thúc phiên nhận dạng: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
    
    def get_supported_languages(self) -> Dict[str, Any]:
        """
        Lấy danh sách ngôn ngữ được hỗ trợ
        
        Returns:
            Dict[str, Any]: Danh sách ngôn ngữ được hỗ trợ
        """
        try:
            languages = self.asr_service.get_supported_languages()
            return {
                "languages": languages,
                "success": True
            }
        except Exception as e:
            logger.error(f"Lỗi khi lấy danh sách ngôn ngữ: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            } 
