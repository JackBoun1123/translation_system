import React, { useState, useEffect, useRef } from 'react';
import './VideoCall.css';

const VideoCallComponent = () => {
  // State và refs
  const [isConnected, setIsConnected] = useState(false);
  const [isCallActive, setIsCallActive] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [translation, setTranslation] = useState('');
  const [sourceLang, setSourceLang] = useState('vi');
  const [targetLang, setTargetLang] = useState('en');
  const [sessionId, setSessionId] = useState(null);
  const [error, setError] = useState(null);
  
  const localVideoRef = useRef(null);
  const remoteVideoRef = useRef(null);
  const wsRef = useRef(null);
  const peerConnectionRef = useRef(null);
  const localStreamRef = useRef(null);

  // Kết nối WebSocket
  useEffect(() => {
    const connectWebSocket = () => {
      const ws = new WebSocket('ws://localhost:5000/ws');
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        setError(null);
      };
      
      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        // Thử kết nối lại sau 3 giây
        setTimeout(connectWebSocket, 3000);
      };
      
      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        setError('Không thể kết nối đến máy chủ');
      };
      
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      };
      
      wsRef.current = ws;
    };
    
    connectWebSocket();
    
    // Cleanup khi unmount
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);
  
  // Xử lý tin nhắn WebSocket
  const handleWebSocketMessage = (data) => {
    const { action } = data;
    
    switch (action) {
      case 'session_created':
        setSessionId(data.session_id);
        createOffer(data.session_id);
        break;
        
      case 'answer':
        handleRemoteAnswer(data.answer);
        break;
        
      case 'transcript':
        setTranscript(data.text);
        break;
        
      case 'translation':
        setTranslation(data.text);
        break;
        
      case 'session_state':
        if (data.state === 'closed') {
          handleCallEnded();
        }
        break;
        
      case 'error':
        setError(data.message);
        break;
        
      default:
        console.log('Unhandled websocket message:', data);
    }
  };
  
  // Bắt đầu cuộc gọi
  const startCall = async () => {
    try {
      // Yêu cầu quyền truy cập media
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: true
      });
      
      // Hiển thị video cục bộ
      if (localVideoRef.current) {
        localVideoRef.current.srcObject = stream;
      }
      
      localStreamRef.current = stream;
      
      // Yêu cầu tạo phiên WebRTC
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          action: 'create_session'
        }));
      }
      
      setIsCallActive(true);
      setError(null);
    } catch (err) {
      console.error('Error accessing media devices:', err);
      setError('Không thể truy cập camera hoặc microphone');
    }
  };
  
  // Tạo offer SDP
  const createOffer = async (sid) => {
    try {
      // Tạo kết nối WebRTC
      const pc = new RTCPeerConnection({
        iceServers: [
          { urls: 'stun:stun.l.google.com:19302' },
          {
            urls: 'turn:localhost:3478',
            username: 'username',
            credential: 'password'
          }
        ]
      });
      
      // Thêm track từ local stream
      if (localStreamRef.current) {
        localStreamRef.current.getTracks().forEach(track => {
          pc.addTrack(track, localStreamRef.current);
        });
      }
      
      // Xử lý ICE candidate
      pc.onicecandidate = (event) => {
        if (event.candidate === null) {
          // ICE gathering complete
          console.log('ICE gathering complete');
        }
      };
      
      // Xử lý track từ remote
      pc.ontrack = (event) => {
        if (remoteVideoRef.current) {
          remoteVideoRef.current.srcObject = event.streams[0];
        }
      };
      
      // Xử lý thay đổi trạng thái kết nối
      pc.onconnectionstatechange = () => {
        console.log('Connection state:', pc.connectionState);
        if (pc.connectionState === 'disconnected' || 
            pc.connectionState === 'failed' || 
            pc.connectionState === 'closed') {
          handleCallEnded();
        }
      };
      
      // Tạo offer
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      
      // Gửi offer đến server
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          action: 'process_offer',
          session_id: sid,
          offer: {
            sdp: pc.localDescription.sdp,
            type: pc.localDescription.type
          }
        }));
      }
      
      peerConnectionRef.current = pc;
      
      // Thiết lập ngôn ngữ
      setLanguages(sid);
    } catch (err) {
      console.error('Error creating offer:', err);
      setError('Lỗi khi tạo kết nối');
    }
  };
  
  // Xử lý answer từ server
  const handleRemoteAnswer = async (answer) => {
    try {
      if (peerConnectionRef.current) {
        const remoteDesc = new RTCSessionDescription(answer);
        await peerConnectionRef.current.setRemoteDescription(remoteDesc);
        console.log('Remote description set successfully');
      }
    } catch (err) {
      console.error('Error setting remote description:', err);
      setError('Lỗi khi thiết lập kết nối');
    }
  };
  
  // Thiết lập ngôn ngữ cho phiên
  const setLanguages = (sid) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: 'set_languages',
        session_id: sid,
        source_lang: sourceLang,
        target_lang: targetLang
      }));
    }
  };
  
  // Kết thúc cuộc gọi
  const endCall = () => {
    if (sessionId && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: 'close_session',
        session_id: sessionId
      }));
    }
    
    handleCallEnded();
  };
  
  // Xử lý khi cuộc gọi kết thúc
  const handleCallEnded = () => {
    // Dừng tất cả track trong local stream
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach(track => track.stop());
      localStreamRef.current = null;
    }
    
    // Đóng kết nối peer
    if (peerConnectionRef.current) {
      peerConnectionRef.current.close();
      peerConnectionRef.current = null;
    }
    
    // Reset video elements
    if (localVideoRef.current) localVideoRef.current.srcObject = null;
    if (remoteVideoRef.current) remoteVideoRef.current.srcObject = null;
    
    // Reset state
    setIsCallActive(false);
    setSessionId(null);
    setTranscript('');
    setTranslation('');
  };
  
  // Thay đổi ngôn ngữ
  const handleLanguageChange = () => {
    if (sessionId) {
      setLanguages(sessionId);
    }
  };

  return (
    <div className="video-call-container">
      <h2>Hệ Thống Dịch Thuật Video Call</h2>
      
      {error && (
        <div className="error-message">
          <p>{error}</p>
        </div>
      )}
      
      <div className="video-grid">
        <div className="video-container local-video">
          <video 
            ref={localVideoRef} 
            autoPlay 
            playsInline 
            muted 
          />
          <div className="label">Bạn</div>
        </div>
        
        <div className="video-container remote-video">
          <video 
            ref={remoteVideoRef} 
            autoPlay 
            playsInline 
          />
          <div className="label">Người đối thoại</div>
        </div>
      </div>
      
      <div className="controls">
        {!isCallActive ? (
          <button 
            className="call-button start" 
            onClick={startCall}
            disabled={!isConnected}
          >
            Bắt đầu cuộc gọi
          </button>
        ) : (
          <button 
            className="call-button end" 
            onClick={endCall}
          >
            Kết thúc cuộc gọi
          </button>
        )}
      </div>
      
      <div className="language-controls">
        <div className="language-select">
          <label>Ngôn ngữ nguồn:</label>
          <select 
            value={sourceLang} 
            onChange={(e) => {
              setSourceLang(e.target.value);
              if (isCallActive) handleLanguageChange();
            }}
          >
            <option value="auto">Tự động</option>
            <option value="vi">Tiếng Việt</option>
            <option value="en">Tiếng Anh</option>
            <option value="fr">Tiếng Pháp</option>
            <option value="de">Tiếng Đức</option>
            <option value="zh">Tiếng Trung</option>
          </select>
        </div>
        
        <div className="language-select">
          <label>Ngôn ngữ đích:</label>
          <select 
            value={targetLang} 
            onChange={(e) => {
              setTargetLang(e.target.value);
              if (isCallActive) handleLanguageChange();
            }}
          >
            <option value="vi">Tiếng Việt</option>
            <option value="en">Tiếng Anh</option>
            <option value="fr">Tiếng Pháp</option>
            <option value="de">Tiếng Đức</option>
            <option value="zh">Tiếng Trung</option>
          </select>
        </div>
      </div>
      
      <div className="translation-area">
        <div className="transcript-box">
          <h3>Văn bản gốc:</h3>
          <p>{transcript || 'Đang lắng nghe...'}</p>
        </div>
        
        <div className="translation-box">
          <h3>Bản dịch:</h3>
          <p>{translation || 'Đang chờ văn bản...'}</p>
        </div>
      </div>
      
      <div className="connection-status">
        <div className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`}></div>
        <span>{isConnected ? 'Đã kết nối đến máy chủ' : 'Đang kết nối...'}</span>
      </div>
    </div>
  );
};

export default VideoCallComponent;