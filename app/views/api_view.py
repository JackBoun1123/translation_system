"""
API view implementation for the translation system.

This module provides a REST API interface for the translation system,
allowing external applications to access the translation services.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Union
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import asyncio
from io import BytesIO

# Assuming controllers are implemented
from ..controllers.asr_controller import ASRController
from ..controllers.translation_controller import TranslationController
from ..controllers.tts_controller import TTSController
from ..controllers.context_controller import ContextController
from ..controllers.streaming_controller import StreamingController

# Configure logger
logger = logging.getLogger(__name__)

class TranslationRequest(BaseModel):
    """Request model for text translation"""
    text: str
    source_language: Optional[str] = None
    target_language: str
    context_id: Optional[str] = None
    preserve_formatting: bool = True

class ASRRequest(BaseModel):
    """Request model for ASR settings"""
    language: Optional[str] = None
    model: Optional[str] = "default"
    context_id: Optional[str] = None

class TTSRequest(BaseModel):
    """Request model for TTS settings"""
    text: str
    language: str
    voice: Optional[str] = "default"
    speed: float = 1.0

class ContextRequest(BaseModel):
    """Request model for context creation/update"""
    name: str
    description: Optional[str] = None
    languages: List[str]
    domain: Optional[str] = None
    custom_terminology: Optional[Dict[str, str]] = None

class StreamingRequest(BaseModel):
    """Request model for streaming translation"""
    source_language: Optional[str] = None
    target_language: str
    context_id: Optional[str] = None

class APIView:
    """API View for the translation system"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the API view.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.app = FastAPI(
            title="Translation System API",
            description="API for the translation system",
            version="1.0.0"
        )
        
        # Setup CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=config.get("cors_origins", ["*"]),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Initialize controllers
        self.asr_controller = ASRController(config)
        self.translation_controller = TranslationController(config)
        self.tts_controller = TTSController(config)
        self.context_controller = ContextController(config)
        self.streaming_controller = StreamingController(config)
        
        # Register routes
        self._register_routes()
    
    def _register_routes(self):
        """Register API routes"""
        # Health check
        @self.app.get("/health")
        async def health_check():
            return {"status": "ok", "version": self.config.get("version", "1.0.0")}
        
        # Translation routes
        @self.app.post("/translate/text")
        async def translate_text(request: TranslationRequest):
            try:
                result = await self.translation_controller.translate_text(
                    text=request.text,
                    source_language=request.source_language,
                    target_language=request.target_language,
                    context_id=request.context_id,
                    preserve_formatting=request.preserve_formatting
                )
                return result
            except Exception as e:
                logger.error(f"Error in translate_text: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/translate/file")
        async def translate_file(
            file: UploadFile = File(...),
            source_language: Optional[str] = Form(None),
            target_language: str = Form(...),
            context_id: Optional[str] = Form(None)
        ):
            try:
                file_content = await file.read()
                result = await self.translation_controller.translate_document(
                    file_content=file_content,
                    filename=file.filename,
                    source_language=source_language,
                    target_language=target_language,
                    context_id=context_id
                )
                
                # Return translated document
                return StreamingResponse(
                    BytesIO(result["content"]),
                    media_type=result["mime_type"],
                    headers={"Content-Disposition": f"attachment; filename={result['filename']}"}
                )
            except Exception as e:
                logger.error(f"Error in translate_file: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # ASR routes
        @self.app.post("/asr")
        async def speech_to_text(
            audio: UploadFile = File(...),
            settings: Optional[str] = Form(None)
        ):
            try:
                # Parse settings if provided
                asr_settings = ASRRequest(**json.loads(settings)) if settings else ASRRequest()
                
                audio_content = await audio.read()
                result = await self.asr_controller.transcribe(
                    audio_data=audio_content,
                    language=asr_settings.language,
                    model=asr_settings.model,
                    context_id=asr_settings.context_id
                )
                return result
            except Exception as e:
                logger.error(f"Error in speech_to_text: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # TTS routes
        @self.app.post("/tts")
        async def text_to_speech(request: TTSRequest):
            try:
                audio_data = await self.tts_controller.synthesize(
                    text=request.text,
                    language=request.language,
                    voice=request.voice,
                    speed=request.speed
                )
                
                return StreamingResponse(
                    BytesIO(audio_data),
                    media_type="audio/wav",
                    headers={"Content-Disposition": "attachment; filename=synthesized_speech.wav"}
                )
            except Exception as e:
                logger.error(f"Error in text_to_speech: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Context routes
        @self.app.post("/context")
        async def create_context(request: ContextRequest):
            try:
                context_id = await self.context_controller.create_context(
                    name=request.name,
                    description=request.description,
                    languages=request.languages,
                    domain=request.domain,
                    custom_terminology=request.custom_terminology
                )
                return {"context_id": context_id}
            except Exception as e:
                logger.error(f"Error in create_context: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/context/{context_id}")
        async def get_context(context_id: str):
            try:
                context = await self.context_controller.get_context(context_id)
                if not context:
                    raise HTTPException(status_code=404, detail="Context not found")
                return context
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error in get_context: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.put("/context/{context_id}")
        async def update_context(context_id: str, request: ContextRequest):
            try:
                success = await self.context_controller.update_context(
                    context_id=context_id,
                    name=request.name,
                    description=request.description,
                    languages=request.languages,
                    domain=request.domain,
                    custom_terminology=request.custom_terminology
                )
                if not success:
                    raise HTTPException(status_code=404, detail="Context not found")
                return {"status": "updated"}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error in update_context: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/context/{context_id}")
        async def delete_context(context_id: str):
            try:
                success = await self.context_controller.delete_context(context_id)
                if not success:
                    raise HTTPException(status_code=404, detail="Context not found")
                return {"status": "deleted"}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error in delete_context: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Streaming translation routes
        @self.app.websocket("/translate/streaming")
        async def streaming_translation(websocket):
            try:
                await websocket.accept()
                
                # Get streaming settings
                settings_json = await websocket.receive_text()
                settings = StreamingRequest(**json.loads(settings_json))
                
                # Initialize streaming session
                session_id = await self.streaming_controller.create_session(
                    source_language=settings.source_language,
                    target_language=settings.target_language,
                    context_id=settings.context_id
                )
                
                # Send session ID
                await websocket.send_json({"session_id": session_id})
                
                # Process audio chunks
                while True:
                    try:
                        chunk = await websocket.receive_bytes()
                        if not chunk:
                            continue
                            
                        # Process chunk
                        result = await self.streaming_controller.process_chunk(
                            session_id=session_id,
                            audio_chunk=chunk
                        )
                        
                        # Send translation result
                        await websocket.send_json(result)
                    except Exception as e:
                        logger.error(f"Error processing streaming chunk: {str(e)}")
                        await websocket.send_json({"error": str(e)})
                        break
            except Exception as e:
                logger.error(f"Error in streaming_translation: {str(e)}")
                # Connection likely already closed
            finally:
                # Clean up session
                if 'session_id' in locals():
                    await self.streaming_controller.close_session(session_id)
    
    def run(self, host: str = "0.0.0.0", port: int = 8000, debug: bool = False):
        """
        Run the API server.
        
        Args:
            host: Host address to listen on
            port: Port to listen on
            debug: Whether to run in debug mode
        """
        uvicorn.run(self.app, host=host, port=port, debug=debug) 
