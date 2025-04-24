"""
Bộ điều khiển tổng hợp giọng nói (TTS)
"""
import logging
import os
import hashlib
from typing import Dict, Any, Optional, List, BinaryIO

from app.services.tts_service import TTSService
from app.services.cache_service import CacheService
from app.utils.text_utils import normalize_text
from app.utils.audio_utils import save_audio_file

logger = logging.getLogger(__name__)

class TTSController:
    def __init__(self, tts_service: TTSService, cache_service: CacheService):
        """
        Khởi tạo bộ điều khiển TTS
        
        Args:
            tts_service: Dịch vụ tổng hợp giọng nói
            cache_service: Dịch vụ bộ nhớ đệm
        """
        self.tts_service = tts_service
        self.cache_service = cache_service
        logger.info("Đã khởi tạo bộ điều khiển TTS")
    
    def synthesize_speech(self, text: str, language: str, voice: str = "default",
                        use_cache: bool = True) -> Dict[str, Any]:
        """
        Tổng hợp giọng nói từ văn bản
        
        Args:
            text: Văn bản cần chuyển thành giọng nói
            language: Mã ngôn ngữ
            voice: Mã giọng nói
            use_cache: Sử dụng cache hay không
            
        Returns:
            Dict[str, Any]: Kết quả tổng hợp giọng nói
        """
        try:
            # Chuẩn hóa văn bản
            normalized_text = normalize_text(text)
            
            if not normalized_text:
                return {
                    "error": "Văn bản rỗng",
                    "success": False
                }
            
            # Tạo hash cho văn bản để làm key cache
            text_hash = hashlib.md5(normalized_text.encode('utf-8')).hexdigest()
            
            # Kiểm tra cache nếu bật
            if use_cache:
                cached_audio = self.cache_service.get_tts_audio(text_hash, voice)
                if cached_audio:
                    logger.info(f"Sử dụng audio TTS từ cache cho ngôn ngữ: {language}, giọng: {voice}")
                    return {
                        "audio_data": cached_audio,
                        "text": text,
                        "language": language,
                        "voice": voice,
                        "cached": True,
                        "success": True
                    }
            
            # Thực hiện tổng hợp giọng nói
            tts_result = self.tts_service.synthesize(normalized_text, language, voice)
            
            if not tts_result["success"]:
                return tts_result
            
            # Lưu vào cache nếu bật
            if use_cache:
                self.cache_service.store_tts_audio(text_hash, voice, tts_result["audio_data"])
            
            # Trả về kết quả
            return {
                "audio_data": tts_result["audio_data"],
                "text": text,
                "language": language,
                "voice": voice,
                "audio_format": tts_result.get("audio_format", "wav"),
                "cached": False,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Lỗi khi tổng hợp giọng nói: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
    
    def save_speech_to_file(self, text: str, output_path: str, language: str,
                          voice: str = "default", file_format: str = "wav",
                          use_cache: bool = True) -> Dict[str, Any]:
        """
        Tổng hợp giọng nói và lưu vào file
        
        Args:
            text: Văn bản cần chuyển thành giọng nói
            output_path: Đường dẫn lưu file
            language: Mã ngôn ngữ
            voice: Mã giọng nói
            file_format: Định dạng file âm thanh
            use_cache: Sử dụng cache hay không
            
        Returns:
            Dict[str, Any]: Kết quả tạo file âm thanh
        """
        try:
            # Tổng hợp giọng nói
            tts_result = self.synthesize_speech(text, language, voice, use_cache)
            
            if not tts_result["success"]:
                return tts_result
            
            # Đảm bảo thư mục tồn tại
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            # Lưu vào file
            save_audio_file(tts_result["audio_data"], output_path, file_format)
            
            return {
                "file_path": output_path,
                "text": text,
                "language": language,
                "voice": voice,
                "file_format": file_format,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Lỗi khi lưu giọng nói vào file: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
    
    def get_available_voices(self, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Lấy danh sách giọng nói có sẵn
        
        Args:
            language: Mã ngôn ngữ (nếu None sẽ lấy tất cả)
            
        Returns:
            Dict[str, Any]: Danh sách giọng nói có sẵn
        """
        try:
            voices = self.tts_service.get_available_voices(language)
            
            return {
                "voices": voices,
                "language": language,
                "count": len(voices),
                "success": True
            }
        except Exception as e:
            logger.error(f"Lỗi khi lấy danh sách giọng nói: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
    
    def batch_synthesize(self, texts: List[str], language: str, voice: str = "default",
                        use_cache: bool = True) -> Dict[str, Any]:
        """
        Tổng hợp giọng nói hàng loạt
        
        Args:
            texts: Danh sách văn bản
            language: Mã ngôn ngữ
            voice: Mã giọng nói
            use_cache: Sử dụng cache hay không
            
        Returns:
            Dict[str, Any]: Kết quả tổng hợp giọng nói hàng loạt
        """
        try:
            results = []
            
            for text in texts:
                # Tổng hợp giọng nói cho từng văn bản
                result = self.synthesize_speech(text, language, voice, use_cache)
                results.append(result)
            
            # Tính tỷ lệ thành công
            success_count = sum(1 for r in results if r["success"])
            
            return {
                "audio_results": results,
                "count": len(texts),
                "success_count": success_count,
                "success_rate": success_count / len(texts) if texts else 0,
                "language": language,
                "voice": voice,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Lỗi khi tổng hợp giọng nói hàng loạt: {e}")
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
            languages = self.tts_service.get_supported_languages()
            
            return {
                "languages": languages,
                "count": len(languages),
                "success": True
            }
        except Exception as e:
            logger.error(f"Lỗi khi lấy danh sách ngôn ngữ hỗ trợ TTS: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            } 
