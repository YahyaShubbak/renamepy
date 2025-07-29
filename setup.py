#!/usr/bin/env python3
"""
Setup script for RenameFiles - Advanced Photo Renaming Tool
"""

from setuptools import setup, find_packages
import os

# Read README for long description
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()

# Read requirements
def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="renamepy",
    version="1.0.0",
    author="Yahya Shubbak",
    author_email="",  # Add your email if desired
    description="A powerful PyQt6 application for batch renaming image files with EXIF data integration",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/YahyaShubbak/renamepy",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Graphics",
        "Topic :: System :: Filesystems",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Environment :: X11 Applications :: Qt",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.900",
        ],
    },
    entry_points={
        "console_scripts": [
            "renamepy=RenameFiles:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.ico", "*.png", "*.md", "*.txt"],
    },
    keywords="photo rename exif batch image metadata camera lens",
    project_urls={
        "Bug Reports": "https://github.com/YahyaShubbak/renamepy/issues",
        "Source": "https://github.com/YahyaShubbak/renamepy",
        "Documentation": "https://github.com/YahyaShubbak/renamepy#readme",
    },
)
