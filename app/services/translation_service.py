"""
Dịch vụ xử lý dịch thuật
"""
import logging
import hashlib
from typing import Dict, Optional, List, Union
from app.models.translation_model import TranslationModel
from app.services.cache_service import CacheService
from app.models.context_model import ContextModel

logger = logging.getLogger(__name__)

class TranslationService:
    def __init__(self, cache_service: Optional[CacheService] = None,
                 context_model: Optional[ContextModel] = None):
        """
        Khởi tạo dịch vụ dịch thuật
        
        Args:
            cache_service: Dịch vụ cache để tái sử dụng kết quả dịch
            context_model: Mô hình ngữ cảnh để cải thiện chất lượng dịch
        """
        self.translation_model = TranslationModel()
        self.cache_service = cache_service
        self.context_model = context_model
        logger.info("Đã khởi tạo dịch vụ dịch thuật")
    
    def translate(self, text: str, source_lang: str, target_lang: str,
                 context_id: Optional[str] = None) -> str:
        """
        Dịch văn bản từ ngôn ngữ nguồn sang ngôn ngữ đích
        
        Args:
            text: Văn bản cần dịch
            source_lang: Mã ngôn ngữ nguồn 
            target_lang: Mã ngôn ngữ đích
            context_id: ID ngữ cảnh để cải thiện chất lượng dịch
            
        Returns:
            str: Văn bản đã dịch
        """
        # Kiểm tra cache trước khi dịch
        if self.cache_service:
            cached_translation = self.cache_service.get_translation(
                text, source_lang, target_lang, context_id
            )
            if cached_translation:
                logger.info("Đã tìm thấy bản dịch trong cache")
                return cached_translation
        
        # Xử lý ngữ cảnh
        context_text = None
        domain_terms = {}
        
        if self.context_model and context_id:
            # Lấy ngữ cảnh liên quan đến text
            context_text = self.context_model.get_relevant_context(text, context_id)
            
            # Lấy từ điển chuyên ngành
            domain_terms = self.context_model.get_domain_vocabulary(
                context_id, source_lang, target_lang
            )
            
            logger.info(f"Đã lấy ngữ cảnh với {len(domain_terms)} thuật ngữ chuyên ngành")
        
        # Thực hiện dịch thuật
        if domain_terms:
            # Dịch với từ điển chuyên ngành
            translated_text = self.translation_model.translate_with_domain_vocabulary(
                text=text,
                domain_terms=domain_terms,
                source_lang=source_lang,
                target_lang=target_lang
            )
        else:
            # Dịch thông thường
            translated_text = self.translation_model.translate(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang,
                context=context_text
            )
        
        # Lưu kết quả vào cache
        if self.cache_service:
            self.cache_service.store_translation(
                text, translated_text, source_lang, target_lang, context_id
            )
        
        return translated_text
    
    def batch_translate(self, texts: List[str], source_lang: str, target_lang: str,
                       context_id: Optional[str] = None) -> List[str]:
        """
        Dịch một loạt văn bản cùng một lúc
        
        Args:
            texts: Danh sách các văn bản cần dịch
            source_lang: Mã ngôn ngữ nguồn
            target_lang: Mã ngôn ngữ đích
            context_id: ID ngữ cảnh
            
        Returns:
            List[str]: Danh sách các văn bản đã dịch
        """
        results = []
        cached_count = 0
        to_translate = []
        to_translate_indices = []
        
        # Kiểm tra cache trước
        if self.cache_service:
            for i, text in enumerate(texts):
                cached = self.cache_service.get_translation(
                    text, source_lang, target_lang, context_id
                )
                if cached:
                    results.append(cached)
                    cached_count += 1
                else:
                    to_translate.append(text)
                    to_translate_indices.append(i)
            
            logger.info(f"Đã tìm thấy {cached_count}/{len(texts)} bản dịch trong cache")
        else:
            to_translate = texts
            to_translate_indices = list(range(len(texts)))
        
        # Nếu tất cả đã có trong cache
        if not to_translate:
            return results
        
        # Lấy ngữ cảnh nếu có
        domain_terms = {}
        if self.context_model and context_id:
            domain_terms = self.context_model.get_domain_vocabulary(
                context_id, source_lang, target_lang
            )
        
        # Dịch các văn bản chưa có trong cache
        if domain_terms:
            # Dịch từng văn bản với từ điển chuyên ngành
            translated = []
            for text in to_translate:
                trans = self.translation_model.translate_with_domain_vocabulary(
                    text=text,
                    domain_terms=domain_terms,
                    source_lang=source_lang,
                    target_lang=target_lang
                )
                translated.append(trans)
        else:
            # Dịch hàng loạt thông thường
            translated = self.translation_model.batch_translate(
                texts=to_translate,
                source_lang=source_lang,
                target_lang=target_lang
            )
        
        # Lưu vào cache và kết quả
        final_results = [None] * len(texts)
        for i, idx in enumerate(to_translate_indices):
            trans = translated[i]
            if self.cache_service:
                self.cache_service.store_translation(
                    to_translate[i], trans, source_lang, target_lang, context_id
                )
            final_results[idx] = trans
        
        # Điền kết quả đã cache
        for i in range(len(texts)):
            if i not in to_translate_indices:
                final_results[i] = results[to_translate_indices.index(i) if to_translate_indices else 0]
        
        return final_results
    
    def translate_segments(self, segments: List[Dict], source_lang: str, target_lang: str,
                         context_id: Optional[str] = None) -> List[Dict]:
        """
        Dịch các đoạn văn bản từ kết quả nhận dạng giọng nói
        
        Args:
            segments: Danh sách các đoạn từ ASR
            source_lang: Mã ngôn ngữ nguồn
            target_lang: Mã ngôn ngữ đích
            context_id: ID ngữ cảnh
            
        Returns:
            List[Dict]: Danh sách các đoạn đã dịch
        """
        # Trích xuất văn bản từ các đoạn
        texts = [segment['text'] for segment in segments]
        
        # Dịch các văn bản
        translated_texts = self.batch_translate(
            texts=texts,
            source_lang=source_lang,
            target_lang=target_lang,
            context_id=context_id
        )
        
        # Gán kết quả dịch vào các đoạn
        translated_segments = []
        for i, segment in enumerate(segments):
            translated_segment = segment.copy()
            translated_segment['translated_text'] = translated_texts[i]
            translated_segments.append(translated_segment)
        
        return translated_segments 
