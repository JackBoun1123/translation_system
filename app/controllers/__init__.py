"""
Khởi tạo các bộ điều khiển của hệ thống
"""
from app.controllers.asr_controller import ASRController
from app.controllers.translation_controller import TranslationController
from app.controllers.tts_controller import TTSController
from app.controllers.context_controller import ContextController
from app.controllers.streaming_controller import StreamingController

__all__ = [
    'ASRController',
    'TranslationController',
    'TTSController',
    'ContextController',
    'StreamingController'
] 
