"""
Dịch vụ quản lý kết nối WebRTC cho phiên gọi video/audio.
"""
import asyncio
import logging
import uuid
from typing import Dict, Any, Optional, Callable

import json
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaBlackhole, MediaRecorder, MediaRelay
from aiortc.mediastreams import MediaStreamError, AudioStreamTrack, VideoStreamTrack

from app.services.streaming_service import StreamingService

logger = logging.getLogger(__name__)

class AudioTransformTrack(MediaStreamTrack):
    """
    Track cho xử lý audio thời gian thực.
    """
    kind = "audio"
    
    def __init__(self, track, session_id: str, streaming_service: StreamingService):
        super().__init__()
        self.track = track
        self.session_id = session_id
        self.streaming_service = streaming_service
        
    async def recv(self):
        # Nhận frame audio từ track gốc
        frame = await self.track.recv()
        
        # Chuyển đổi frame thành dữ liệu âm thanh nhị phân
        audio_data = frame.to_ndarray().tobytes()
        
        # Xử lý audio và dịch thuật
        await self.streaming_service.process_audio_chunk(
            self.session_id, 
            audio_data
        )
        
        # Trả về frame gốc cho luồng audio
        return frame

class WebRTCService:
    def __init__(self, streaming_service: StreamingService):
        self.streaming_service = streaming_service
        self.peer_connections = {}
        self.audio_relays = {}
        self.video_relays = {}
        self.session_callbacks = {}
        
    async def create_peer_connection(self, session_id: Optional[str] = None) -> str:
        """
        Tạo một kết nối WebRTC mới.
        
        Returns:
            ID phiên kết nối
        """
        if not session_id:
            session_id = str(uuid.uuid4())
            
        # Tạo peer connection
        pc = RTCPeerConnection()
        
        # Tạo các relay cho audio/video
        self.audio_relays[session_id] = MediaRelay()
        self.video_relays[session_id] = MediaRelay()
        self.peer_connections[session_id] = pc
        
        # Xử lý track từ peer
        @pc.on("track")
        async def on_track(track):
            logger.info(f"Nhận track: {track.kind} cho phiên {session_id}")
            
            if track.kind == "audio":
                # Tạo track xử lý audio
                audio_track = AudioTransformTrack(
                    self.audio_relays[session_id].subscribe(track),
                    session_id,
                    self.streaming_service
                )
                pc.addTrack(audio_track)
                
            elif track.kind == "video":
                # Relay video track
                pc.addTrack(
                    self.video_relays[session_id].subscribe(track)
                )
            
            @track.on("ended")
            async def on_ended():
                logger.info(f"Track {track.kind} kết thúc cho phiên {session_id}")
        
        # Xử lý đóng kết nối
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"Trạng thái kết nối thay đổi: {pc.connectionState} cho phiên {session_id}")
            if pc.connectionState == "failed" or pc.connectionState == "closed":
                await self.close_peer_connection(session_id)
        
        return session_id
        
    async def process_offer(self, session_id: str, offer: Dict[str, Any]) -> Dict[str, Any]:
        """
        Xử lý offer SDP từ client.
        
        Args:
            session_id: ID phiên
            offer: Offer SDP từ client
            
        Returns:
            Answer SDP
        """
        if session_id not in self.peer_connections:
            await self.create_peer_connection(session_id)
            
        pc = self.peer_connections[session_id]
        
        # Thiết lập remote description
        offer_sdp = RTCSessionDescription(sdp=offer["sdp"], type=offer["type"])
        await pc.setRemoteDescription(offer_sdp)
        
        # Tạo answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        
        return {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        }
    
    async def close_peer_connection(self, session_id: str):
        """
        Đóng kết nối WebRTC.
        
        Args:
            session_id: ID phiên
        """
        if session_id in self.peer_connections:
            pc = self.peer_connections[session_id]
            await pc.close()
            
            # Xóa peer connection và các relay
            del self.peer_connections[session_id]
            
            if session_id in self.audio_relays:
                del self.audio_relays[session_id]
                
            if session_id in self.video_relays:
                del self.video_relays[session_id]
            
            # Kết thúc stream trong streaming service
            self.streaming_service.end_stream(session_id)
            
            # Gọi callback khi có
            if session_id in self.session_callbacks:
                for callback in self.session_callbacks[session_id]:
                    callback(session_id, "closed")
    
    def register_session_callback(self, session_id: str, callback: Callable[[str, str], None]):
        """
        Đăng ký callback cho các sự kiện phiên.
        
        Args:
            session_id: ID phiên
            callback: Hàm callback với tham số (session_id, event)
        """
        if session_id not in self.session_callbacks:
            self.session_callbacks[session_id] = []
        
        self.session_callbacks[session_id].append(callback)
    
    def set_languages(self, session_id: str, source_lang: str, target_lang: str):
        """
        Thiết lập ngôn ngữ cho phiên.
        
        Args:
            session_id: ID phiên
            source_lang: Ngôn ngữ nguồn
            target_lang: Ngôn ngữ đích
        """
        self.streaming_service.set_languages(session_id, source_lang, target_lang)