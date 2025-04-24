#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Mô-đun chính của ứng dụng Hệ Thống Dịch Thuật.
"""

import argparse
import asyncio
import logging
import sys
from typing import Dict, Any, Optional

from fastapi import FastAPI, WebSocket, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect

from app.config import load_config
from app.models.asr_model import ASRModel
from app.models.translation_model import TranslationModel
from app.models.tts_model import TTSModel
from app.controllers.asr_controller import ASRController
from app.controllers.translation_controller import TranslationController
from app.controllers.tts_controller import TTSController
from app.controllers.context_controller import ContextController
from app.views.cli_view import CLIView
from app.views.api_view import APIView
from app.views.websocket_view import WebSocketView
from app.services.streaming_service import StreamingService
from app.services.webrtc_service import WebRTCService
from app.utils.audio_utils import AudioProcessor
from app.utils.model_loader import load_models

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

# Tạo ứng dụng FastAPI
app = FastAPI(title="Hệ Thống Dịch Thuật API", version="1.0.0")

# Cấu hình CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Trong môi trường production, hãy chỉ định các tên miền cụ thể
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Khởi tạo các đối tượng toàn cục
config = None
asr_model = None
translation_model = None
tts_model = None
audio_processor = None
streaming_service = None
webrtc_service = None
websocket_view = None

@app.on_event("startup")
async def startup_event():
    """
    Khởi tạo các thành phần khi ứng dụng khởi động.
    """
    global config, asr_model, translation_model, tts_model, audio_processor
    global streaming_service, webrtc_service, websocket_view
    
    # Tải cấu hình
    config = load_config()
    
    # Khởi tạo các models
    asr_model = ASRModel(config)
    translation_model = TranslationModel(config)
    tts_model = TTSModel(config)
    
    # Khởi tạo audio processor
    audio_processor = AudioProcessor(config)
    
    # Khởi tạo streaming service
    streaming_service = StreamingService(asr_model, translation_model, tts_model, audio_processor)
    
    # Khởi tạo WebRTC service
    webrtc_service = WebRTCService(streaming_service)
    
    # Khởi tạo WebSocket view
    websocket_view = WebSocketView(webrtc_service, streaming_service)
    
    logger.info("Hệ Thống Dịch Thuật đã khởi động thành công!")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Dọn dẹp tài nguyên khi ứng dụng dừng.
    """
    # Thêm các thao tác dọn dẹp nếu cần
    logger.info("Hệ Thống Dịch Thuật đã dừng!")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Endpoint WebSocket cho kết nối thời gian thực.
    """
    # Đảm bảo đã khởi tạo websocket_view
    if websocket_view is None:
        await startup_event()
        
    await websocket_view.websocket_endpoint(websocket)

def main():
    """
    Hàm chính để chạy ứng dụng.
    """
    parser = argparse.ArgumentParser(description="Hệ Thống Dịch Thuật")
    parser.add_argument("--config", type=str, default="config.json",
                        help="Đường dẫn đến tệp cấu hình")
    parser.add_argument("--mode", type=str, choices=["cli", "api"], default="cli",
                        help="Chế độ chạy ứng dụng (cli hoặc api)")
    parser.add_argument("--port", type=int, default=5000,
                        help="Cổng để chạy API server")
    parser.add_argument("--host", type=str, default="0.0.0.0",
                        help="Host để chạy API server")
    parser.add_argument("--source", type=str, default="auto",
                        help="Ngôn ngữ nguồn mặc định")
    parser.add_argument("--target", type=str, default="en",
                        help="Ngôn ngữ đích mặc định")
    
    args = parser.parse_args()
    
    # Tải cấu hình
    global config
    config = load_config(args.config)
    
    if args.mode == "cli":
        # Chạy giao diện dòng lệnh
        asyncio.run(run_cli(args))
    else:
        # Chạy API server
        import uvicorn
        logger.info(f"Khởi động API server tại {args.host}:{args.port}")
        uvicorn.run(app, host=args.host, port=args.port)

async def run_cli(args):
    """
    Chạy ứng dụng trong chế độ CLI.
    """
    # Khởi tạo các models
    global asr_model, translation_model, tts_model, audio_processor
    asr_model = ASRModel(config)
    translation_model = TranslationModel(config)
    tts_model = TTSModel(config)
    audio_processor = AudioProcessor(config)
    
    # Khởi tạo các controllers
    asr_controller = ASRController(asr_model)
    translation_controller = TranslationController(translation_model)
    tts_controller = TTSController(tts_model)
    context_controller = ContextController()
    
    # Khởi tạo và chạy CLI view
    cli_view = CLIView(
        asr_controller,
        translation_controller,
        tts_controller,
        context_controller,
        source_lang=args.source,
        target_lang=args.target
    )
    
    await cli_view.run()

if __name__ == "__main__":
    main()