/**
 * Dịch vụ WebRTC cho frontend
 * Quản lý kết nối WebRTC và WebSocket cho tính năng video call với dịch thuật thời gian thực
 */

class WebRTCService {
    constructor() {
      this.websocket = null;
      this.peerConnection = null;
      this.localStream = null;
      this.remoteStream = null;
      this.sessionId = null;
      this.isConnected = false;
      this.callbacks = {
        onConnectionStateChange: null,
        onTranscript: null,
        onTranslation: null,
        onError: null,
        onSessionCreated: null,
        onCallEstablished: null,
        onCallEnded: null
      };
    }
  
    /**
     * Kết nối tới WebSocket server
     * @param {string} url - URL của WebSocket server
     * @returns {Promise} - Promise giải quyết khi kết nối thành công
     */
    connect(url) {
      return new Promise((resolve, reject) => {
        try {
          this.websocket = new WebSocket(url);
  
          this.websocket.onopen = () => {
            console.log('WebSocket connected');
            this.isConnected = true;
            if (this.callbacks.onConnectionStateChange) {
              this.callbacks.onConnectionStateChange(true);
            }
            resolve();
          };
  
          this.websocket.onclose = () => {
            console.log('WebSocket disconnected');
            this.isConnected = false;
            if (this.callbacks.onConnectionStateChange) {
              this.callbacks.onConnectionStateChange(false);
            }
          };
  
          this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            if (this.callbacks.onError) {
              this.callbacks.onError('Lỗi kết nối WebSocket');
            }
            reject(error);
          };
  
          this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
          };
        } catch (error) {
          console.error('Failed to create WebSocket:', error);
          if (this.callbacks.onError) {
            this.callbacks.onError('Không thể kết nối đến máy chủ');
          }
          reject(error);
        }
      });
    }
  
    /**
     * Xử lý tin nhắn từ WebSocket
     * @param {Object} data - Dữ liệu từ server
     */
    handleWebSocketMessage(data) {
      const { action } = data;
  
      switch (action) {
        case 'session_created':
          this.sessionId = data.session_id;
          if (this.callbacks.onSessionCreated) {
            this.callbacks.onSessionCreated(data.session_id);
          }
          break;
  
        case 'answer':
          this.handleRemoteAnswer(data.answer);
          break;
  
        case 'transcript':
          if (this.callbacks.onTranscript) {
            this.callbacks.onTranscript(data.text);
          }
          break;
  
        case 'translation':
          if (this.callbacks.onTranslation) {
            this.callbacks.onTranslation(data.text);
          }
          break;
  
        case 'session_state':
          if (data.state === 'closed') {
            if (this.callbacks.onCallEnded) {
              this.callbacks.onCallEnded();
            }
          }
          break;
  
        case 'error':
          if (this.callbacks.onError) {
            this.callbacks.onError(data.message);
          }
          break;
  
        default:
          console.log('Unhandled websocket message:', data);
      }
    }
  
    /**
     * Bắt đầu một phiên WebRTC mới
     * @returns {Promise} - Promise giải quyết khi phiên được tạo
     */
    createSession() {
      return new Promise((resolve, reject) => {
        if (!this.isConnected) {
          reject(new Error('WebSocket chưa kết nối'));
          return;
        }
  
        try {
          this.websocket.send(JSON.stringify({
            action: 'create_session'
          }));
  
          // Resolve được xử lý khi nhận được sự kiện session_created
          const sessionCreatedHandler = (sessionId) => {
            resolve(sessionId);
            // Xóa listener sau khi đã nhận được phản hồi
            const originalCallback = this.callbacks.onSessionCreated;
            this.callbacks.onSessionCreated = (sid) => {
              if (originalCallback) originalCallback(sid);
            };
          };
  
          // Lưu callback gốc và thêm handler tạm thời
          const originalCallback = this.callbacks.onSessionCreated;
          this.callbacks.onSessionCreated = (sessionId) => {
            sessionCreatedHandler(sessionId);
            if (originalCallback) originalCallback(sessionId);
          };
  
          // Timeout sau 10 giây
          setTimeout(() => {
            reject(new Error('Tạo phiên hết thời gian chờ'));
            // Khôi phục callback gốc
            this.callbacks.onSessionCreated = originalCallback;
          }, 10000);
        } catch (error) {
          console.error('Error creating session:', error);
          reject(error);
        }
      });
    }
  
    /**
     * Thiết lập kết nối WebRTC
     * @param {MediaStream} localStream - Luồng media cục bộ
     * @returns {Promise} - Promise giải quyết khi kết nối được thiết lập
     */
    async setupPeerConnection(localStream) {
      if (!this.sessionId) {
        throw new Error('Phiên chưa được tạo');
      }
  
      this.localStream = localStream;
  
      try {
        // Tạo peer connection
        this.peerConnection = new RTCPeerConnection({
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
        this.localStream.getTracks().forEach(track => {
          this.peerConnection.addTrack(track, this.localStream);
        });
  
        // Xử lý track từ remote
        this.peerConnection.ontrack = (event) => {
          this.remoteStream = event.streams[0];
          if (this.callbacks.onCallEstablished) {
            this.callbacks.onCallEstablished(this.remoteStream);
          }
        };
  
        // Xử lý ICE candidate
        this.peerConnection.onicecandidate = (event) => {
          if (event.candidate === null) {
            // ICE gathering complete
            console.log('ICE gathering complete');
          }
        };
  
        // Xử lý thay đổi trạng thái kết nối
        this.peerConnection.onconnectionstatechange = () => {
          console.log('Connection state:', this.peerConnection.connectionState);
          if (this.peerConnection.connectionState === 'disconnected' ||
              this.peerConnection.connectionState === 'failed' ||
              this.peerConnection.connectionState === 'closed') {
            this.endCall();
          }
        };
  
        // Tạo offer
        const offer = await this.peerConnection.createOffer({
          offerToReceiveAudio: true,
          offerToReceiveVideo: true
        });
        
        await this.peerConnection.setLocalDescription(offer);
  
        // Gửi offer đến server
        this.websocket.send(JSON.stringify({
          action: 'process_offer',
          session_id: this.sessionId,
          offer: {
            sdp: this.peerConnection.localDescription.sdp,
            type: this.peerConnection.localDescription.type
          }
        }));
  
        return this.sessionId;
      } catch (error) {
        console.error('Error setting up peer connection:', error);
        throw error;
      }
    }
  
    /**
     * Xử lý SDP answer từ server
     * @param {Object} answer - SDP answer
     */
    async handleRemoteAnswer(answer) {
      try {
        if (!this.peerConnection) {
          console.error('Peer connection not established');
          return;
        }
  
        const remoteDesc = new RTCSessionDescription(answer);
        await this.peerConnection.setRemoteDescription(remoteDesc);
        console.log('Remote description set successfully');
      } catch (error) {
        console.error('Error handling remote answer:', error);
        if (this.callbacks.onError) {
          this.callbacks.onError('Lỗi khi thiết lập kết nối');
        }
      }
    }
  
    /**
     * Thiết lập ngôn ngữ cho phiên dịch thuật
     * @param {string} sourceLang - Ngôn ngữ nguồn
     * @param {string} targetLang - Ngôn ngữ đích
     */
    setLanguages(sourceLang, targetLang) {
      if (!this.sessionId || !this.isConnected) {
        console.error('Cannot set languages: No active session or connection');
        return;
      }
  
      this.websocket.send(JSON.stringify({
        action: 'set_languages',
        session_id: this.sessionId,
        source_lang: sourceLang,
        target_lang: targetLang
      }));
    }
  
    /**
     * Kết thúc cuộc gọi và dọn dẹp tài nguyên
     */
    endCall() {
      // Đóng kết nối WebRTC
      if (this.peerConnection) {
        this.peerConnection.close();
        this.peerConnection = null;
      }
  
      // Dừng luồng media cục bộ
      if (this.localStream) {
        this.localStream.getTracks().forEach(track => track.stop());
        this.localStream = null;
      }
  
      // Gửi thông báo đóng phiên
      if (this.sessionId && this.isConnected) {
        this.websocket.send(JSON.stringify({
          action: 'close_session',
          session_id: this.sessionId
        }));
      }
  
      // Reset các biến
      this.remoteStream = null;
      this.sessionId = null;
  
      // Gọi callback
      if (this.callbacks.onCallEnded) {
        this.callbacks.onCallEnded();
      }
    }
  
    /**
     * Đăng ký callback
     * @param {string} eventName - Tên sự kiện
     * @param {Function} callback - Hàm callback
     */
    on(eventName, callback) {
      if (this.callbacks.hasOwnProperty(eventName)) {
        this.callbacks[eventName] = callback;
      } else {
        console.error(`Unknown event: ${eventName}`);
      }
    }
  
    /**
     * Đóng kết nối và dọn dẹp tài nguyên
     */
    disconnect() {
      this.endCall();
      
      if (this.websocket && this.isConnected) {
        this.websocket.close();
      }
      
      this.websocket = null;
      this.isConnected = false;
    }
  }
  
  export default WebRTCService;