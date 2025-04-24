# Hệ Thống Dịch Thuật

Một hệ thống dịch thuật toàn diện hỗ trợ dịch giọng nói sang giọng nói, văn bản sang văn bản và các chế độ hỗn hợp với khả năng nhận thức ngữ cảnh.

## Tính Năng

- **Nhận Dạng Giọng Nói (ASR)**: Chuyển đổi ngôn ngữ nói thành văn bản
- **Dịch Máy**: Dịch văn bản giữa nhiều ngôn ngữ khác nhau
- **Chuyển Văn Bản Thành Giọng Nói (TTS)**: Chuyển đổi văn bản thành giọng nói tự nhiên
- **Quản Lý Ngữ Cảnh**: Nâng cao chất lượng dịch thuật với các ngữ cảnh chuyên ngành
- **Dịch Thuật Trực Tuyến**: Dịch thuật giọng nói sang giọng nói theo thời gian thực
- **Nhiều Giao Diện**: Giao diện dòng lệnh (CLI) và API để linh hoạt trong sử dụng

## Cài Đặt

### Sử Dụng Docker (Khuyến nghị)

```bash
# Sao chép repository
git clone https://github.com/tendangnhap/he_thong_dich_thuat.git
cd he_thong_dich_thuat

# Khởi động các dịch vụ
docker-compose up -d
```

### Cài Đặt Thủ Công

```bash
# Sao chép repository
git clone https://github.com/tendangnhap/he_thong_dich_thuat.git
cd he_thong_dich_thuat

# Tạo môi trường ảo
python -m venv venv
source venv/bin/activate  # Trên Windows: venv\Scripts\activate

# Cài đặt các gói phụ thuộc
pip install -r requirements.txt

# Cài đặt gói
pip install -e .
```

## Cấu Hình

Hệ thống được cấu hình thông qua tệp JSON. Mặc định, nó tìm kiếm `config.json` trong thư mục hiện tại. Bạn có thể chỉ định tệp cấu hình thay thế bằng tham số `--config`.

Ví dụ cấu hình cơ bản:

```json
{
  "version": "1.0.0",
  "audio": {
    "sample_rate": 16000,
    "channels": 1
  },
  "models": {
    "asr": {
      "default": "whisper-large-v3",
      "languages": ["vi", "en", "fr", "de", "zh"]
    },
    "translation": {
      "default": "nllb-600M",
      "languages": ["vi", "en", "fr", "de", "zh"]
    },
    "tts": {
      "default": "piper-tts",
      "voices": {
        "vi": "vi-vn-northern-female",
        "en": "en-us-neural-female",
        "fr": "fr-fr-neural-female"
      }
    }
  }
}
```

## Sử Dụng

### Giao Diện Dòng Lệnh (CLI)

Khởi động giao diện dòng lệnh:

```bash
python -m app.main --source vi --target en
```

Các lệnh cơ bản:

- `translate <văn bản>`: Dịch văn bản
- `record [thời_gian]`: Ghi âm và chuyển thành văn bản
- `speak <văn bản>`: Chuyển văn bản thành giọng nói
- `stream`: Bật/tắt chế độ dịch thuật trực tuyến
- `context create <tên>`: Tạo ngữ cảnh mới
- `help`: Hiển thị danh sách lệnh

### API

Khởi động API:

```bash
python -m app.main --mode api --port 5000
```

Ví dụ sử dụng API:

```bash
# Dịch văn bản
curl -X POST "http://localhost:5000/translate" \
  -H "Content-Type: application/json" \
  -d '{"text":"Xin chào thế giới","source":"vi","target":"en"}'
```

## Giấy Phép

Phần mềm này được phân phối theo giấy phép MIT. Xem tệp `LICENSE` để biết thêm chi tiết. 
