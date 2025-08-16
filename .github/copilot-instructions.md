<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

# Newspaper Summary Project

This is a Python Flask web application for processing newspaper PDFs with the following workflow:

1. PDF Upload and Splitting - Split multi-page PDFs into individual page files
2. OCR Processing - Convert non-text PDFs to text-readable format using Tesseract
3. PDF Merging - Combine processed pages back into a single PDF
4. Text Extraction - Extract text content from processed PDFs
5. Vector Database Storage - Store text chunks in ChromaDB for RAG
6. AI Summarization - Use OpenAI GPT for intelligent document summarization

## Key Technologies:
- Flask for web framework with WebSocket support for real-time progress
- PyPDF2/pypdf for PDF manipulation
- Tesseract OCR for text extraction from images
- ChromaDB for vector database
- OpenAI API for summarization
- Bootstrap for responsive UI

## Project Structure:
- `app.py` - Main Flask application
- `pdf_processor.py` - PDF splitting, OCR, and merging logic
- `rag_system.py` - Vector database and RAG implementation
- `templates/` - HTML templates
- `static/` - CSS, JS, and other static files
- `uploads/` - User uploaded files
- `temp/` - Temporary processing files
- `processed/` - Final processed files