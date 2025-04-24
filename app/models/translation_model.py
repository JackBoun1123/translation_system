"""
Model dịch thuật sử dụng NLLB với CTranslate2 để tối ưu hiệu suất
"""
import os
import torch
import logging
from typing import Dict, List, Optional, Union
from pathlib import Path
import ctranslate2
from transformers import AutoTokenizer
from app.config import TRANSLATION_CONFIG

logger = logging.getLogger(__name__)

class TranslationModel:
    def __init__(self, config: Dict = None):
        """
        Khởi tạo mô hình dịch thuật
        
        Args:
            config: Cấu hình cho mô hình dịch, nếu None sẽ sử dụng cấu hình mặc định
        """
        self.config = config or TRANSLATION_CONFIG
        self.model = None
        self.tokenizer = None
        self.load_model()
        
    def load_model(self):
        """Tải mô hình dịch thuật"""
        try:
            logger.info(f"Đang tải mô hình dịch thuật: {self.config['model_name']}")
            
            # Tạo thư mục download_root nếu chưa tồn tại
            os.makedirs(self.config['download_root'], exist_ok=True)
            
            # Đường dẫn đến mô hình CTranslate2 đã chuyển đổi
            ct2_model_path = Path(self.config['download_root']) / "ct2_model"
            
            # Kiểm tra xem mô hình CTranslate2 đã tồn tại chưa
            if not os.path.exists(ct2_model_path):
                logger.info(f"Chưa tìm thấy mô hình CTranslate2, cần chuyển đổi từ Hugging Face")
                
                # Tạo thư mục ct2_model
                os.makedirs(ct2_model_path, exist_ok=True)
                
                # Chuyển đổi từ Hugging Face sang CTranslate2
                logger.info("Bắt đầu chuyển đổi mô hình, quá trình này có thể mất vài phút...")
                from ctranslate2.converters import TransformersConverter
                
                converter = TransformersConverter(self.config['model_name'])
                converter.convert(
                    output_dir=str(ct2_model_path),
                    quantization=self.config['compute_type'],
                    force=True
                )
                logger.info(f"Đã chuyển đổi thành công mô hình sang CTranslate2 tại {ct2_model_path}")
            
            # Tải tokenizer
            logger.info(f"Đang tải tokenizer: {self.config['model_name']}")
            self.tokenizer = AutoTokenizer.from_pretrained(self.config['model_name'])
            
            # Tải mô hình CTranslate2
            logger.info(f"Đang tải mô hình CTranslate2 từ {ct2_model_path}")
            self.model = ctranslate2.Translator(
                model_path=str(ct2_model_path),
                device=self.config['device'],
                compute_type=self.config['compute_type']
            )
            
            logger.info("Đã tải thành công mô hình dịch thuật")
        except Exception as e:
            logger.error(f"Lỗi khi tải mô hình dịch thuật: {e}")
            raise
    
    def translate(self, text: str, source_lang: Optional[str] = None, 
                 target_lang: Optional[str] = None, context: Optional[str] = None) -> str:
        """
        Dịch văn bản từ ngôn ngữ nguồn sang ngôn ngữ đích
        
        Args:
            text: Văn bản cần dịch
            source_lang: Mã ngôn ngữ nguồn, nếu None sẽ dùng mặc định
            target_lang: Mã ngôn ngữ đích, nếu None sẽ dùng mặc định
            context: Văn bản ngữ cảnh để cải thiện chất lượng dịch
            
        Returns:
            str: Văn bản đã dịch
        """
        if self.model is None or self.tokenizer is None:
            self.load_model()
            
        source_lang = source_lang or self.config['source_language']
        target_lang = target_lang or self.config['target_language']
        
        try:
            # Thêm ngữ cảnh nếu có
            input_text = text
            if context:
                # Thêm ngữ cảnh vào đầu văn bản với định dạng phù hợp
                input_text = f"Context: {context}\nTranslate: {text}"
            
            # Tokenize đầu vào
            tokens = self.tokenizer.encode(input_text, return_tensors=None, add_special_tokens=False)
            
            # Thiết lập source language tag
            source_prefix = f"___{source_lang}___"
            source_prefix_tokens = self.tokenizer.encode(source_prefix, return_tensors=None, add_special_tokens=False)
            
            # Kết hợp prefix và tokens
            source_tokens = source_prefix_tokens + tokens
            
            # Dịch với CTranslate2
            target_prefix = f"___{target_lang}___"
            target_prefix_tokens = self.tokenizer.encode(target_prefix, return_tensors=None, add_special_tokens=False)
            
            results = self.model.translate_batch(
                source=[source_tokens],
                target_prefix=[target_prefix_tokens],
                beam_size=5,
                max_batch_size=1
            )
            
            # Lấy kết quả dịch
            target_tokens = results[0].hypotheses[0]
            translated_text = self.tokenizer.decode(target_tokens, skip_special_tokens=True)
            
            # Loại bỏ bất kỳ phần target prefix nào còn sót lại
            if translated_text.startswith(target_prefix):
                translated_text = translated_text[len(target_prefix):].strip()
                
            return translated_text
            
        except Exception as e:
            logger.error(f"Lỗi khi dịch văn bản: {e}")
            return f"[Lỗi dịch: {str(e)}]"
    
    def translate_with_domain_vocabulary(self, text: str, domain_terms: Dict[str, str], 
                                        source_lang: Optional[str] = None, 
                                        target_lang: Optional[str] = None) -> str:
        """
        Dịch văn bản với hỗ trợ từ điển chuyên ngành
        
        Args:
            text: Văn bản cần dịch
            domain_terms: Từ điển các thuật ngữ chuyên ngành {nguồn: đích}
            source_lang: Mã ngôn ngữ nguồn
            target_lang: Mã ngôn ngữ đích
            
        Returns:
            str: Văn bản đã dịch với thuật ngữ chuyên ngành được áp dụng
        """
        # Dịch văn bản
        translated = self.translate(text, source_lang, target_lang)
        
        # Áp dụng từ điển chuyên ngành cho kết quả dịch
        # (Đơn giản hóa: thực tế cần xử lý phức tạp hơn để áp dụng thuật ngữ đúng ngữ cảnh)
        for source_term, target_term in domain_terms.items():
            # Tìm trong văn bản dịch các thuật ngữ cần thay thế
            # Đây là giải pháp đơn giản, thực tế cần xử lý phức tạp hơn với NLP
            if source_term.lower() in text.lower():
                # Áp dụng thuật ngữ chuyên ngành trong kết quả dịch
                translated = translated.replace(source_term, target_term)
        
        return translated
    
    def batch_translate(self, texts: List[str], source_lang: Optional[str] = None,
                       target_lang: Optional[str] = None) -> List[str]:
        """
        Dịch một loạt các đoạn văn bản trong một lần gọi
        
        Args:
            texts: Danh sách các văn bản cần dịch
            source_lang: Mã ngôn ngữ nguồn
            target_lang: Mã ngôn ngữ đích
            
        Returns:
            List[str]: Danh sách các văn bản đã dịch
        """
        if self.model is None or self.tokenizer is None:
            self.load_model()
            
        source_lang = source_lang or self.config['source_language']
        target_lang = target_lang or self.config['target_language']
        
        try:
            batch_tokens = []
            for text in texts:
                # Tokenize
                tokens = self.tokenizer.encode(text, return_tensors=None, add_special_tokens=False)
                
                # Thiết lập source language tag
                source_prefix = f"___{source_lang}___"
                source_prefix_tokens = self.tokenizer.encode(source_prefix, return_tensors=None, add_special_tokens=False)
                
                # Kết hợp prefix và tokens
                batch_tokens.append(source_prefix_tokens + tokens)
            
            # Dịch với CTranslate2
            target_prefix = f"___{target_lang}___"
            target_prefix_tokens = self.tokenizer.encode(target_prefix, return_tensors=None, add_special_tokens=False)
            
            target_prefixes = [target_prefix_tokens] * len(texts)
            
            results = self.model.translate_batch(
                source=batch_tokens,
                target_prefix=target_prefixes,
                beam_size=5,
                batch_type="examples"
            )
            
            # Giải mã kết quả
            translated_texts = []
            for result in results:
                tokens = result.hypotheses[0]
                text = self.tokenizer.decode(tokens, skip_special_tokens=True)
                
                # Loại bỏ target prefix nếu còn sót lại
                if text.startswith(target_prefix):
                    text = text[len(target_prefix):].strip()
                    
                translated_texts.append(text)
                
            return translated_texts
            
        except Exception as e:
            logger.error(f"Lỗi khi dịch hàng loạt: {e}")
            return ["[Lỗi dịch]"] * len(texts)
