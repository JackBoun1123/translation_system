"""
Bộ điều khiển dịch (Translation)
"""
import logging
import hashlib
from typing import Dict, Any, Optional, List

from app.services.translation_service import TranslationService
from app.services.context_service import ContextService
from app.services.cache_service import CacheService
from app.utils.text_utils import split_text, normalize_text

logger = logging.getLogger(__name__)

class TranslationController:
    def __init__(self, translation_service: TranslationService, 
                context_service: ContextService, 
                cache_service: CacheService):
        """
        Khởi tạo bộ điều khiển dịch
        
        Args:
            translation_service: Dịch vụ dịch
            context_service: Dịch vụ ngữ cảnh
            cache_service: Dịch vụ bộ nhớ đệm
        """
        self.translation_service = translation_service
        self.context_service = context_service
        self.cache_service = cache_service
        logger.info("Đã khởi tạo bộ điều khiển dịch")
    
    def translate_text(self, text: str, source_lang: str, target_lang: str,
                     context_id: Optional[str] = None, use_cache: bool = True) -> Dict[str, Any]:
        """
        Dịch văn bản
        
        Args:
            text: Văn bản cần dịch
            source_lang: Mã ngôn ngữ nguồn
            target_lang: Mã ngôn ngữ đích
            context_id: ID ngữ cảnh (nếu có)
            use_cache: Sử dụng cache hay không
            
        Returns:
            Dict[str, Any]: Kết quả dịch
        """
        try:
            # Chuẩn hóa văn bản
            normalized_text = normalize_text(text)
            
            if not normalized_text:
                return {
                    "error": "Văn bản rỗng",
                    "success": False
                }
            
            # Kiểm tra cache nếu bật
            if use_cache:
                cached_translation = self.cache_service.get_translation(
                    normalized_text, source_lang, target_lang, context_id
                )
                
            if cached_translation:
                    logger.info(f"Sử dụng bản dịch từ cache cho ngôn ngữ {source_lang} → {target_lang}")
                    return {
                        "original": text,
                        "translation": cached_translation,
                        "source_lang": source_lang,
                        "target_lang": target_lang,
                        "cached": True,
                        "success": True
                    }
            
            # Lấy ngữ cảnh liên quan nếu có context_id
            context_text = ""
            domain_vocabulary = {}
            
            if context_id:
                try:
                    # Lấy ngữ cảnh liên quan
                    context_text = self.context_service.get_context_for_text(
                        normalized_text, context_id, num_results=3
                    )
                    
                    # Lấy từ điển chuyên ngành
                    domain_vocabulary = self.context_service.get_domain_vocabulary(
                        context_id, source_lang, target_lang
                    )
                    
                    logger.info(f"Đã lấy ngữ cảnh và từ điển chuyên ngành cho ID: {context_id}")
                except Exception as context_error:
                    logger.warning(f"Không thể lấy ngữ cảnh: {context_error}")
            
            # Thực hiện dịch với ngữ cảnh và từ điển chuyên ngành
            translation_result = self.translation_service.translate(
                normalized_text, 
                source_lang,
                target_lang,
                context_text,
                domain_vocabulary
            )
            
            if not translation_result["success"]:
                return translation_result
            
            # Lưu vào cache nếu bật
            if use_cache:
                self.cache_service.store_translation(
                    normalized_text,
                    translation_result["translation"],
                    source_lang,
                    target_lang,
                    context_id
                )
            
            # Trả về kết quả
            return {
                "original": text,
                "translation": translation_result["translation"],
                "source_lang": source_lang,
                "target_lang": target_lang,
                "cached": False,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Lỗi khi dịch văn bản: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
    
    def translate_document(self, file_path: str, source_lang: str, target_lang: str,
                         context_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Dịch tài liệu
        
        Args:
            file_path: Đường dẫn đến tài liệu cần dịch
            source_lang: Mã ngôn ngữ nguồn
            target_lang: Mã ngôn ngữ đích
            context_id: ID ngữ cảnh (nếu có)
            
        Returns:
            Dict[str, Any]: Kết quả dịch
        """
        try:
            # Gọi dịch vụ dịch tài liệu
            document_result = self.translation_service.translate_document(
                file_path, source_lang, target_lang, context_id
            )
            
            if not document_result["success"]:
                return document_result
            
            return {
                "original_file": file_path,
                "translated_file": document_result["output_file"],
                "source_lang": source_lang,
                "target_lang": target_lang,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Lỗi khi dịch tài liệu: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
    
    def translate_batch(self, texts: List[str], source_lang: str, target_lang: str,
                      context_id: Optional[str] = None, use_cache: bool = True) -> Dict[str, Any]:
        """
        Dịch hàng loạt các văn bản
        
        Args:
            texts: Danh sách văn bản cần dịch
            source_lang: Mã ngôn ngữ nguồn
            target_lang: Mã ngôn ngữ đích
            context_id: ID ngữ cảnh (nếu có)
            use_cache: Sử dụng cache hay không
            
        Returns:
            Dict[str, Any]: Kết quả dịch hàng loạt
        """
        try:
            results = []
            
            for text in texts:
                # Dịch từng văn bản
                result = self.translate_text(
                    text, source_lang, target_lang, context_id, use_cache
                )
                
                results.append(result)
            
            # Tính tỷ lệ thành công
            success_count = sum(1 for r in results if r["success"])
            
            return {
                "translations": results,
                "count": len(texts),
                "success_count": success_count,
                "success_rate": success_count / len(texts) if texts else 0,
                "source_lang": source_lang,
                "target_lang": target_lang,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Lỗi khi dịch hàng loạt: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
    
    def detect_language(self, text: str) -> Dict[str, Any]:
        """
        Phát hiện ngôn ngữ của văn bản
        
        Args:
            text: Văn bản cần phát hiện ngôn ngữ
            
        Returns:
            Dict[str, Any]: Kết quả phát hiện ngôn ngữ
        """
        try:
            # Chuẩn hóa văn bản
            normalized_text = normalize_text(text)
            
            if not normalized_text:
                return {
                    "error": "Văn bản rỗng",
                    "success": False
                }
            
            # Gọi dịch vụ phát hiện ngôn ngữ
            detection_result = self.translation_service.detect_language(normalized_text)
            
            if not detection_result["success"]:
                return detection_result
            
            return {
                "language": detection_result["language"],
                "confidence": detection_result["confidence"],
                "text": text,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Lỗi khi phát hiện ngôn ngữ: {e}")
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
            languages = self.translation_service.get_supported_languages()
            
            return {
                "languages": languages,
                "count": len(languages),
                "success": True
            }
        except Exception as e:
            logger.error(f"Lỗi khi lấy danh sách ngôn ngữ: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
