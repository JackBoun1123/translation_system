"""
Script cài đặt cho hệ thống dịch thuật.
"""

from setuptools import setup, find_packages
import os
import re

# Lấy thông tin phiên bản từ __init__.py
with open(os.path.join('app', '__init__.py'), encoding='utf-8') as f:
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", f.read(), re.M)
    if version_match:
        version = version_match.group(1)
    else:
        version = '0.1.0'  # Phiên bản mặc định nếu không tìm thấy

# Đọc tệp README.md
with open('README.md', encoding='utf-8') as f:
    long_description = f.read()

# Đọc danh sách các gói phụ thuộc
with open('requirements.txt', encoding='utf-8') as f:
    requirements = f.read().splitlines()

setup(
    name="he_thong_dich_thuat",
    version=version,
    author="Nhóm Phát Triển",
    author_email="nhom@example.com",
    description="Hệ thống dịch thuật đa ngôn ngữ với ASR, MT và TTS",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tendangnhap/he_thong_dich_thuat",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Text Processing :: Linguistic",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'dich_thuat=app.main:main',
        ],
    },
    include_package_data=True,
    package_data={
        '': ['*.json', '*.yml', '*.yaml'],
    },
    zip_safe=False,
) 
