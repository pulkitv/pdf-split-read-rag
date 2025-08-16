import os
import chromadb
from chromadb.config import Settings
from openai import OpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
import numpy as np
from typing import List, Dict, Optional, Any
import time
import tiktoken

class RAGSystem:
    def __init__(self):
        self.chroma_client: Optional[Any] = None
        self.openai_client = None
        self.collections = {}
        
        # Load environment configuration for text chunking
        chunk_size = int(os.getenv('TEXT_CHUNK_SIZE', 1000))
        chunk_overlap = int(os.getenv('TEXT_CHUNK_OVERLAP', 200))
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        
        # Load OpenAI configuration from environment - use 16k model by default
        self.openai_model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo-16k')
        self.openai_max_tokens = int(os.getenv('OPENAI_MAX_TOKENS', 2000))
        self.openai_temperature = float(os.getenv('OPENAI_TEMPERATURE', 0))
        
        # Token counting setup
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.openai_model)
        except:
            # Fallback to a common tokenizer if model-specific one isn't available
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Calculate safe context limits
        if "16k" in self.openai_model:
            self.max_context_tokens = 16385
        elif "gpt-4" in self.openai_model:
            self.max_context_tokens = 8192
        else:
            self.max_context_tokens = 4097
            
        # Reserve tokens for system prompt, user prompt structure, and response
        self.reserved_tokens = 1000 + self.openai_max_tokens
        self.max_content_tokens = self.max_context_tokens - self.reserved_tokens
        
        # Vector database configuration
        self.vector_batch_size = int(os.getenv('VECTOR_BATCH_SIZE', 100))
        self.chroma_db_path = os.getenv('CHROMA_DB_PATH', 'chroma_db')
        
        # Initialize OpenAI
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            self.openai_client = OpenAI(api_key=api_key)
        
        # Initialize ChromaDB
        self._setup_chromadb()
    
    def _setup_chromadb(self):
        """Initialize ChromaDB client"""
        try:
            # Create ChromaDB directory using environment path
            db_path = os.path.join(os.getcwd(), self.chroma_db_path)
            os.makedirs(db_path, exist_ok=True)
            
            # Initialize ChromaDB client
            self.chroma_client = chromadb.PersistentClient(
                path=db_path,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
        except Exception as e:
            print(f"Error setting up ChromaDB: {str(e)}")
            raise
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using the model's tokenizer"""
        try:
            return len(self.tokenizer.encode(text))
        except:
            # Fallback: rough estimate of 4 characters per token
            return len(text) // 4
    
    def truncate_to_token_limit(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit"""
        current_tokens = self.count_tokens(text)
        if current_tokens <= max_tokens:
            return text
            
        # Binary search to find the right length
        start, end = 0, len(text)
        while start < end:
            mid = (start + end + 1) // 2
            test_text = text[:mid]
            if self.count_tokens(test_text) <= max_tokens:
                start = mid
            else:
                end = mid - 1
                
        return text[:start] + "\n\n[Content truncated due to length...]"

    def create_vector_db(self, text_data: List[Dict], session_id: str, progress_callback=None):
        """Create vector database from extracted text"""
        if not self.chroma_client:
            raise Exception("ChromaDB client not initialized")
            
        try:
            collection_name = f"documents_{session_id}"
            
            # Delete existing collection if it exists
            try:
                self.chroma_client.delete_collection(collection_name)
            except:
                pass
            
            # Create new collection
            collection = self.chroma_client.create_collection(
                name=collection_name,
                metadata={"description": f"Document collection for session {session_id}"}
            )
            
            # Process each page's text
            all_chunks = []
            all_metadatas = []
            all_ids = []
            
            total_pages = len(text_data)
            
            for page_idx, page_data in enumerate(text_data):
                content = page_data['content']
                filename = page_data['file']
                
                # Split text into chunks using environment configuration
                chunks = self.text_splitter.split_text(content)
                
                for chunk_idx, chunk in enumerate(chunks):
                    if chunk.strip():  # Only add non-empty chunks
                        chunk_id = f"{session_id}_{page_idx}_{chunk_idx}"
                        
                        all_chunks.append(chunk)
                        all_metadatas.append({
                            "source": filename,
                            "page_number": page_idx + 1,
                            "chunk_index": chunk_idx,
                            "session_id": session_id
                        })
                        all_ids.append(chunk_id)
                
                # Update progress
                progress = int((page_idx + 1) / total_pages * 100)
                if progress_callback:
                    progress_callback(progress)
            
            # Add documents to collection using environment-configured batch size
            for i in range(0, len(all_chunks), self.vector_batch_size):
                batch_chunks = all_chunks[i:i + self.vector_batch_size]
                batch_metadatas = all_metadatas[i:i + self.vector_batch_size]
                batch_ids = all_ids[i:i + self.vector_batch_size]
                
                collection.add(
                    documents=batch_chunks,
                    metadatas=batch_metadatas,
                    ids=batch_ids
                )
            
            # Store collection reference
            self.collections[session_id] = collection
            
            print(f"Created vector database with {len(all_chunks)} chunks")
            
        except Exception as e:
            raise Exception(f"Error creating vector database: {str(e)}")
    
    def query_documents(self, session_id: str, query: str, n_results: int = 10):
        """Query the vector database for relevant chunks"""
        try:
            if session_id not in self.collections:
                if not self.chroma_client:
                    raise Exception("ChromaDB client not initialized")
                collection_name = f"documents_{session_id}"
                self.collections[session_id] = self.chroma_client.get_collection(collection_name)
            
            collection = self.collections[session_id]
            
            # Query the collection
            results = collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            return results
            
        except Exception as e:
            raise Exception(f"Error querying documents: {str(e)}")
    
    def generate_summary_hierarchical(self, chunks: List[str], system_prompt: str, progress_callback=None) -> str:
        """Generate summary using hierarchical approach for very long documents"""
        if not chunks:
            return "No content to summarize."
            
        # If we have few chunks, process them together
        if len(chunks) <= 3:
            combined_text = "\n\n".join(chunks)
            if self.count_tokens(combined_text) <= self.max_content_tokens:
                return self._generate_single_summary(combined_text, system_prompt)
        
        # For many chunks, use hierarchical summarization
        print(f"Using hierarchical summarization for {len(chunks)} chunks...")
        chunk_summaries = []
        
        # First pass: summarize chunks in groups
        group_size = 3  # Process 3 chunks at a time
        total_groups = (len(chunks) + group_size - 1) // group_size
        
        for i in range(0, len(chunks), group_size):
            group = chunks[i:i + group_size]
            group_text = "\n\n".join(group)
            
            # Truncate if necessary
            group_text = self.truncate_to_token_limit(group_text, self.max_content_tokens)
            
            # Generate summary for this group
            group_summary = self._generate_single_summary(
                group_text, 
                "Summarize the following newspaper content, focusing on key economic and business news:"
            )
            chunk_summaries.append(group_summary)
            
            # Update progress
            if progress_callback:
                progress = int(50 + (i // group_size + 1) / total_groups * 40)
                progress_callback(progress)
        
        # Second pass: combine chunk summaries into final summary
        final_text = "\n\n".join(chunk_summaries)
        final_text = self.truncate_to_token_limit(final_text, self.max_content_tokens)
        
        return self._generate_single_summary(final_text, system_prompt)
    
    def _generate_single_summary(self, content: str, system_prompt: str) -> str:
        """Generate a single summary for the given content"""
        if not self.openai_client:
            raise Exception("OpenAI client not configured. Please set OPENAI_API_KEY environment variable.")
            
        user_prompt = f"Please summarize the following Economic Times newspaper content:\n\n{content}"
        
        # Double-check token count
        total_tokens = (
            self.count_tokens(system_prompt) + 
            self.count_tokens(user_prompt) + 
            self.openai_max_tokens
        )
        
        if total_tokens > self.max_context_tokens:
            # Further truncate content if needed
            available_tokens = self.max_context_tokens - self.count_tokens(system_prompt) - self.openai_max_tokens - 100
            content = self.truncate_to_token_limit(content, available_tokens)
            user_prompt = f"Please summarize the following Economic Times newspaper content:\n\n{content}"
        
        response = self.openai_client.chat.completions.create(
            model=self.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=self.openai_max_tokens,
            temperature=self.openai_temperature
        )
        
        content = response.choices[0].message.content or "No summary generated by AI model."
        return content

    def generate_summary(self, session_id: str, custom_prompt: str = "", progress_callback=None):
        """Generate AI summary using OpenAI and RAG with proper token management"""
        if not self.openai_client:
            raise Exception("OpenAI client not configured. Please set OPENAI_API_KEY environment variable.")
            
        try:
            if progress_callback:
                progress_callback(10)
            
            # Default summarization prompt
            default_prompt = """
           Extract the list of all the companies mentioned in the content. For each company in the list, mention the following context:
           1. Name of the company, Sentiment: Positive/Neutral/Negative (with color dot red/amber/green) of the news related to the company in the content.
           2. 30-50 words summary with fact based context related to the company in the content. The summary should include the logic used to derive the sentiment of the news.
           3. Source of the news, Page number in the newspaper.
           """
            
            # Use custom prompt if provided, otherwise use default
            system_prompt = custom_prompt if custom_prompt.strip() else default_prompt
            
            if progress_callback:
                progress_callback(30)
            
            # Get all document chunks for context
            collection = self.collections.get(session_id)
            if not collection:
                if not self.chroma_client:
                    raise Exception("ChromaDB client not initialized")
                collection_name = f"documents_{session_id}"
                collection = self.chroma_client.get_collection(collection_name)
                self.collections[session_id] = collection
            
            # Get all documents from the collection
            all_docs = collection.get()
            
            if progress_callback:
                progress_callback(50)
            
            # Handle the documents properly
            documents = all_docs.get('documents', [])
            if not documents:
                raise Exception("No documents found in the collection")
            
            # Convert documents to list of strings
            doc_chunks = [str(doc) for doc in documents if doc and str(doc).strip()]
            
            if not doc_chunks:
                raise Exception("No valid document content found")
            
            print(f"Processing {len(doc_chunks)} document chunks...")
            print(f"Using model: {self.openai_model} with max context: {self.max_context_tokens} tokens")
            
            # Calculate total tokens
            total_content = "\n\n".join(doc_chunks)
            total_tokens = self.count_tokens(total_content)
            print(f"Total content tokens: {total_tokens}")
            
            if progress_callback:
                progress_callback(70)
            
            # Choose summarization strategy based on content length
            if total_tokens <= self.max_content_tokens:
                # Content fits in one request
                print("Using single-pass summarization...")
                summary = self._generate_single_summary(total_content, system_prompt)
            else:
                # Use hierarchical summarization
                print("Content too long, using hierarchical summarization...")
                summary = self.generate_summary_hierarchical(doc_chunks, system_prompt, progress_callback)
            
            if progress_callback:
                progress_callback(100)
            
            return summary
            
        except Exception as e:
            print(f"Summarization error: {str(e)}")
            if "api_key" in str(e).lower():
                raise Exception("OpenAI API key not configured. Please set OPENAI_API_KEY environment variable.")
            elif "context_length_exceeded" in str(e).lower():
                raise Exception("Content is too long even for hierarchical processing. Please try with a shorter document.")
            else:
                raise Exception(f"Error generating summary: {str(e)}")
    
    def get_document_stats(self, session_id: str):
        """Get statistics about the document collection"""
        try:
            collection = self.collections.get(session_id)
            if not collection:
                if not self.chroma_client:
                    raise Exception("ChromaDB client not initialized")
                collection_name = f"documents_{session_id}"
                collection = self.chroma_client.get_collection(collection_name)
                self.collections[session_id] = collection
            
            # Get collection info
            count = collection.count()
            
            return {
                "total_chunks": count,
                "collection_name": f"documents_{session_id}",
                "status": "ready"
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "status": "error"
            }
    
    def cleanup_session(self, session_id: str):
        """Clean up vector database for a session"""
        try:
            if not self.chroma_client:
                return
                
            collection_name = f"documents_{session_id}"
            self.chroma_client.delete_collection(collection_name)
            
            if session_id in self.collections:
                del self.collections[session_id]
                
        except Exception as e:
            print(f"Warning: Could not clean up vector database: {str(e)}")
    
    def search_documents(self, session_id: str, search_query: str, max_results: int = 5):
        """Search for specific content in the documents"""
        try:
            results = self.query_documents(session_id, search_query, max_results)
            
            formatted_results = []
            if results and results['documents'] and results['documents'][0]:
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                    
                    formatted_results.append({
                        'content': doc,
                        'source': metadata.get('source', 'Unknown'),
                        'page_number': metadata.get('page_number', 0),
                        'relevance_score': results['distances'][0][i] if results['distances'] else 0
                    })
            
            return formatted_results
            
        except Exception as e:
            raise Exception(f"Error searching documents: {str(e)}")