# Newspaper Summary - PDF Processing & AI Summarization

A comprehensive web application for processing Economic Times newspaper PDFs with AI-powered summarization and voiceover generation capabilities.

## Features

🔄 **Dual Processing Modes**
- **OCR Processing**: For scanned PDFs that need text extraction via Tesseract OCR
- **Direct Upload**: For text-readable PDFs (faster processing, direct to AI summary)
- Split multi-page PDFs into individual page files
- Merge processed pages back into a single searchable PDF
- Real-time progress tracking for all operations

🤖 **AI-Powered Summarization**
- Extract text from processed PDFs
- Store content in ChromaDB vector database
- RAG (Retrieval-Augmented Generation) implementation
- OpenAI GPT integration for intelligent summarization
- Customizable prompts for different analysis needs

🎤 **AI Voiceover Generation** (NEW!)
- **Standalone Voiceover Creator**: Generate AI voiceovers without uploading PDFs
- **Summary-to-Voice**: Convert AI-generated summaries to professional voiceovers
- **Custom Text-to-Voice**: Create voiceovers from any text content
- **6 Voice Options**: Choose from Alloy, Echo, Fable, Onyx, Nova, and Shimmer
- **Speed Control**: Adjustable speech speed (0.7x to 1.5x)
- **Multiple Formats**: Generate MP3 audio, WAV audio, or MP4 video with waveforms
- **High-Quality TTS**: Powered by OpenAI's advanced text-to-speech models

🌐 **Modern Web Interface**
- Responsive Bootstrap UI
- Drag-and-drop file upload
- Real-time WebSocket progress updates
- Mobile-friendly design
- Collapsible panels for enhanced UX

## Prerequisites

### System Requirements
- Python 3.8 or higher
- Tesseract OCR engine (for OCR processing mode)
- FFmpeg (for video generation)

### Install Dependencies

**FFmpeg (required for video generation):**
```bash
# macOS (using Homebrew)
brew install ffmpeg

# Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg

# Windows
# Download from: https://ffmpeg.org/download.html
```

**Tesseract OCR (for OCR processing mode):**
```bash
# macOS (using Homebrew)
brew install tesseract

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install tesseract-ocr

# Windows
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
```

## Installation

1. **Clone the repository:**
```bash
git clone https://github.com/pulkitv/pdf-split-read-rag.git
cd pdf-split-read-rag
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
SECRET_KEY=your_secret_key_here
```

4. **Create required directories:**
```bash
mkdir -p uploads temp processed chroma_db voiceovers
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

### Standalone AI Voiceover (New Feature!)

**Create voiceovers without uploading any PDFs:**
1. On the homepage, click "Create Voiceover Now"
2. Enter any text content (news summaries, announcements, etc.)
3. Choose voice type, speed, and output format
4. Generate and download professional AI voiceovers
5. Perfect for content creators, accessibility, and quick announcements

### PDF Processing Modes

#### OCR Processing Mode
For scanned PDFs that need text extraction:
1. Select "OCR Processing" mode
2. Upload PDF and click "Start Processing"
3. Monitor progress through 4 steps: Splitting → OCR → Merging → Vector DB
4. Download the searchable PDF
5. Generate AI summary and convert to voiceover

#### Direct Upload Mode  
For text-readable PDFs (faster processing):
1. Select "Direct Upload" mode
2. Upload PDF and click "Start Processing"
3. Monitor progress: Text Extraction & Vector DB Creation
4. Generate AI summary and convert to voiceover

### AI Voiceover Options

#### From Document Summary
1. Process a PDF and generate AI summary
2. Click "Generate AI Voiceover"
3. Choose "Summary to Voice" mode
4. Customize voice settings and generate

#### Custom Text Input
1. In any voiceover section, select "Custom Text to Voice"
2. Enter your own text content
3. Customize voice settings and generate

### Voice Customization Options

- **Voice Types**: Alloy (Neutral), Echo (Deep), Fable (Expressive), Onyx (Professional), Nova (Clear), Shimmer (Warm)
- **Speed Settings**: 0.7x (Slow), 1.0x (Normal), 1.2x (Fast), 1.5x (Very Fast)
- **Output Formats**: 
  - MP3 Audio (standard audio file)
  - WAV Audio (high-quality uncompressed)
  - MP4 Video (with waveform visualization and text overlay)

### Custom Prompts

You can customize the AI summarization by providing specific instructions, such as:
- "Focus on market analysis and stock movements"
- "Summarize policy announcements and their economic impact"
- "Extract key business deals and corporate news"

## Project Structure

```
pdf-split-read-rag/
├── app.py                 # Main Flask application with voiceover endpoints
├── pdf_processor.py       # PDF manipulation and OCR logic
├── rag_system.py         # Vector database and AI integration
├── voiceover_system.py   # AI text-to-speech and video generation
├── requirements.txt      # Python dependencies
├── .env.template        # Environment variables template
├── .gitignore           # Git ignore file
├── templates/
│   └── index.html       # Main web interface with voiceover UI
├── static/
│   ├── app.js          # Frontend JavaScript with voiceover logic
│   └── style.css       # Custom styling including voiceover components
├── uploads/            # User uploaded files
├── temp/              # Temporary processing files
├── processed/         # Final processed PDFs
├── voiceovers/        # Generated voiceover files
└── chroma_db/         # Vector database storage
```

## API Endpoints

- `GET /` - Main web interface
- `POST /upload` - Upload PDF file
- `GET /process/<session_id>` - Start processing pipeline
- `GET /download/<session_id>` - Download processed PDF
- `POST /summarize/<session_id>` - Generate AI summary
- `POST /generate-voiceover/<session_id>` - Generate AI voiceover (supports 'standalone' for independent usage)
- `GET /download-voiceover/<filename>` - Download generated voiceover file
- `GET /status/<session_id>` - Get processing status

## Technologies Used

- **Backend**: Flask, Flask-SocketIO, Python
- **PDF Processing**: PyPDF, pdf2image, Tesseract OCR
- **AI/ML**: OpenAI GPT, OpenAI TTS, LangChain, ChromaDB
- **Media Processing**: FFmpeg for audio/video conversion
- **Frontend**: Bootstrap 5, JavaScript, WebSocket
- **Real-time Updates**: Socket.IO
- **File Handling**: Werkzeug, UUID for session management

## Configuration

### Key Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key for summarization and TTS | - | ✅ |
| `SECRET_KEY` | Flask secret key for sessions | - | ✅ |
| `FLASK_DEBUG` | Enable debug mode | true | ❌ |
| `FLASK_PORT` | Server port | 5000 | ❌ |
| `MAX_FILE_SIZE_MB` | Max file upload size | 50 | ❌ |
| `OCR_DPI` | OCR image resolution | 150 | ❌ |
| `OPENAI_MODEL` | GPT model to use | gpt-3.5-turbo-16k | ❌ |
| `TEXT_CHUNK_SIZE` | Vector DB chunk size | 1000 | ❌ |
| `VOICEOVER_FOLDER` | Voiceover output directory | voiceovers | ❌ |
| `VIDEO_WIDTH` | Video output width | 1920 | ❌ |
| `VIDEO_HEIGHT` | Video output height | 1080 | ❌ |

### File Limits

- Maximum PDF file size: 50MB
- Supported format: PDF only
- Recommended: 15-20 pages for optimal processing time
- Text length for voiceover: No strict limit (OpenAI TTS handles up to ~4096 characters efficiently)

## Troubleshooting

### Common Issues

1. **Tesseract not found error:**
   - Ensure Tesseract is properly installed
   - Check the path configuration in `pdf_processor.py`

2. **FFmpeg not found error:**
   - Install FFmpeg using the system package manager
   - Ensure it's available in your system PATH

3. **OpenAI API errors:**
   - Verify your API key is correct in `.env`
   - Check your OpenAI account has sufficient credits
   - Ensure you have access to both GPT and TTS APIs

4. **Memory issues with large PDFs:**
   - Process smaller files or increase system memory
   - Consider splitting very large documents

5. **WebSocket connection issues:**
   - Check firewall settings
   - Ensure port 5000 is available

6. **"No module named" errors:**
   - Ensure all dependencies are installed: `pip install -r requirements.txt`
   - Consider using a virtual environment

7. **Voiceover generation fails:**
   - Check FFmpeg installation
   - Verify OpenAI API key has TTS access
   - Ensure sufficient disk space in voiceovers folder

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
3. **Voiceover Features**: Update `voiceover_system.py`
4. **Web Interface**: Update templates and static files
5. **API Endpoints**: Add routes in `app.py`

### Testing

Test with sample Economic Times PDFs and various text inputs to ensure all features work correctly.

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly with both PDF processing and standalone voiceover features
5. Submit a pull request

## Recent Updates (v2.0)

### New Features
- **Standalone AI Voiceover Generator**: Create professional voiceovers without PDF processing
- **Enhanced Voice Options**: 6 different voice personalities with speed control
- **Multiple Output Formats**: MP3 audio, WAV audio, and MP4 video with waveform visualization
- **Improved UI/UX**: Collapsible panels and better organization
- **Video Generation**: Automatic creation of MP4 videos with audio waveforms and text overlays

### Technical Improvements
- **FFmpeg Integration**: Professional audio/video processing capabilities
- **Session Management**: Better handling of standalone vs. document-based workflows
- **Error Handling**: Enhanced error messages and fallback mechanisms
- **Performance**: Optimized processing for both small and large text inputs

## License

This project is for educational and research purposes.

## Support

For issues and questions:
- Check the troubleshooting section
- Review code comments for implementation details
- Open an issue on the GitHub repository

---

**Perfect for:** News organizations, content creators, accessibility applications, educational institutions, and anyone needing AI-powered document processing with professional voiceover capabilities.