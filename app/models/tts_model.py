"""
Model Text-to-Speech (TTS) sử dụng Piper
"""
import os
import logging
import subprocess
import tempfile
import numpy as np
from typing import Dict, Optional, Union, Tuple
import soundfile as sf
from pathlib import Path
import requests
import zipfile
from app.config import TTS_CONFIG

logger = logging.getLogger(__name__)

class TTSModel:
    def __init__(self, config: Dict = None):
        """
        Khởi tạo mô hình TTS với Piper
        
        Args:
            config: Cấu hình cho mô hình TTS, nếu None sẽ sử dụng cấu hình mặc định
        """
        self.config = config or TTS_CONFIG
        self.model_path = None
        self.download_model()
        
    def download_model(self):
        """Tải mô hình Piper TTS"""
        try:
            # Tạo thư mục download_root nếu chưa tồn tại
            os.makedirs(self.config['download_root'], exist_ok=True)
            
            model_name = self.config['model_name']
            model_dir = Path(self.config['download_root']) / model_name
            
            if not os.path.exists(model_dir):
                logger.info(f"Đang tải mô hình Piper TTS: {model_name}")
                os.makedirs(model_dir, exist_ok=True)
                
                # URL tải mô hình (thay đổi theo mô hình thực tế)
                model_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/{model_name}.tar.gz"
                
                # Tải mô hình
                response = requests.get(model_url, stream=True)
                response.raise_for_status()
                
                # Lưu tạm thời
                temp_file = model_dir / f"{model_name}.tar.gz"
                with open(temp_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Giải nén
                subprocess.run(['tar', '-xzf', str(temp_file), '-C', str(model_dir)])
                
                # Xóa file tạm
                os.remove(temp_file)
                
                logger.info(f"Đã tải và giải nén mô hình Piper TTS: {model_name}")
            
            # Đường dẫn đến mô hình
            self.model_path = model_dir / f"{model_name}.onnx"
            logger.info(f"Đã thiết lập đường dẫn mô hình Piper TTS: {self.model_path}")
            
        except Exception as e:
            logger.error(f"Lỗi khi tải mô hình Piper TTS: {e}")
            # Fallback: Sử dụng đường dẫn giả định
            self.model_path = Path(self.config['download_root']) / self.config['model_name'] / f"{self.config['model_name']}.onnx"
    
    def synthesize(self, text: str) -> np.ndarray:
        """
        Tổng hợp giọng nói từ văn bản
        
        Args:
            text: Văn bản cần chuyển thành giọng nói
            
        Returns:
            np.ndarray: Dữ liệu âm thanh dạng numpy array
        """
        try:
            # Tạo file tạm cho đầu vào và đầu ra
            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as text_file:
                text_file.write(text.encode('utf-8'))
                text_path = text_file.name
                
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as wav_file:
                wav_path = wav_file.name
            
            # Gọi Piper để tổng hợp giọng nói
            # Giả định Piper đã được cài đặt và có thể gọi thông qua command line
            # Trong thực tế, bạn cần cài đặt Piper hoặc sử dụng Python binding nếu có
            cmd = [
                'piper',
                '--model', str(self.model_path),
                '--output-file', wav_path,
                '--text-file', text_path
            ]
            
            # Thực thi lệnh
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            if process.returncode != 0:
                logger.error(f"Lỗi khi tổng hợp giọng nói: {process.stderr}")
                raise Exception(f"Lỗi Piper: {process.stderr}")
            
            # Đọc file wav
            audio_data, sample_rate = sf.read(wav_path)
            
            # Chuyển đổi định dạng nếu cần
            if sample_rate != self.config['sample_rate']:
                # Cần một thư viện resampling ở đây trong thực tế
                pass
            
            # Xóa file tạm
            os.remove(text_path)
            os.remove(wav_path)
            
            return audio_data
            
        except Exception as e:
            logger.error(f"Lỗi khi tổng hợp giọng nói: {e}")
            # Trả về âm thanh im lặng trong trường hợp lỗi
            return np.zeros(1000, dtype=np.float32)
    
    def synthesize_and_save(self, text: str, output_path: str) -> bool:
        """
        Tổng hợp giọng nói và lưu vào file
        
        Args:
            text: Văn bản cần chuyển thành giọng nói
            output_path: Đường dẫn file đầu ra
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        try:
            # Tạo file tạm cho đầu vào
            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as text_file:
                text_file.write(text.encode('utf-8'))
                text_path = text_file.name
            
            # Gọi Piper để tổng hợp giọng nói trực tiếp vào file đầu ra
            cmd = [
                'piper',
                '--model', str(self.model_path),
                '--output-file', output_path,
                '--text-file', text_path
            ]
            
            # Thực thi lệnh
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            # Xóa file tạm
            os.remove(text_path)
            
            if process.returncode != 0:
                logger.error(f"Lỗi khi tổng hợp giọng nói: {process.stderr}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Lỗi khi tổng hợp giọng nói và lưu file: {e}")
            return False
    
    def synthesize_ssml(self, ssml: str) -> np.ndarray:
        """
        Tổng hợp giọng nói từ văn bản định dạng SSML
        
        Args:
            ssml: Văn bản SSML cần chuyển thành giọng nói
            
        Returns:
            np.ndarray: Dữ liệu âm thanh dạng numpy array
        """
        # Giả định Piper hỗ trợ SSML
        # Quá trình tương tự như synthesize, nhưng với cờ SSML
        try:
            # Tạo file tạm cho đầu vào và đầu ra
            with tempfile.NamedTemporaryFile(suffix='.xml', delete=False) as ssml_file:
                ssml_file.write(ssml.encode('utf-8'))
                ssml_path = ssml_file.name
                
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as wav_file:
                wav_path = wav_file.name
            
            # Gọi Piper với cờ SSML
            cmd = [
                'piper',
                '--model', str(self.model_path),
                '--output-file', wav_path,
                '--ssml-file', ssml_path
            ]
            
            # Thực thi lệnh
            process = subprocess.run(cmd, capture_output=True, text=True)
            
            if process.returncode != 0:
                logger.error(f"Lỗi khi tổng hợp giọng nói từ SSML: {process.stderr}")
                raise Exception(f"Lỗi Piper: {process.stderr}")
            
            # Đọc file wav
            audio_data, sample_rate = sf.read(wav_path)
            
            # Xóa file tạm
            os.remove(ssml_path)
            os.remove(wav_path)
            
            return audio_data
            
        except Exception as e:
            logger.error(f"Lỗi khi tổng hợp giọng nói từ SSML: {e}")
            # Trả về âm thanh im lặng trong trường hợp lỗi
            return np.zeros(1000, dtype=np.float32) 
