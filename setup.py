'''
To build the package, run:
    pip install --upgrade build && rm dist/* && python -m build

The built package will be in the dist/ directory

To upload the package to PyPI, run:
    pip install --upgrade twine && twine upload dist/*
'''

from setuptools import setup, find_packages
from pathlib import Path

readme = Path(__file__).parent / 'README.md'

setup(
    name='zosedit',
    version='0.0.2',
    description='FTP-based MVS Dataset Editor',
    long_description=readme.read_text(),
    long_description_content_type='text/markdown',
    author='KyleTheScientist',
    author_email='kylethescientist@gmail.com',
    url='https://github.com/KyleTheScientist/zOSEdit',
    packages=find_packages(),
    install_requires=[
        'dearpygui',
    ],
    entry_points={'console_scripts': ['zosedit=zosedit.main:main']},
    keywords=['editor', 'z/OS', 'MVS', 'dataset', 'FTP'],
    classifiers=[
        'Intended Audience :: Developers',
        'Operating System :: Microsoft :: Windows',
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
)
