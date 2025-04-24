"""
Model quản lý và xử lý ngữ cảnh (context)
"""
import os
import logging
import uuid
import numpy as np
import re
from typing import Dict, List, Optional, Union, Set, Tuple
import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer
from app.config import CONTEXT_DB_CONFIG

logger = logging.getLogger(__name__)

class ContextModel:
    def __init__(self, config: Dict = None):
        """
        Khởi tạo mô hình xử lý ngữ cảnh
        
        Args:
            config: Cấu hình cho mô hình ngữ cảnh, nếu None sẽ sử dụng cấu hình mặc định
        """
        self.config = config or CONTEXT_DB_CONFIG
        self.client = None
        self.collection = None
        self.embedding_model = None
        self.initialize_db()
        
    def initialize_db(self):
        """Khởi tạo vector database (ChromaDB)"""
        try:
            # Tạo thư mục persist_directory nếu chưa tồn tại
            os.makedirs(self.config['persist_directory'], exist_ok=True)
            
            logger.info(f"Khởi tạo ChromaDB tại {self.config['persist_directory']}")
            self.client = chromadb.PersistentClient(path=str(self.config['persist_directory']))
            
            # Tạo hoặc lấy collection
            self.collection = self.client.get_or_create_collection(
                name="context_documents",
                embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=self.config['embedding_model']
                )
            )
            
            # Tải embedding model
            logger.info(f"Tải mô hình embedding: {self.config['embedding_model']}")
            self.embedding_model = SentenceTransformer(self.config['embedding_model'])
            
            logger.info("Đã khởi tạo thành công cơ sở dữ liệu ngữ cảnh")
        except Exception as e:
            logger.error(f"Lỗi khi khởi tạo cơ sở dữ liệu ngữ cảnh: {e}")
            raise
    
    def add_context_file(self, file_path: str, language: str = "vi", 
                        chunk_size: int = 500, chunk_overlap: int = 50) -> str:
        """
        Thêm file ngữ cảnh vào cơ sở dữ liệu
        
        Args:
            file_path: Đường dẫn đến file ngữ cảnh
            language: Ngôn ngữ của tài liệu
            chunk_size: Kích thước của mỗi đoạn (số từ)
            chunk_overlap: Độ chồng lấn giữa các đoạn (số từ)
            
        Returns:
            str: ID của ngữ cảnh đã thêm
        """
        try:
            # Tạo ID duy nhất cho file ngữ cảnh
            context_id = str(uuid.uuid4())
            
            # Đọc nội dung file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Phân đoạn nội dung thành các đoạn nhỏ
            chunks = self._chunk_text(content, chunk_size, chunk_overlap)
            
            # Thêm các đoạn vào cơ sở dữ liệu vector
            documents = []
            ids = []
            metadatas = []
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{context_id}_{i}"
                documents.append(chunk)
                ids.append(chunk_id)
                metadatas.append({
                    "context_id": context_id,
                    "file_path": file_path,
                    "language": language,
                    "chunk_index": i,
                    "source": os.path.basename(file_path)
                })
            
            # Thêm vào ChromaDB
            self.collection.add(
                documents=documents,
                ids=ids,
                metadatas=metadatas
            )
            
            logger.info(f"Đã thêm file ngữ cảnh: {file_path} với ID: {context_id}")
            
            # Trích xuất thuật ngữ chuyên ngành từ nội dung
            domain_terms = self._extract_domain_terms(content)
            logger.info(f"Đã trích xuất {len(domain_terms)} thuật ngữ chuyên ngành từ tài liệu")
            
            return context_id
            
        except Exception as e:
            logger.error(f"Lỗi khi thêm file ngữ cảnh: {e}")
            return None
    
    def get_relevant_context(self, query: str, context_id: Optional[str] = None, 
                           num_results: int = 3) -> str:
        """
        Lấy ngữ cảnh liên quan từ cơ sở dữ liệu dựa trên truy vấn
        
        Args:
            query: Văn bản truy vấn để tìm ngữ cảnh liên quan
            context_id: ID của ngữ cảnh cụ thể, nếu None sẽ tìm trong tất cả
            num_results: Số lượng kết quả trả về
            
        Returns:
            str: Văn bản ngữ cảnh liên quan
        """
        try:
            # Xây dựng filter nếu có context_id
            query_filter = None
            if context_id:
                query_filter = {"context_id": context_id}
                
            # Thực hiện tìm kiếm
            results = self.collection.query(
                query_texts=[query],
                n_results=num_results,
                where=query_filter
            )
            
            # Tổng hợp kết quả
            if results and 'documents' in results and len(results['documents']) > 0:
                context_texts = results['documents'][0]
                context_string = "\n\n".join(context_texts)
                
                # Giới hạn độ dài của context
                if len(context_string) > 5000:
                    context_string = context_string[:5000] + "..."
                    
                return context_string
            else:
                return ""
                
        except Exception as e:
            logger.error(f"Lỗi khi lấy ngữ cảnh liên quan: {e}")
            return ""
    
    def extract_key_terms(self, context_id: str, max_terms: int = 20) -> List[str]:
        """
        Trích xuất các thuật ngữ quan trọng từ ngữ cảnh
        
        Args:
            context_id: ID của ngữ cảnh
            max_terms: Số lượng thuật ngữ tối đa trả về
            
        Returns:
            List[str]: Danh sách các thuật ngữ quan trọng
        """
        try:
            # Lấy tất cả đoạn từ context_id
            results = self.collection.get(
                where={"context_id": context_id}
            )
            
            if not results or 'documents' not in results or len(results['documents']) == 0:
                return []
                
            # Tổng hợp tất cả nội dung
            all_text = " ".join(results['documents'])
            
            # Trích xuất thuật ngữ
            terms = self._extract_domain_terms(all_text)
            
            # Trả về danh sách các thuật ngữ (tối đa max_terms)
            return terms[:max_terms]
            
        except Exception as e:
            logger.error(f"Lỗi khi trích xuất thuật ngữ: {e}")
            return []
    
    def get_domain_vocabulary(self, context_id: str, source_lang: str, 
                             target_lang: str) -> Dict[str, str]:
        """
        Lấy từ điển chuyên ngành từ ngữ cảnh (chức năng giả lập)
        
        Lưu ý: Trong triển khai thực tế, hàm này sẽ sử dụng dịch thuật để tạo từ điển
        
        Args:
            context_id: ID của ngữ cảnh
            source_lang: Mã ngôn ngữ nguồn
            target_lang: Mã ngôn ngữ đích
            
        Returns:
            Dict[str, str]: Từ điển thuật ngữ chuyên ngành {nguồn: đích}
        """
        # Trích xuất thuật ngữ nguồn
        source_terms = self.extract_key_terms(context_id)
        
        # Giả lập từ điển đích (trong thực tế sẽ sử dụng dịch thuật)
        # Đây chỉ là giả lập, trong thực tế sẽ cần dịch thuật thực sự
        domain_vocabulary = {}
        for term in source_terms:
            # Trong triển khai thực tế, đây sẽ là kết quả dịch thuật
            domain_vocabulary[term] = f"[{term}_translated]"
            
        return domain_vocabulary
    
    def _chunk_text(self, text: str, chunk_size: int = 500, 
                   chunk_overlap: int = 50) -> List[str]:
        """
        Phân đoạn văn bản thành các đoạn nhỏ
        
        Args:
            text: Văn bản cần phân đoạn
            chunk_size: Kích thước mỗi đoạn (số từ)
            chunk_overlap: Độ chồng lấn giữa các đoạn (số từ)
            
        Returns:
            List[str]: Danh sách các đoạn văn bản
        """
        # Tách văn bản thành các từ
        words = text.split()
        
        # Phân đoạn
        chunks = []
        i = 0
        while i < len(words):
            # Lấy đoạn hiện tại
            chunk_words = words[i:i + chunk_size]
            chunk = " ".join(chunk_words)
            chunks.append(chunk)
            
            # Di chuyển đến vị trí tiếp theo (trừ đi overlap)
            i += (chunk_size - chunk_overlap)
            
            # Đảm bảo không âm
            i = max(0, i)
            
            # Nếu đã qua hết văn bản thì dừng
            if i >= len(words):
                break
                
        return chunks
    
    def _extract_domain_terms(self, text: str) -> List[str]:
        """
        Trích xuất các thuật ngữ chuyên ngành từ văn bản
        
        Args:
            text: Văn bản cần trích xuất thuật ngữ
            
        Returns:
            List[str]: Danh sách các thuật ngữ chuyên ngành
        """
        # Xử lý văn bản
        text = text.lower()
        
        # Phương pháp đơn giản: tách từ và đếm tần suất
        # Trong thực tế nên sử dụng các kỹ thuật NLP phức tạp hơn
        words = re.findall(r'\b\w+\b', text)
        word_count = {}
        
        # Đếm tần suất
        for word in words:
            if len(word) > 3:  # Bỏ qua từ quá ngắn
                word_count[word] = word_count.get(word, 0) + 1
        
        # Tìm các cụm từ (2-gram)
        bigrams = []
        for i in range(len(words) - 1):
            if len(words[i]) > 2 and len(words[i+1]) > 2:  # Bỏ qua từ quá ngắn
                bigram = f"{words[i]} {words[i+1]}"
                bigrams.append(bigram)
        
        # Đếm tần suất bigram
        bigram_count = {}
        for bigram in bigrams:
            bigram_count[bigram] = bigram_count.get(bigram, 0) + 1
        
        # Kết hợp từ đơn và cụm từ
        all_terms = []
        
        # Thêm các cụm từ phổ biến (xuất hiện ít nhất 2 lần)
        for bigram, count in sorted(bigram_count.items(), key=lambda x: x[1], reverse=True):
            if count >= 2 and len(all_terms) < 50:
                all_terms.append(bigram)
        
        # Thêm các từ đơn phổ biến
        for word, count in sorted(word_count.items(), key=lambda x: x[1], reverse=True):
            if count >= 5 and len(all_terms) < 100:  # Từ xuất hiện ít nhất 5 lần
                all_terms.append(word)
        
        return all_terms