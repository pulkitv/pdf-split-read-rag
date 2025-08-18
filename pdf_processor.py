import os
import tempfile
from pypdf import PdfReader, PdfWriter
from pdf2image.pdf2image import convert_from_path
import pytesseract
from PIL import Image
import io
import subprocess
import platform
import warnings
import shutil

class PDFProcessor:
    def __init__(self, upload_folder, temp_folder, processed_folder):
        self.upload_folder = upload_folder
        self.temp_folder = temp_folder
        self.processed_folder = processed_folder
        
        # Load environment configuration
        self.ocr_dpi = int(os.getenv('OCR_DPI', 150))  # Reduced from 200 to 150 for smaller images
        self.ocr_max_dimension = int(os.getenv('OCR_MAX_DIMENSION', 1500))  # Reduced from 2000 to 1500
        self.ocr_batch_size = int(os.getenv('OCR_BATCH_SIZE', 5))
        self.ocr_jpeg_quality = int(os.getenv('OCR_JPEG_QUALITY', 85))
        self.pdf_merge_batch_size = int(os.getenv('PDF_MERGE_BATCH_SIZE', 10))
        self.gc_threshold = int(os.getenv('PYTHON_GC_THRESHOLD', 5))
        
        # Tesseract configuration from environment
        self.tesseract_lang = os.getenv('TESSERACT_LANG', 'eng')
        self.tesseract_oem = os.getenv('TESSERACT_OEM', '3')
        self.tesseract_psm = os.getenv('TESSERACT_PSM', '6')
        
        # Configure PIL to handle large images safely
        Image.MAX_IMAGE_PIXELS = 200000000  # Allow up to 200M pixels
        warnings.filterwarnings("ignore", category=Image.DecompressionBombWarning)
        
        # Ensure Tesseract is available
        self._setup_tesseract()
    
    def _setup_tesseract(self):
        """Setup Tesseract OCR based on the operating system"""
        system = platform.system().lower()
        
        # Check for environment-specific Tesseract paths first
        tesseract_cmd = None
        if system == "darwin":
            tesseract_cmd = os.getenv('TESSERACT_CMD_MACOS')
        elif system == "linux":
            tesseract_cmd = os.getenv('TESSERACT_CMD_LINUX')
        elif system == "windows":
            tesseract_cmd = os.getenv('TESSERACT_CMD_WINDOWS')
        
        if tesseract_cmd and os.path.exists(tesseract_cmd):
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            return
        
        # Fallback to auto-detection
        if system == "darwin":  # macOS
            possible_paths = [
                "/usr/local/bin/tesseract",
                "/opt/homebrew/bin/tesseract",
                "/usr/bin/tesseract"
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    break
            else:
                print("Warning: Tesseract not found. Please install with: brew install tesseract")
        
        elif system == "linux":
            try:
                subprocess.run(["tesseract", "--version"], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                print("Warning: Tesseract not found. Please install with: sudo apt-get install tesseract-ocr")
        
        elif system == "windows":
            tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(tesseract_path):
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
            else:
                print("Warning: Tesseract not found. Please install from: https://github.com/UB-Mannheim/tesseract/wiki")
    
    def split_pdf(self, pdf_path, session_id, progress_callback=None):
        """Split PDF into individual page files"""
        split_files = []
        
        try:
            reader = PdfReader(pdf_path)
            total_pages = len(reader.pages)
            
            # Create session-specific temp directory
            session_temp_dir = os.path.join(self.temp_folder, session_id)
            os.makedirs(session_temp_dir, exist_ok=True)
            
            for page_num in range(total_pages):
                # Create a new PDF writer for each page
                writer = PdfWriter()
                writer.add_page(reader.pages[page_num])
                
                # Save individual page as PDF
                page_filename = f"page_{page_num + 1:03d}.pdf"
                page_path = os.path.join(session_temp_dir, page_filename)
                
                with open(page_path, 'wb') as output_file:
                    writer.write(output_file)
                
                split_files.append(page_path)
                
                # Update progress
                progress = int((page_num + 1) / total_pages * 100)
                if progress_callback:
                    progress_callback(progress)
            
            return split_files
            
        except Exception as e:
            raise Exception(f"Error splitting PDF: {str(e)}")
    
    def process_ocr(self, pdf_files, session_id, progress_callback=None):
        """Convert PDFs to text-searchable format using OCR - optimized for large files"""
        ocr_files = []
        total_files = len(pdf_files)
        
        try:
            for i, pdf_file in enumerate(pdf_files):
                # Calculate base progress for this page
                base_progress = int(i / total_files * 100)
                page_progress_increment = int(100 / total_files)
                
                # Sub-step 1: Converting PDF to image (0-20% of page progress)
                if progress_callback:
                    current_progress = base_progress + int(page_progress_increment * 0.1)
                    progress_callback(current_progress)
                
                print(f"Converting page {i+1}/{total_files} to image...")
                images = convert_from_path(
                    pdf_file, 
                    dpi=self.ocr_dpi,
                    first_page=1,
                    last_page=1,
                    thread_count=1,
                    fmt='jpeg',
                    jpegopt={
                        "quality": 75,
                        "progressive": True, 
                        "optimize": True
                    }
                )
                
                if images:
                    image = images[0]
                    
                    # Sub-step 2: Resizing image (20-40% of page progress)
                    if progress_callback:
                        current_progress = base_progress + int(page_progress_increment * 0.3)
                        progress_callback(current_progress)
                    
                    original_size = max(image.size)
                    if original_size > self.ocr_max_dimension:
                        ratio = self.ocr_max_dimension / original_size
                        new_width = int(image.size[0] * ratio)
                        new_height = int(image.size[1] * ratio)
                        new_size = (new_width, new_height)
                        
                        print(f"Resizing page {i+1}/{total_files}: {image.size} → {new_size}")
                        image = image.resize(new_size, Image.Resampling.LANCZOS)
                    
                    # Convert to RGB if necessary
                    if image.mode != 'RGB':
                        image = image.convert('RGB')
                    
                    # Sub-step 3: Running OCR (40-80% of page progress)
                    if progress_callback:
                        current_progress = base_progress + int(page_progress_increment * 0.6)
                        progress_callback(current_progress)
                    
                    custom_config = f'--oem {self.tesseract_oem} --psm {self.tesseract_psm}'
                    
                    try:
                        print(f"Running OCR on page {i+1}/{total_files}...")
                        ocr_text = pytesseract.image_to_string(
                            image, 
                            lang=self.tesseract_lang, 
                            config=custom_config
                        )
                        
                        # Sub-step 4: Creating searchable PDF (80-95% of page progress)
                        if progress_callback:
                            current_progress = base_progress + int(page_progress_increment * 0.9)
                            progress_callback(current_progress)
                        
                        print(f"Creating searchable PDF for page {i+1}/{total_files}...")
                        ocr_pdf_path = self._create_searchable_pdf(image, ocr_text, pdf_file)
                        ocr_files.append(ocr_pdf_path)
                        print(f"Completed OCR for page {i+1}/{total_files}")
                        
                    except Exception as ocr_error:
                        print(f"OCR failed for {pdf_file}: {str(ocr_error)}")
                        ocr_files.append(pdf_file)
                else:
                    ocr_files.append(pdf_file)
                
                # Clean up memory
                if 'image' in locals():
                    del image
                if 'images' in locals():
                    del images
                
                # Final progress for this page (100% of page progress)
                final_progress = int((i + 1) / total_files * 100)
                if progress_callback:
                    progress_callback(final_progress)
                
                # Memory cleanup
                if i % self.gc_threshold == 0:
                    import gc
                    gc.collect()
            
            return ocr_files
            
        except Exception as e:
            raise Exception(f"Error during OCR processing: {str(e)}")
    
    def _create_searchable_pdf(self, image, ocr_text, original_pdf_path):
        """Create a searchable PDF with OCR text overlay"""
        try:
            # Create OCR version filename
            ocr_filename = original_pdf_path.replace('.pdf', '_ocr.pdf')
            
            # Get image data for PDF creation
            img_data = pytesseract.image_to_pdf_or_hocr(image, extension='pdf')
            
            with open(ocr_filename, 'wb') as f:
                if isinstance(img_data, (bytes, bytearray, memoryview)):
                    f.write(img_data)
                else:
                    # Handle string case
                    f.write(str(img_data).encode('utf-8'))
            
            return ocr_filename
            
        except Exception as e:
            print(f"Warning: Could not create searchable PDF for {original_pdf_path}: {str(e)}")
            # Return original file if OCR overlay fails
            return original_pdf_path
    
    def merge_pdfs(self, pdf_files, session_id, progress_callback=None):
        """Merge individual PDF files back into a single PDF - optimized for large files"""
        try:
            merger = PdfWriter()
            total_files = len(pdf_files)
            
            pdf_files.sort()
            
            # Use environment-configured batch size
            for batch_start in range(0, total_files, self.pdf_merge_batch_size):
                batch_end = min(batch_start + self.pdf_merge_batch_size, total_files)
                batch_files = pdf_files[batch_start:batch_end]
                
                for i, pdf_file in enumerate(batch_files):
                    try:
                        reader = PdfReader(pdf_file)
                        
                        for page in reader.pages:
                            merger.add_page(page)
                        
                        current_file = batch_start + i + 1
                        progress = int(current_file / total_files * 100)
                        if progress_callback:
                            progress_callback(progress)
                            
                    except Exception as e:
                        print(f"Warning: Could not process file {pdf_file}: {str(e)}")
                        continue
                
                # Memory cleanup
                import gc
                gc.collect()
            
            merged_filename = f"merged_document_{session_id}.pdf"
            merged_path = os.path.join(self.processed_folder, merged_filename)
            
            with open(merged_path, 'wb') as output_file:
                merger.write(output_file)
            
            merger.close()
            return merged_path
            
        except Exception as e:
            raise Exception(f"Error merging PDFs: {str(e)}")
    
    def extract_text_from_pdfs(self, pdf_files):
        """Extract text from a list of PDF files (typically single-page PDFs). Returns list[{'file','content'}]."""
        results = []
        try:
            # Keep original order
            for pdf_path in pdf_files:
                try:
                    reader = PdfReader(pdf_path)
                    page_texts = []
                    for page in reader.pages:
                        text = page.extract_text() or ""
                        # Normalize whitespace
                        text = " ".join(text.split())
                        page_texts.append(text)
                    combined = "\n\n".join([t for t in page_texts if t])
                    results.append({
                        'file': os.path.basename(pdf_path),
                        'content': combined
                    })
                except Exception as e:
                    print(f"Warning: Failed to extract text from {pdf_path}: {e}")
                    results.append({
                        'file': os.path.basename(pdf_path),
                        'content': ""
                    })
            return results
        except Exception as e:
            raise Exception(f"Error extracting text from PDFs: {str(e)}")
    
    def extract_text_from_single_pdf(self, pdf_path, progress_callback=None):
        """Extract text from a single multi-page PDF. Returns a single concatenated string.
        Progress callback (if provided) will be called with 0-50 to align with UI expectations.
        """
        try:
            reader = PdfReader(pdf_path)
            total_pages = len(reader.pages) or 1
            texts = []
            for i, page in enumerate(reader.pages):
                try:
                    text = page.extract_text() or ""
                except Exception as e:
                    print(f"Warning: Text extraction failed on page {i+1}: {e}")
                    text = ""
                texts.append(text)
                if progress_callback:
                    progress = int(((i + 1) / total_pages) * 50)
                    progress_callback(progress)
            # Normalize and join
            joined = "\n\n".join([" ".join(t.split()) for t in texts if t])
            return joined
        except Exception as e:
            raise Exception(f"Error extracting text from PDF: {str(e)}")
    
    def cleanup_temp_files(self, session_id):
        """Remove temporary files for a session (split pages and OCR outputs)."""
        try:
            session_temp_dir = os.path.join(self.temp_folder, session_id)
            if os.path.isdir(session_temp_dir):
                shutil.rmtree(session_temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"Warning: Failed to clean up temp files for session {session_id}: {e}")