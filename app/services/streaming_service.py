"""
Dịch vụ xử lý streaming audio và video thời gian thực.
"""
import asyncio
import logging
from typing import Dict, Callable, Any, Optional

from app.models.asr_model import ASRModel
from app.models.translation_model import TranslationModel
from app.models.tts_model import TTSModel
from app.utils.audio_utils import AudioProcessor

logger = logging.getLogger(__name__)

class StreamingService:
    def __init__(self, asr_model: ASRModel, translation_model: TranslationModel, 
                 tts_model: TTSModel, audio_processor: AudioProcessor):
        self.asr_model = asr_model
        self.translation_model = translation_model
        self.tts_model = tts_model
        self.audio_processor = audio_processor
        self.active_streams = {}
        self.buffer_size = 4096  # Kích thước buffer âm thanh
        self.transcript_callbacks = {}
        self.translation_callbacks = {}
        
    async def process_audio_chunk(self, session_id: str, audio_chunk: bytes) -> Dict[str, Any]:
        """
        Xử lý một đoạn âm thanh từ stream và trả về kết quả.
        
        Args:
            session_id: ID của phiên làm việc
            audio_chunk: Chunk âm thanh dạng bytes
            
        Returns:
            Dict chứa transcript và bản dịch
        """
        if session_id not in self.active_streams:
            self.active_streams[session_id] = {
                'audio_buffer': bytearray(),
                'last_transcript': '',
                'last_translation': '',
                'source_lang': 'auto',
                'target_lang': 'en'
            }
            
        stream = self.active_streams[session_id]
        
        # Thêm chunk vào buffer
        stream['audio_buffer'].extend(audio_chunk)
        
        # Khi buffer đủ lớn để xử lý
        if len(stream['audio_buffer']) >= self.buffer_size:
            # Chuyển đổi âm thanh sang định dạng phù hợp
            audio_data = self.audio_processor.process_raw_audio(bytes(stream['audio_buffer']))
            
            # Nhận dạng giọng nói
            transcript = await self.asr_model.transcribe_audio_stream(audio_data)
            
            # Nếu có transcript mới
            if transcript and transcript != stream['last_transcript']:
                stream['last_transcript'] = transcript
                
                # Dịch văn bản
                translation = await self.translation_model.translate_text(
                    transcript, 
                    source_lang=stream['source_lang'], 
                    target_lang=stream['target_lang']
                )
                
                stream['last_translation'] = translation
                
                # Tạo âm thanh từ bản dịch
                translated_audio = await self.tts_model.synthesize(
                    translation, 
                    lang=stream['target_lang']
                )
                
                # Gọi callback nếu được đăng ký
                if session_id in self.transcript_callbacks:
                    self.transcript_callbacks[session_id](transcript)
                
                if session_id in self.translation_callbacks:
                    self.translation_callbacks[session_id](translation)
                
                # Xóa buffer
                stream['audio_buffer'] = bytearray()
                
                return {
                    'transcript': transcript,
                    'translation': translation,
                    'translated_audio': translated_audio
                }
        
        # Nếu buffer chưa đủ lớn
        return {
            'transcript': stream.get('last_transcript', ''),
            'translation': stream.get('last_translation', ''),
            'translated_audio': None
        }
    
    def register_transcript_callback(self, session_id: str, callback: Callable[[str], None]):
        """Đăng ký callback khi có transcript mới"""
        self.transcript_callbacks[session_id] = callback
    
    def register_translation_callback(self, session_id: str, callback: Callable[[str], None]):
        """Đăng ký callback khi có bản dịch mới"""
        self.translation_callbacks[session_id] = callback
    
    def set_languages(self, session_id: str, source_lang: str, target_lang: str):
        """Thiết lập ngôn ngữ nguồn và đích cho phiên"""
        if session_id not in self.active_streams:
            self.active_streams[session_id] = {
                'audio_buffer': bytearray(),
                'last_transcript': '',
                'last_translation': '',
                'source_lang': source_lang,
                'target_lang': target_lang
            }
        else:
            self.active_streams[session_id]['source_lang'] = source_lang
            self.active_streams[session_id]['target_lang'] = target_lang
    
    def end_stream(self, session_id: str):
        """Kết thúc một phiên stream"""
        if session_id in self.active_streams:
            del self.active_streams[session_id]
        
        if session_id in self.transcript_callbacks:
            del self.transcript_callbacks[session_id]
            
        if session_id in self.translation_callbacks:
            del self.translation_callbacks[session_id]