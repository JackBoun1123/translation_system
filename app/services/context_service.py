"""
Dịch vụ xử lý ngữ cảnh
"""
import logging
import os
from typing import Dict, Optional, List, Tuple, Set
from app.models.context_model import ContextModel
from app.config import CONTEXT_DIR

logger = logging.getLogger(__name__)

class ContextService:
    def __init__(self):
        """Khởi tạo dịch vụ ngữ cảnh"""
        self.context_model = ContextModel()
        self.active_contexts = {}  # {context_id: {file_path, language}}
        logger.info("Đã khởi tạo dịch vụ ngữ cảnh")
    
    def load_context_file(self, file_path: str, language: str = "vi") -> Optional[str]:
        """
        Tải file ngữ cảnh vào hệ thống
        
        Args:
            file_path: Đường dẫn đến file ngữ cảnh
            language: Ngôn ngữ của file ngữ cảnh
            
        Returns:
            Optional[str]: ID của ngữ cảnh đã tải, None nếu thất bại
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
                    return None
            
            # Thêm file vào model ngữ cảnh
            context_id = self.context_model.add_context_file(file_path, language)
            
            if context_id:
                # Lưu thông tin ngữ cảnh đang hoạt động
                self.active_contexts[context_id] = {
                    'file_path': file_path,
                    'language': language
                }
                logger.info(f"Đã tải file ngữ cảnh: {file_path} với ID: {context_id}")
                return context_id
            else:
                logger.error(f"Không thể tải file ngữ cảnh: {file_path}")
                return None
                
        except Exception as e:
            logger.error(f"Lỗi khi tải file ngữ cảnh: {e}")
            return None
    
    def get_context_for_text(self, text: str, context_id: str, 
                           num_results: int = 3) -> str:
        """
        Lấy ngữ cảnh liên quan cho văn bản
        
        Args:
            text: Văn bản cần tìm ngữ cảnh
            context_id: ID của ngữ cảnh
            num_results: Số lượng kết quả trả về
            
        Returns:
            str: Văn bản ngữ cảnh liên quan
        """
        # Kiểm tra context_id có tồn tại không
        if context_id not in self.active_contexts:
            logger.warning(f"Không tìm thấy ngữ cảnh với ID: {context_id}")
            return ""
        
        # Lấy ngữ cảnh liên quan
        return self.context_model.get_relevant_context(text, context_id, num_results)
    
    def get_key_terms(self, context_id: str, max_terms: int = 20) -> List[str]:
        """
        Lấy danh sách thuật ngữ quan trọng từ ngữ cảnh
        
        Args:
            context_id: ID của ngữ cảnh
            max_terms: Số lượng thuật ngữ tối đa
            
        Returns:
            List[str]: Danh sách các thuật ngữ quan trọng
        """
        # Kiểm tra context_id có tồn tại không
        if context_id not in self.active_contexts:
            logger.warning(f"Không tìm thấy ngữ cảnh với ID: {context_id}")
            return []
        
        return self.context_model.extract_key_terms(context_id, max_terms)
    
    def get_domain_vocabulary(self, context_id: str, source_lang: str, 
                             target_lang: str) -> Dict[str, str]:
        """
        Lấy từ điển chuyên ngành từ ngữ cảnh
        
        Args:
            context_id: ID của ngữ cảnh
            source_lang: Mã ngôn ngữ nguồn
            target_lang: Mã ngôn ngữ đích
            
        Returns:
            Dict[str, str]: Từ điển thuật ngữ chuyên ngành {nguồn: đích}
        """
        # Kiểm tra context_id có tồn tại không
        if context_id not in self.active_contexts:
            logger.warning(f"Không tìm thấy ngữ cảnh với ID: {context_id}")
            return {}
        
        return self.context_model.get_domain_vocabulary(context_id, source_lang, target_lang)
    
    def list_active_contexts(self) -> Dict[str, Dict]:
        """
        Liệt kê các ngữ cảnh đang hoạt động
        
        Returns:
            Dict[str, Dict]: Thông tin các ngữ cảnh đang hoạt động {context_id: {file_path, language}}
        """
        return self.active_contexts
    
    def remove_context(self, context_id: str) -> bool:
        """
        Xóa ngữ cảnh khỏi danh sách hoạt động
        
        Args:
            context_id: ID của ngữ cảnh
            
        Returns:
            bool: True nếu xóa thành công, False nếu không
        """
        if context_id in self.active_contexts:
            # Xóa khỏi model
            success = self.context_model.remove_context(context_id)
            
            if success:
                # Xóa khỏi danh sách hoạt động
                del self.active_contexts[context_id]
                logger.info(f"Đã xóa ngữ cảnh: {context_id}")
                return True
            else:
                logger.error(f"Không thể xóa ngữ cảnh từ model: {context_id}")
                return False
        else:
            logger.warning(f"Không tìm thấy ngữ cảnh để xóa với ID: {context_id}")
            return False
    
    def update_context_status(self, context_id: str, active: bool = True) -> bool:
        """
        Cập nhật trạng thái hoạt động của ngữ cảnh
        
        Args:
            context_id: ID của ngữ cảnh
            active: True để kích hoạt, False để vô hiệu hóa
            
        Returns:
            bool: True nếu cập nhật thành công, False nếu không
        """
        if context_id in self.active_contexts:
            if not active:
                # Chỉ cần đánh dấu là không hoạt động, không xóa khỏi hệ thống
                self.active_contexts[context_id]['active'] = False
                logger.info(f"Đã vô hiệu hóa ngữ cảnh: {context_id}")
            else:
                # Kích hoạt lại ngữ cảnh
                self.active_contexts[context_id]['active'] = True
                logger.info(f"Đã kích hoạt ngữ cảnh: {context_id}")
            return True
        else:
            logger.warning(f"Không tìm thấy ngữ cảnh để cập nhật trạng thái: {context_id}")
            return False
    
    def get_context_info(self, context_id: str) -> Optional[Dict]:
        """
        Lấy thông tin về ngữ cảnh
        
        Args:
            context_id: ID của ngữ cảnh
            
        Returns:
            Optional[Dict]: Thông tin về ngữ cảnh hoặc None nếu không tìm thấy
        """
        if context_id in self.active_contexts:
            # Lấy thông tin cơ bản
            context_info = self.active_contexts[context_id].copy()
            
            # Thêm các thông tin chi tiết từ model
            stats = self.context_model.get_context_stats(context_id)
            if stats:
                context_info.update(stats)
                
            return context_info
        else:
            logger.warning(f"Không tìm thấy ngữ cảnh: {context_id}")
            return None
    
    def find_similar_documents(self, text: str, context_id: str, 
                              max_results: int = 5) -> List[Dict]:
        """
        Tìm các tài liệu tương tự dựa trên văn bản đầu vào
        
        Args:
            text: Văn bản tìm kiếm
            context_id: ID của ngữ cảnh
            max_results: Số lượng kết quả tối đa
            
        Returns:
            List[Dict]: Danh sách các tài liệu tương tự
        """
        # Kiểm tra context_id có tồn tại không
        if context_id not in self.active_contexts:
            logger.warning(f"Không tìm thấy ngữ cảnh với ID: {context_id}")
            return []
        
        return self.context_model.find_similar_documents(text, context_id, max_results)
    
    def extract_terminology(self, context_id: str, source_lang: str, 
                           target_lang: str) -> Dict[str, str]:
        """
        Trích xuất thuật ngữ từ ngữ cảnh cho cặp ngôn ngữ
        
        Args:
            context_id: ID của ngữ cảnh
            source_lang: Mã ngôn ngữ nguồn
            target_lang: Mã ngôn ngữ đích
            
        Returns:
            Dict[str, str]: Từ điển thuật ngữ {nguồn: đích}
        """
        # Kiểm tra context_id có tồn tại không
        if context_id not in self.active_contexts:
            logger.warning(f"Không tìm thấy ngữ cảnh với ID: {context_id}")
            return {}
        
        return self.context_model.extract_terminology(context_id, source_lang, target_lang)