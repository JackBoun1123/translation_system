"""
Điểm khởi chạy chính cho ứng dụng dịch thuật theo thời gian thực
"""
import argparse
import logging
import sys
from app.config import API_CONFIG
from app.views.cli_view import run_cli
from app.views.api_view import run_api

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Hệ thống dịch thuật video call theo thời gian thực')
    parser.add_argument('--mode', type=str, choices=['cli', 'api'], default='cli',
                        help='Chế độ chạy: cli - dòng lệnh, api - REST API')
    parser.add_argument('--source-lang', type=str, default='vi',
                        help='Mã ngôn ngữ nguồn')
    parser.add_argument('--target-lang', type=str, default='en',
                        help='Mã ngôn ngữ đích')
    parser.add_argument('--context-file', type=str, default=None,
                        help='Đường dẫn đến file ngữ cảnh')
    parser.add_argument('--input-audio', type=str, default=None,
                        help='Đường dẫn đến file âm thanh đầu vào (cho chế độ CLI)')
    parser.add_argument('--port', type=int, default=API_CONFIG['port'],
                        help=f'Cổng cho API (mặc định: {API_CONFIG["port"]})')
    
    args = parser.parse_args()
    
    logger.info(f"Khởi chạy ứng dụng trong chế độ: {args.mode}")
    
    if args.mode == 'cli':
        run_cli(
            source_lang=args.source_lang,
            target_lang=args.target_lang,
            context_file=args.context_file,
            input_audio=args.input_audio
        )
    else:
        run_api(port=args.port)

if __name__ == "__main__":
    main() 
