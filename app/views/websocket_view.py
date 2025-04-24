"""
Quản lý kết nối WebSocket cho hệ thống dịch thuật trực tuyến.
"""
import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Set

import uuid
from fastapi import WebSocket, WebSocketDisconnect, Depends
from starlette.websockets import WebSocketState

from app.services.webrtc_service import WebRTCService
from app.services.streaming_service import StreamingService

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Quản lý các kết nối WebSocket.
    """
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_to_connection: Dict[str, str] = {}
    
    async def connect(self, websocket: WebSocket, connection_id: Optional[str] = None) -> str:
        """
        Kết nối WebSocket mới.
        
        Args:
            websocket: WebSocket connection
            connection_id: ID kết nối tùy chọn
            
        Returns:
            ID kết nối
        """
        if not connection_id:
            connection_id = str(uuid.uuid4())
            
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        
        return connection_id
    
    def get_connection(self, connection_id: str) -> Optional[WebSocket]:
        """
        Lấy kết nối WebSocket theo ID.
        
        Args:
            connection_id: ID kết nối
            
        Returns:
            WebSocket object nếu có
        """
        return self.active_connections.get(connection_id)
    
    async def disconnect(self, connection_id: str):
        """
        Ngắt kết nối WebSocket.
        
        Args:
            connection_id: ID kết nối
        """
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close()
            del self.active_connections[connection_id]
        
        # Xóa ánh xạ session_id nếu có
        for session_id, conn_id in list(self.session_to_connection.items()):
            if conn_id == connection_id:
                del self.session_to_connection[session_id]
    
    def register_session(self, session_id: str, connection_id: str):
        """
        Đăng ký ánh xạ giữa session ID và connection ID.
        
        Args:
            session_id: ID phiên WebRTC
            connection_id: ID kết nối WebSocket
        """
        self.session_to_connection[session_id] = connection_id
    
    def get_connection_by_session(self, session_id: str) -> Optional[WebSocket]:
        """
        Lấy kết nối WebSocket theo Session ID.
        
        Args:
            session_id: ID phiên
            
        Returns:
            WebSocket object nếu có
        """
        connection_id = self.session_to_connection.get(session_id)
        if connection_id:
            return self.get_connection(connection_id)
        return None
    
    async def send_json(self, connection_id: str, data: Dict[str, Any]):
        """
        Gửi dữ liệu JSON tới kết nối cụ thể.
        
        Args:
            connection_id: ID kết nối
            data: Dữ liệu để gửi
        """
        websocket = self.get_connection(connection_id)
        if websocket and websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.send_json(data)
    
    async def send_json_by_session(self, session_id: str, data: Dict[str, Any]):
        """
        Gửi dữ liệu JSON theo Session ID.
        
        Args:
            session_id: ID phiên
            data: Dữ liệu để gửi
        """
        connection_id = self.session_to_connection.get(session_id)
        if connection_id:
            await self.send_json(connection_id, data)

class WebSocketView:
    """
    View quản lý các kết nối WebSocket cho hệ thống dịch thuật trực tuyến.
    """
    def __init__(self, webrtc_service: WebRTCService, streaming_service: StreamingService):
        self.webrtc_service = webrtc_service
        self.streaming_service = streaming_service
        self.connection_manager = ConnectionManager()
    
    async def websocket_endpoint(self, websocket: WebSocket):
        connection_id = await self.connection_manager.connect(websocket)
        
        try:
            while True:
                message = await websocket.receive_json()
                await self.handle_message(connection_id, message)
        except WebSocketDisconnect:
            await self.handle_disconnect(connection_id)
        except Exception as e:
            logger.error(f"Lỗi xử lý WebSocket: {str(e)}")
            await self.connection_manager.disconnect(connection_id)
    
    async def handle_message(self, connection_id: str, message: Dict[str, Any]):
        """
        Xử lý tin nhắn từ WebSocket.
        
        Args:
            connection_id: ID kết nối
            message: Tin nhắn nhận được
        """
        action = message.get("action")
        
        if action == "create_session":
            # Tạo phiên WebRTC
            session_id = await self.webrtc_service.create_peer_connection()
            
            # Đăng ký các callback
            self.register_callbacks(session_id, connection_id)
            
            # Đăng ký session cho connection
            self.connection_manager.register_session(session_id, connection_id)
            
            # Trả về ID phiên
            await self.connection_manager.send_json(
                connection_id, 
                {"action": "session_created", "session_id": session_id}
            )
        
        elif action == "process_offer":
            # Xử lý offer SDP
            session_id = message.get("session_id")
            offer = message.get("offer")
            
            if not session_id or not offer:
                await self.connection_manager.send_json(
                    connection_id, 
                    {"action": "error", "message": "session_id và offer là bắt buộc"}
                )
                return
            
            # Đăng ký session cho connection nếu chưa
            self.connection_manager.register_session(session_id, connection_id)
            
            # Xử lý offer và lấy answer
            answer = await self.webrtc_service.process_offer(session_id, offer)
            
            # Trả về answer
            await self.connection_manager.send_json(
                connection_id, 
                {"action": "answer", "session_id": session_id, "answer": answer}
            )
        
        elif action == "set_languages":
            # Thiết lập ngôn ngữ cho phiên
            session_id = message.get("session_id")
            source_lang = message.get("source_lang", "auto")
            target_lang = message.get("target_lang", "en")
            
            if not session_id:
                await self.connection_manager.send_json(
                    connection_id, 
                    {"action": "error", "message": "session_id là bắt buộc"}
                )
                return
            
            # Thiết lập ngôn ngữ
            self.webrtc_service.set_languages(session_id, source_lang, target_lang)
            
            await self.connection_manager.send_json(
                connection_id, 
                {"action": "languages_set", "session_id": session_id}
            )
        
        elif action == "close_session":
            # Đóng phiên WebRTC
            session_id = message.get("session_id")
            
            if not session_id:
                await self.connection_manager.send_json(
                    connection_id, 
                    {"action": "error", "message": "session_id là bắt buộc"}
                )
                return
            
            # Đóng kết nối
            await self.webrtc_service.close_peer_connection(session_id)
            
            await self.connection_manager.send_json(
                connection_id, 
                {"action": "session_closed", "session_id": session_id}
            )
    
    async def handle_disconnect(self, connection_id: str):
        """
        Xử lý ngắt kết nối WebSocket.
        
        Args:
            connection_id: ID kết nối
        """
        # Đóng tất cả các phiên được liên kết với kết nối này
        for session_id, conn_id in list(self.connection_manager.session_to_connection.items()):
            if conn_id == connection_id:
                await self.webrtc_service.close_peer_connection(session_id)
        
        # Đóng kết nối WebSocket
        await self.connection_manager.disconnect(connection_id)
    
    def register_callbacks(self, session_id: str, connection_id: str):
        """
        Đăng ký các callback cho phiên.
        
        Args:
            session_id: ID phiên
            connection_id: ID kết nối
        """
        # Callback khi có transcript mới
        def on_transcript(transcript: str):
            asyncio.create_task(
                self.connection_manager.send_json_by_session(
                    session_id,
                    {"action": "transcript", "session_id": session_id, "text": transcript}
                )
            )
        
        # Callback khi có bản dịch mới
        def on_translation(translation: str):
            asyncio.create_task(
                self.connection_manager.send_json_by_session(
                    session_id,
                    {"action": "translation", "session_id": session_id, "text": translation}
                )
            )
        
        # Callback khi trạng thái phiên thay đổi
        def on_session_state(session_id: str, state: str):
            asyncio.create_task(
                self.connection_manager.send_json_by_session(
                    session_id,
                    {"action": "session_state", "session_id": session_id, "state": state}
                )
            )
        
        # Đăng ký các callback
        self.streaming_service.register_transcript_callback(session_id, on_transcript)
        self.streaming_service.register_translation_callback(session_id, on_translation)
        self.webrtc_service.register_session_callback(session_id, on_session_state)