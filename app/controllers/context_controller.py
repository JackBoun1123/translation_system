"""
Bộ điều khiển ngữ cảnh (Context)
"""
import logging
import os
from typing import Dict, Any, Optional, List, BinaryIO
import hashlib

from app.services.context_service import ContextService
from app.config import CONTEXT_DIR

logger = logging.getLogger(__name__)

class ContextController:
    def __init__(self, context_service: ContextService):
        """
        Khởi tạo bộ điều khiển ngữ cảnh
        
        Args:
            context_service: Dịch vụ xử lý ngữ cảnh
        """
        self.context_service = context_service
        logger.info("Đã khởi tạo bộ điều khiển ngữ cảnh")
    
    def load_context(self, file_path: str, language: str = "vi") -> Dict[str, Any]:
        """
        Tải file ngữ cảnh vào hệ thống
        
        Args:
            file_path: Đường dẫn đến file ngữ cảnh
            language: Ngôn ngữ của file ngữ cảnh
            
        Returns:
            Dict[str, Any]: Kết quả tải ngữ cảnh
        """
        try:
            # Kiểm tra file tồn tại
            if not os.path.isfile(file_path):
                # Thử tìm trong thư mục context
                context_file_path = os.path.join(CONTEXT_DIR, os.path.basename(file_path))
                if os.path.isfile(context_file_path):
                    file_path = context_file_path
                else:
                    logger.error(f"Không tìm thấy file ngữ cảnh: {file_path}")
                    return {
                        "error": f"Không tìm thấy file ngữ cảnh: {file_path}",
                        "success": False
                    }
            
            # Thêm file vào ngữ cảnh
            context_id = self.context_service.load_context_file(file_path, language)
            
            if not context_id:
                return {
                    "error": f"Không thể tải file ngữ cảnh: {file_path}",
                    "success": False
                }
            
            # Lấy thông tin ngữ cảnh
            context_info = self.context_service.get_context_info(context_id)
            
            return {
                "context_id": context_id,
                "file_path": file_path,
                "language": language,
                "info": context_info,
                "success": True
            }
                
        except Exception as e:
            logger.error(f"Lỗi khi tải file ngữ cảnh: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
    
    def get_context_for_text(self, text: str, context_id: str, 
                           num_results: int = 3) -> Dict[str, Any]:
        """
        Lấy ngữ cảnh liên quan cho văn bản
        
        Args:
            text: Văn bản cần tìm ngữ cảnh
            context_id: ID của ngữ cảnh
            num_results: Số lượng kết quả trả về
            
        Returns:
            Dict[str, Any]: Văn bản ngữ cảnh liên quan
        """
        try:
            # Lấy ngữ cảnh liên quan
            context_text = self.context_service.get_context_for_text(
                text, context_id, num_results
            )
            
            return {
                "context_text": context_text,
                "success": True
            }
        except Exception as e:
            logger.error(f"Lỗi khi lấy ngữ cảnh: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
    
    def list_contexts(self) -> Dict[str, Any]:
        """
        Liệt kê các ngữ cảnh đang hoạt động
        
        Returns:
            Dict[str, Any]: Danh sách ngữ cảnh
        """
        try:
            contexts = self.context_service.list_active_contexts()
            
            # Thêm thông tin chi tiết cho mỗi ngữ cảnh
            detailed_contexts = {}
            for context_id, context_info in contexts.items():
                detailed_info = self.context_service.get_context_info(context_id)
                detailed_contexts[context_id] = detailed_info or context_info
            
            return {
                "contexts": detailed_contexts,
                "success": True
            }
        except Exception as e:
            logger.error(f"Lỗi khi liệt kê ngữ cảnh: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
    
    def remove_context(self, context_id: str) -> Dict[str, Any]:
        """
        Xóa ngữ cảnh khỏi hệ thống
        
        Args:
            context_id: ID của ngữ cảnh
            
        Returns:
            Dict[str, Any]: Kết quả xóa
        """
        try:
            success = self.context_service.remove_context(context_id)
            
            if success:
                return {
                    "context_id": context_id,
                    "status": "removed",
                    "success": True
                }
            else:
                return {
                    "error": f"Không thể xóa ngữ cảnh: {context_id}",
                    "success": False
                }
        except Exception as e:
            logger.error(f"Lỗi khi xóa ngữ cảnh: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
    
    def get_domain_vocabulary(self, context_id: str, source_lang: str, 
                            target_lang: str) -> Dict[str, Any]:
        """
        Lấy từ điển chuyên ngành từ ngữ cảnh
        
        Args:
            context_id: ID của ngữ cảnh
            source_lang: Mã ngôn ngữ nguồn
            target_lang: Mã ngôn ngữ đích
            
        Returns:
            Dict[str, Any]: Từ điển thuật ngữ chuyên ngành
        """
        try:
            vocabulary = self.context_service.get_domain_vocabulary(
                context_id, source_lang, target_lang
            )
            
            return {
                "vocabulary": vocabulary,
                "source_lang": source_lang,
                "target_lang": target_lang,
                "count": len(vocabulary),
                "success": True
            }
        except Exception as e:
            logger.error(f"Lỗi khi lấy từ điển chuyên ngành: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            }
    
    def get_key_terms(self, context_id: str, max_terms: int = 20) -> Dict[str, Any]:
        """
        Lấy danh sách thuật ngữ quan trọng từ ngữ cảnh
        
        Args:
            context_id: ID của ngữ cảnh
            max_terms: Số lượng thuật ngữ tối đa
            
        Returns:
            Dict[str, Any]: Danh sách các thuật ngữ quan trọng
        """
        try:
            terms = self.context_service.get_key_terms(context_id, max_terms)
            
            return {
                "terms": terms,
                "count": len(terms),
                "success": True
            }
        except Exception as e:
            logger.error(f"Lỗi khi lấy thuật ngữ quan trọng: {e}")
            return {
                "error": f"Lỗi xử lý: {str(e)}",
                "success": False
            } 
