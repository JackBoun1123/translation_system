"""
Model ASR (Automatic Speech Recognition) sử dụng Whisper
"""
import os
import numpy as np
import torch
from typing import Dict, List, Optional, Union, Tuple
import logging
from pathlib import Path
from app.config import ASR_CONFIG
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

class ASRModel:
    def __init__(self, config: Dict = None):
        """
        Khởi tạo mô hình ASR với Faster Whisper
        
        Args:
            config: Cấu hình cho mô hình ASR, nếu None sẽ sử dụng cấu hình mặc định
        """
        self.config = config or ASR_CONFIG
        self.model = None
        self.load_model()
        
    def load_model(self):
        """Tải mô hình Whisper"""
        try:
            logger.info(f"Đang tải mô hình Whisper: {self.config['model_size']}")
            
            # Tạo thư mục download_root nếu chưa tồn tại
            os.makedirs(self.config['download_root'], exist_ok=True)
            
            # Tải mô hình Faster Whisper
            self.model = WhisperModel(
                model_size_or_path=self.config['model_size'],
                device=self.config['device'],
                compute_type=self.config['compute_type'],
                download_root=str(self.config['download_root'])
            )
            
            logger.info(f"Đã tải thành công mô hình Whisper {self.config['model_size']}")
        except Exception as e:
            logger.error(f"Lỗi khi tải mô hình Whisper: {e}")
            raise

    def transcribe(self, audio_data: Union[np.ndarray, str], language: Optional[str] = None, 
                   context_prompt: Optional[str] = None) -> Dict:
        """
        Nhận dạng giọng nói từ audio
        
        Args:
            audio_data: Dữ liệu âm thanh, có thể là numpy array hoặc đường dẫn đến file audio
            language: Mã ngôn ngữ, nếu None sẽ sử dụng ngôn ngữ mặc định
            context_prompt: Gợi ý ngữ cảnh để cải thiện độ chính xác
            
        Returns:
            Dict: Kết quả nhận dạng với các thông tin: text, segments, language
        """
        if self.model is None:
            self.load_model()
            
        language = language or self.config['language']
        
        try:
            # Faster Whisper transcribe
            segments, info = self.model.transcribe(
                audio=audio_data,
                language=language,
                initial_prompt=context_prompt,
                word_timestamps=True,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500}
            )
            
            # Xử lý kết quả
            result = {
                "text": "",
                "segments": [],
                "language": info.language,
                "language_probability": info.language_probability
            }
            
            # Chuyển đổi iterator segments thành list để có thể lưu trữ
            for segment in segments:
                result["text"] += segment.text + " "
                segment_dict = {
                    "id": segment.id,
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                    "words": []
                }
                
                # Thêm thông tin từng từ nếu có
                if segment.words:
                    for word in segment.words:
                        segment_dict["words"].append({
                            "word": word.word,
                            "start": word.start,
                            "end": word.end,
                            "probability": word.probability
                        })
                
                result["segments"].append(segment_dict)
                
            result["text"] = result["text"].strip()
            return result
            
        except Exception as e:
            logger.error(f"Lỗi khi nhận dạng giọng nói: {e}")
            return {"text": "", "segments": [], "language": language, "error": str(e)}
    
    def transcribe_with_context(self, audio_data: Union[np.ndarray, str], 
                               context_terms: List[str] = None,
                               language: Optional[str] = None) -> Dict:
        """
        Nhận dạng giọng nói có tích hợp ngữ cảnh
        
        Args:
            audio_data: Dữ liệu âm thanh
            context_terms: Danh sách các thuật ngữ liên quan từ ngữ cảnh
            language: Mã ngôn ngữ
            
        Returns:
            Dict: Kết quả nhận dạng đã được cải thiện với ngữ cảnh
        """
        context_prompt = None
        if context_terms and len(context_terms) > 0:
            # Tạo context prompt từ các thuật ngữ
            context_prompt = f"Transcript contains these terms: {', '.join(context_terms[:15])}"
            
        # Thực hiện nhận dạng với context prompt
        result = self.transcribe(audio_data, language, context_prompt)
        
        return result

    def segment_audio(self, audio_data: np.ndarray, sample_rate: int = 16000) -> List[Dict]:
        """
        Phân đoạn audio dựa trên sự im lặng
        
        Args:
            audio_data: Dữ liệu âm thanh dạng numpy array
            sample_rate: Tần số lấy mẫu của audio
            
        Returns:
            List[Dict]: Danh sách các đoạn âm thanh với thời gian bắt đầu và kết thúc
        """
        # Đơn giản hóa: phát hiện khoảng lặng bằng ngưỡng biên độ
        threshold = 0.01  # Ngưỡng biên độ để xác định im lặng
        min_silence_samples = int(0.5 * sample_rate)  # 0.5 giây im lặng tối thiểu
        
        # Tính biên độ
        amplitude = np.abs(audio_data)
        is_silence = amplitude < threshold
        
        segments = []
        start = None
        silence_count = 0
        
        for i, silent in enumerate(is_silence):
            if not silent and start is None:
                # Bắt đầu đoạn nói
                start = i / sample_rate
                silence_count = 0
            elif silent and start is not None:
                silence_count += 1
                if silence_count >= min_silence_samples:
                    # Kết thúc đoạn nói
                    end = (i - silence_count) / sample_rate
                    if end - start > 0.5:  # Chỉ lấy đoạn dài hơn 0.5 giây
                        segments.append({
                            "start": start,
                            "end": end,
                            "data": audio_data[int(start * sample_rate):int(end * sample_rate)]
                        })
                    start = None
            elif not silent:
                silence_count = 0
        
        # Xử lý đoạn cuối cùng
        if start is not None:
            end = len(audio_data) / sample_rate
            segments.append({
                "start": start,
                "end": end,
                "data": audio_data[int(start * sample_rate):]
            })
        
        return segments