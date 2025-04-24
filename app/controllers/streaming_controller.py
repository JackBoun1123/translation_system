"""
Bộ điều khiển luồng truyền (Streaming)
"""
import logging
import uuid
from typing import Dict, Any, Optional, List, Callable, BinaryIO
import asyncio
import json

from app.controllers.asr_controller import ASRController
from app.controllers.translation_controller import TranslationController
from app.controllers.tts_controller import TTSController

logger = logging.getLogger(__name__)

class StreamingController:
    def __init__(self, asr_controller: ASRController, 
                translation_controller: TranslationController,
                tts_controller: TTSController):
        """
        Khởi tạo bộ điều khiển luồng truyền
        
        Args:
            asr_controller: Bộ điều khiển ASR
            translation_controller: Bộ điều khiển dịch
            tts_controller: Bộ điều khiển TTS
        """
        self.asr_controller = asr_controller
        self.translation_controller = translation_controller
        self.tts_controller = tts_controller
        
        # Lưu trữ các phiên hoạt động
        self.active_sessions = {}
        
        logger.info("Đã khởi tạo bộ điều khiển luồng truyền")
    
    async def start_streaming_session(self, source_lang: str, target_lang: str, 
                                    settings: Dict = None) -> Dict[str, Any]:
        """
        Bắt đầu phiên luồng truyền
        
        Args:
            source_lang: Mã ngôn ngữ nguồn
            target_lang: Mã ngôn ngữ đích
            settings: Cài đặt bổ sung
            
        Returns:
            Dict[str, Any]: Thông tin phiên
        """
        try:
            # Khởi tạo cài đặt mặc định nếu không có
            if settings is None:
                settings = {}
            
            # Cài đặt phiên ASR
            asr_settings = settings.get('asr', {})
            asr_result = self.asr_controller.start_streaming_recognition(source_lang, asr_settings)
            
            if not asr_result["success"]:
                return {
                    "error": f"Không thể khởi tạo phiên ASR: {asr_result.get('error', 'Unknown error')}",
                    "success": False
                }
            
            # Tạo ID phiên
            session_id = str(uuid.uuid4())
            
            # Lưu thông tin phiên
            self.active_sessions[session_id] = {
                "asr_session_id": asr_result["session_id"],
                "source_lang": source_lang,
                "target_lang": target_lang,
                "settings": settings,
                "last_asr_text": "",
                "last_translation": "",
                "last_tts_audio": None,
                "is_active": True
            }
            
            return {
                "session_id": session_id,
                "status": "started",
                "source_lang": source_lang,
                "target_lang": target_lang,
                "success": True
            }
        except Exception as e:
            logger.error(f"Lỗi khi bắt đầu phiên luồng truyền: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
    
    async def process_audio_chunk(self, session_id: str, audio_chunk: bytes, 
                                callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Xử lý một đoạn âm thanh trong phiên luồng truyền
        
        Args:
            session_id: ID phiên
            audio_chunk: Đoạn dữ liệu âm thanh
            callback: Hàm callback để trả về kết quả từng bước
            
        Returns:
            Dict[str, Any]: Kết quả xử lý
        """
        try:
            # Kiểm tra phiên tồn tại
            if session_id not in self.active_sessions:
                return {
                    "error": f"Phiên không tồn tại: {session_id}",
                    "success": False
                }
            
            session = self.active_sessions[session_id]
            
            # Kiểm tra phiên còn hoạt động
            if not session["is_active"]:
                return {
                    "error": f"Phiên đã kết thúc: {session_id}",
                    "success": False
                }
            
            # Xử lý ASR
            asr_result = self.asr_controller.process_audio_chunk(
                session["asr_session_id"], audio_chunk
            )
            
            if not asr_result["success"]:
                return {
                    "error": f"Lỗi ASR: {asr_result.get('error', 'Unknown error')}",
                    "success": False
                }
            
            # Cập nhật văn bản ASR
            session["last_asr_text"] = asr_result["text"]
            
            # Gọi callback với kết quả ASR nếu có
            if callback:
                await callback({
                    "type": "asr",
                    "text": asr_result["text"],
                    "is_final": asr_result["is_final"],
                    "success": True
                })
            
            # Nếu kết quả là cuối cùng, thực hiện dịch và TTS
            if asr_result["is_final"] and asr_result["text"].strip():
                # Dịch văn bản
                context_id = session["settings"].get("context_id")
                translation_result = self.translation_controller.translate_text(
                    asr_result["text"],
                    session["source_lang"],
                    session["target_lang"],
                    context_id
                )
                
                if not translation_result["success"]:
                    if callback:
                        await callback({
                            "type": "translation",
                            "error": translation_result.get("error", "Unknown error"),
                            "success": False
                        })
                    return translation_result
                
                # Cập nhật bản dịch
                session["last_translation"] = translation_result["translation"]
                
                # Gọi callback với kết quả dịch nếu có
                if callback:
                    await callback({
                        "type": "translation",
                        "text": translation_result["translation"],
                        "success": True
                    })
                
                # Thực hiện TTS nếu có yêu cầu
                if session["settings"].get("tts_enabled", True):
                    voice = session["settings"].get("voice", "default")
                    tts_result = self.tts_controller.synthesize_speech(
                        translation_result["translation"],
                        session["target_lang"],
                        voice
                    )
                    
                    if not tts_result["success"]:
                        if callback:
                            await callback({
                                "type": "tts",
                                "error": tts_result.get("error", "Unknown error"),
                                "success": False
                            })
                    else:
                        # Cập nhật audio TTS
                        session["last_tts_audio"] = tts_result["audio_data"]
                        
                        # Gọi callback với kết quả TTS nếu có
                        if callback:
                            await callback({
                                "type": "tts",
                                "audio": tts_result["audio_data"],
                                "success": True
                            })
            
            return {
                "text": asr_result["text"],
                "is_final": asr_result["is_final"],
                "translation": session.get("last_translation", ""),
                "has_audio": session["last_tts_audio"] is not None,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Lỗi khi xử lý đoạn âm thanh trong phiên luồng truyền: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
    
    async def stop_streaming_session(self, session_id: str) -> Dict[str, Any]:
        """
        Kết thúc phiên luồng truyền
        
        Args:
            session_id: ID phiên
            
        Returns:
            Dict[str, Any]: Kết quả cuối cùng
        """
        try:
            # Kiểm tra phiên tồn tại
            if session_id not in self.active_sessions:
                return {
                    "error": f"Phiên không tồn tại: {session_id}",
                    "success": False
                }
            
            session = self.active_sessions[session_id]
            
            # Kiểm tra phiên còn hoạt động
            if not session["is_active"]:
                return {
                    "error": f"Phiên đã kết thúc: {session_id}",
                    "success": False
                }
            
            # Kết thúc phiên ASR
            asr_result = self.asr_controller.stop_streaming_recognition(
                session["asr_session_id"]
            )
            
            # Đánh dấu phiên đã kết thúc
            session["is_active"] = False
            
            return {
                "asr_text": asr_result["text"] if asr_result["success"] else session["last_asr_text"],
                "translation": session["last_translation"],
                "has_audio": session["last_tts_audio"] is not None,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Lỗi khi kết thúc phiên luồng truyền: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
    
    def get_streaming_session_info(self, session_id: str) -> Dict[str, Any]:
        """
        Lấy thông tin phiên luồng truyền
        
        Args:
            session_id: ID phiên
            
        Returns:
            Dict[str, Any]: Thông tin phiên
        """
        try:
            # Kiểm tra phiên tồn tại
            if session_id not in self.active_sessions:
                return {
                    "error": f"Phiên không tồn tại: {session_id}",
                    "success": False
                }
            
            session = self.active_sessions[session_id]
            
            return {
                "session_id": session_id,
                "source_lang": session["source_lang"],
                "target_lang": session["target_lang"],
                "is_active": session["is_active"],
                "settings": session["settings"],
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Lỗi khi lấy thông tin phiên luồng truyền: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            } 
