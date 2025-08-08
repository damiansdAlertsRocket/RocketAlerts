# setup.py
from setuptools import setup, find_packages

setup(
    name='tvdatafeed',
    version='1.0.2',
    description='TradingView data downloader with session support (fork with cookies)',
    author='backtestingtv (modified by daminosz)',
    author_email='example@example.com',
    packages=find_packages(),
    install_requires=[
        'pandas>=1.0',
        'requests>=2.0',
        'lxml>=4.0',
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
)
