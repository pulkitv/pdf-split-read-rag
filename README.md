# Newspaper Summary - PDF Processing & AI Summarization

A comprehensive web application for processing Economic Times newspaper PDFs with AI-powered summarization capabilities.

## Features

🔄 **PDF Processing Pipeline**
- Split multi-page PDFs into individual page files
- OCR processing for non-text-readable PDFs using Tesseract
- Merge processed pages back into a single searchable PDF
- Real-time progress tracking for all operations

🤖 **AI-Powered Summarization**
- Extract text from processed PDFs
- Store content in ChromaDB vector database
- RAG (Retrieval-Augmented Generation) implementation
- OpenAI GPT integration for intelligent summarization
- Customizable prompts for different analysis needs

🌐 **Modern Web Interface**
- Responsive Bootstrap UI
- Drag-and-drop file upload
- Real-time WebSocket progress updates
- Mobile-friendly design

## Prerequisites

### System Requirements
- Python 3.8 or higher
- Tesseract OCR engine

### Install Tesseract OCR

**macOS (using Homebrew):**
```bash
brew install tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

**Windows:**
Download and install from: https://github.com/UB-Mannheim/tesseract/wiki

## Installation

1. **Clone or navigate to the project directory:**
```bash
cd /Users/pulkitvashishta/pdf-split-read
```

2. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables:**
```bash
cp .env.template .env
```

Edit the `.env` file and add your OpenAI API key:
```bash
OPENAI_API_KEY=your_actual_openai_api_key_here
```

4. **Create required directories:**
```bash
mkdir -p uploads temp processed chroma_db
```

## Usage

### Starting the Application

1. **Run the Flask application:**
```bash
python app.py
```

2. **Open your web browser and navigate to:**
```
http://localhost:5000
```

### Processing Workflow

1. **Upload PDF**: Drag and drop or browse to select your Economic Times PDF file
2. **Start Processing**: Click "Start Processing" to begin the pipeline
3. **Monitor Progress**: Watch real-time progress for each step:
   - PDF splitting into individual pages
   - OCR processing for text recognition
   - Merging pages back into searchable PDF
   - Creating vector database for RAG
4. **Download Results**: Download the processed, text-searchable PDF
5. **Generate Summary**: Use AI to create intelligent summaries with optional custom prompts

### Custom Prompts

You can customize the AI summarization by providing specific instructions, such as:
- "Focus on market analysis and stock movements"
- "Summarize policy announcements and their economic impact"
- "Extract key business deals and corporate news"

## Project Structure

```
pdf-split-read/
├── app.py                 # Main Flask application
├── pdf_processor.py       # PDF manipulation and OCR logic
├── rag_system.py         # Vector database and AI integration
├── requirements.txt      # Python dependencies
├── .env.template        # Environment variables template
├── .github/
│   └── copilot-instructions.md
├── templates/
│   └── index.html       # Main web interface
├── static/
│   ├── app.js          # Frontend JavaScript
│   └── style.css       # Custom styling
├── uploads/            # User uploaded files
├── temp/              # Temporary processing files
├── processed/         # Final processed PDFs
└── chroma_db/         # Vector database storage
```

## API Endpoints

- `GET /` - Main web interface
- `POST /upload` - Upload PDF file
- `GET /process/<session_id>` - Start processing pipeline
- `GET /download/<session_id>` - Download processed PDF
- `POST /summarize/<session_id>` - Generate AI summary
- `GET /status/<session_id>` - Get processing status

## Technologies Used

- **Backend**: Flask, Flask-SocketIO, Python
- **PDF Processing**: PyPDF, pdf2image, Tesseract OCR
- **AI/ML**: OpenAI GPT, LangChain, ChromaDB
- **Frontend**: Bootstrap 5, JavaScript, WebSocket
- **Real-time Updates**: Socket.IO

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for summarization | Required |
| `FLASK_ENV` | Flask environment | development |
| `FLASK_DEBUG` | Enable debug mode | True |
| `MAX_CONTENT_LENGTH` | Max file upload size | 50MB |

### File Limits

- Maximum PDF file size: 50MB
- Supported format: PDF only
- Recommended: 15-20 pages for optimal processing time

## Troubleshooting

### Common Issues

1. **Tesseract not found error:**
   - Ensure Tesseract is properly installed
   - Check the path configuration in `pdf_processor.py`

2. **OpenAI API errors:**
   - Verify your API key is correct in `.env`
   - Check your OpenAI account has sufficient credits

3. **Memory issues with large PDFs:**
   - Process smaller files or increase system memory
   - Consider splitting very large documents

4. **WebSocket connection issues:**
   - Check firewall settings
   - Ensure port 5000 is available

### Debug Mode

Run the application in debug mode for detailed error messages:
```bash
export FLASK_DEBUG=1
python app.py
```

## Development

### Adding New Features

1. **PDF Processing**: Extend `pdf_processor.py`
2. **AI Features**: Modify `rag_system.py`
3. **Web Interface**: Update templates and static files
4. **API Endpoints**: Add routes in `app.py`

### Testing

Test with sample Economic Times PDFs to ensure all features work correctly.

## License

This project is for educational and research purposes.

## Support

For issues and questions, please check the troubleshooting section or review the code comments for implementation details.