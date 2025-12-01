"""
PDF text extraction utilities
"""

import io
from typing import Optional
from pypdf import PdfReader


class PDFExtractor:
    """Extract text from PDF files"""
    
    @staticmethod
    def extract_text(pdf_bytes: bytes) -> str:
        """
        Extract text from PDF bytes
        
        Args:
            pdf_bytes: PDF file as bytes
            
        Returns:
            Extracted text content
        """
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)
            
            text_parts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            return "\n\n".join(text_parts)
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")
    
    @staticmethod
    def extract_text_from_file(file_path: str) -> str:
        """
        Extract text from PDF file path
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Extracted text content
        """
        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()
        return PDFExtractor.extract_text(pdf_bytes)


