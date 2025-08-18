import os
import chromadb
from chromadb.config import Settings
from openai import OpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from typing import List, Dict, Optional, Any, cast
from openai.types.chat import ChatCompletionMessageParam
import time
import tiktoken
import shutil
import tempfile

class RAGSystem:
    def __init__(self):
        self.chroma_client: Optional[Any] = None
        self.openai_client = None
        self.collections = {}
        self.db_path: Optional[str] = None
        
        # Load environment configuration for text chunking
        chunk_size = int(os.getenv('TEXT_CHUNK_SIZE', 1000))
        chunk_overlap = int(os.getenv('TEXT_CHUNK_OVERLAP', 200))
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        
        # Load OpenAI configuration from environment - default to modern models
        self.openai_model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.openai_max_tokens = int(os.getenv('OPENAI_MAX_TOKENS', 2000))
        self.openai_temperature = float(os.getenv('OPENAI_TEMPERATURE', 0))
        
        # Optional fallback models when the primary model isn't available
        env_fallbacks = os.getenv('OPENAI_MODEL_FALLBACKS', '')
        self.model_fallbacks = [m.strip() for m in env_fallbacks.split(',') if m.strip()] or [
            'gpt-4o-mini',
            'gpt-4o',
            'gpt-4-turbo',
            'gpt-4',
            'gpt-3.5-turbo-0125'
        ]
        
        # Token counting setup
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.openai_model)
        except Exception:
            # Fallback to a common tokenizer if model-specific one isn't available
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Calculate safe context limits with broader model coverage
        self.max_context_tokens = self._infer_context_window(self.openai_model)
            
        # Reserve tokens for system prompt, user prompt structure, and response
        self.reserved_tokens = 1000 + self.openai_max_tokens
        self.max_content_tokens = max(1024, self.max_context_tokens - self.reserved_tokens)
        
        # Vector database configuration
        self.vector_batch_size = int(os.getenv('VECTOR_BATCH_SIZE', 100))
        self.chroma_db_path = os.getenv('CHROMA_DB_PATH', 'chroma_db')
        
        # Initialize OpenAI
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            self.openai_client = OpenAI(api_key=api_key)
        
        # Embedding model configuration (modern default)
        self.embedding_model = os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
        
        # Initialize ChromaDB
        self._setup_chromadb()

    def _infer_context_window(self, model: str) -> int:
        """Heuristically determine the model context window."""
        name = (model or '').lower()
        # Newer 4o/4.1/turbo/o* models generally support 128k
        if any(k in name for k in ['gpt-4o', 'gpt-4-turbo', 'gpt-4.1', 'gpt-4.1-mini', '4o-mini', 'o1', 'o3']):
            return 128000
        if '32k' in name:
            return 32768
        if '16k' in name or '3.5' in name:
            return 16385
        if 'gpt-4' in name:
            return 8192
        # Sensible default
        return 8192

    def _setup_chromadb(self):
        """Initialize ChromaDB client"""
        try:
            # Preferred persistent path from env
            db_path = os.path.join(os.getcwd(), self.chroma_db_path)
            os.makedirs(db_path, exist_ok=True)
            self.db_path = db_path
            
            # Try persistent client first
            try:
                self.chroma_client = chromadb.PersistentClient(
                    path=db_path,
                    settings=Settings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
                return
            except Exception as e:
                print(f"Warning: Persistent Chroma init failed ({e}). Will try a fresh temp directory...")
                # Try with a brand-new temp directory to avoid schema/lock issues
                tmp_dir = tempfile.mkdtemp(prefix="chroma_db_")
                self.db_path = tmp_dir
                try:
                    self.chroma_client = chromadb.PersistentClient(
                        path=tmp_dir,
                        settings=Settings(
                            anonymized_telemetry=False,
                            allow_reset=True
                        )
                    )
                    print(f"Chroma persistent client initialized at temp path: {tmp_dir}")
                    return
                except Exception as e2:
                    print(f"Warning: Temp persistent Chroma init failed ({e2}). Falling back to EphemeralClient.")
                    self.chroma_client = chromadb.EphemeralClient()
                    self.db_path = None
                    return
        except Exception as e:
            print(f"Error setting up ChromaDB: {str(e)}")
            raise

    def _reset_chroma_storage(self):
        """Reset the Chroma persistent storage to recover from schema mismatches. If persistent setup fails, fall back to EphemeralClient."""
        try:
            # Best-effort close
            self.chroma_client = None
            if self.db_path and os.path.isdir(self.db_path):
                shutil.rmtree(self.db_path, ignore_errors=True)
            # Attempt re-init persistent or ephemeral
            self._setup_chromadb()
            # Clear in-memory collection cache
            self.collections.clear()
            print("ChromaDB storage reset. Database reinitialized (persistent or ephemeral).")
        except Exception as e:
            # Last-resort fallback to ephemeral
            try:
                self.chroma_client = chromadb.EphemeralClient()
                self.db_path = None
                self.collections.clear()
                print("ChromaDB reset fallback to EphemeralClient succeeded.")
            except Exception:
                raise Exception(f"Failed to reset ChromaDB storage: {str(e)}")

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
        client = self.chroma_client
        if client is None:
            raise Exception("ChromaDB client not initialized")
            
        try:
            collection_name = f"documents_{session_id}"
            
            # Delete existing collection if it exists
            try:
                client.delete_collection(collection_name)
            except:
                pass
            
            # Create new collection with robustness
            def _create(c):
                return c.create_collection(
                    name=collection_name,
                    metadata={"description": f"Document collection for session {session_id}"}
                )
            
            try:
                collection = _create(client)
            except Exception as ce:
                msg = str(ce).lower()
                if ("no such column: collections.topic" in msg) or ("collections.topic" in msg) or ("disk i/o error" in msg):
                    self._reset_chroma_storage()
                    client = self.chroma_client
                    if client is None:
                        self.chroma_client = chromadb.EphemeralClient()
                        client = self.chroma_client
                    collection = _create(client)
                else:
                    # Final fallback: switch to ephemeral
                    self.chroma_client = chromadb.EphemeralClient()
                    client = self.chroma_client
                    collection = _create(client)
            
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
                progress = int((page_idx + 1) / max(1, total_pages) * 100)
                if progress_callback:
                    progress_callback(min(progress, 40))  # Cap during ingestion
            
            # Add documents to collection using environment-configured batch size with embeddings
            for i in range(0, len(all_chunks), self.vector_batch_size):
                batch_chunks = all_chunks[i:i + self.vector_batch_size]
                batch_metadatas = all_metadatas[i:i + self.vector_batch_size]
                batch_ids = all_ids[i:i + self.vector_batch_size]
                
                # Create embeddings for this batch
                embeddings = self._embed_texts(batch_chunks)
                
                collection.add(
                    documents=batch_chunks,
                    metadatas=batch_metadatas,
                    ids=batch_ids,
                    embeddings=embeddings
                )
                # Progress through 40-90 during vectorization
                if progress_callback:
                    pct = 40 + int((i + len(batch_chunks)) / max(1, len(all_chunks)) * 50)
                    progress_callback(min(pct, 90))
            
            # Store collection reference
            self.collections[session_id] = collection
            
            print(f"Created vector database with {len(all_chunks)} chunks")
            if progress_callback:
                progress_callback(100)
            
        except Exception as e:
            raise Exception(f"Error creating vector database: {str(e)}")
    
    def query_documents(self, session_id: str, query: str, n_results: int = 10):
        """Query the vector database for relevant chunks"""
        try:
            if session_id not in self.collections:
                client = self.chroma_client
                if client is None:
                    raise Exception("ChromaDB client not initialized")
                collection_name = f"documents_{session_id}"
                self.collections[session_id] = client.get_collection(collection_name)
            
            collection = self.collections[session_id]
            
            # Embed query and search by embedding for reliability
            q_emb = self._embed_texts([query])[0]
            results = collection.query(
                query_embeddings=[q_emb],
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
                if progress_callback: progress_callback(60)
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
        
        if progress_callback: progress_callback(92)
        return self._generate_single_summary(final_text, system_prompt)
    
    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Create embeddings for a list of texts using OpenAI embeddings API."""
        if not self.openai_client:
            raise Exception("OpenAI API key not configured for embeddings")
        try:
            resp = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=texts
            )
            return [d.embedding for d in resp.data]
        except Exception as e:
            raise Exception(f"Error creating embeddings: {str(e)}")
    
    def _generate_single_summary(self, content: str, system_prompt: str) -> str:
        """Call OpenAI Chat Completion to summarize given content with a system prompt. Includes model fallbacks."""
        if not self.openai_client:
            return "OpenAI API key not configured. Cannot generate summary."
        
        messages = cast(List[ChatCompletionMessageParam], [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Summarize the following content. Be concise and structured.\n\n{content}"}
        ])
        
        # Try the configured model first, then fallbacks (ensuring uniqueness/order)
        tried = []
        ordered_models = []
        for m in [self.openai_model] + self.model_fallbacks:
            if m and m not in tried:
                ordered_models.append(m)
                tried.append(m)
        
        errors = []
        for model in ordered_models:
            try:
                resp = self.openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=self.openai_temperature,
                    max_tokens=self.openai_max_tokens
                )
                return (resp.choices[0].message.content or "").strip()
            except Exception as e:
                errors.append(f"{model}: {str(e)}")
                # Try next fallback
                continue
        
        raise Exception("All summary model attempts failed: " + " | ".join(errors))
    
    def _get_collection_for_session(self, session_id: str):
        """Get or open the Chroma collection for a session."""
        if session_id in self.collections:
            return self.collections[session_id]
        if not self.chroma_client:
            raise Exception("ChromaDB client not initialized")
        name = f"documents_{session_id}"
        try:
            collection = self.chroma_client.get_collection(name)
            self.collections[session_id] = collection
            return collection
        except Exception as e:
            raise Exception(f"Collection not found for session {session_id}: {str(e)}")

    def _fetch_all_chunks(self, session_id: str, batch_size: int = 1000) -> List[str]:
        """Fetch all document chunks for a session from its collection."""
        collection = self._get_collection_for_session(session_id)
        chunks: List[str] = []
        try:
            total = collection.count()
            offset = 0
            while offset < total:
                batch = collection.get(
                    include=["documents"],
                    limit=min(batch_size, total - offset),
                    offset=offset
                )
                docs = (batch or {}).get("documents") or []
                # Chroma returns a flat list when using get() without IDs per v0.5+
                chunks.extend([d for d in docs if isinstance(d, str) and d.strip()])
                offset += len(docs)
                if len(docs) == 0:
                    break
            return chunks
        except Exception as e:
            # Fallback: try a single get without pagination
            try:
                batch = collection.get(include=["documents"]) or {}
                docs = batch.get("documents") or []
                return [d for d in docs if isinstance(d, str) and d.strip()]
            except Exception as e2:
                raise Exception(f"Failed to fetch chunks: {str(e)} | {str(e2)}")

    def generate_summary(self, session_id: str, custom_prompt: str = "", progress_callback=None) -> str:
        """Generate a summary for all chunks stored for the given session."""
        # Set an initial progress value for UI feedback
        if progress_callback:
            try:
                progress_callback(10)
            except Exception:
                pass
        # Fetch chunks
        chunks = self._fetch_all_chunks(session_id)
        if not chunks:
            raise Exception("No content available to summarize for this session")
        if progress_callback:
            try:
                progress_callback(30)
            except Exception:
                pass
        # Build system prompt
        default_prompt = (
            "You are an expert news editor. Summarize the newspaper content with a focus on key economic, "
            "business, policy, markets, and company developments. Use concise bullet points grouped into clear "
            "sections (e.g., Macro, Markets, Sectors, Companies, Policy, Global). Keep it factual and avoid speculation."
        )
        system_prompt = (custom_prompt.strip() or default_prompt)
        # Delegate to hierarchical summarizer (handles token limits and progress updates internally)
        summary = self.generate_summary_hierarchical(chunks, system_prompt, progress_callback=progress_callback)
        if progress_callback:
            try:
                progress_callback(100)
            except Exception:
                pass
        return summary

    def get_document_stats(self, session_id: str) -> Dict[str, Any]:
        """Return basic stats about the session's collection."""
        name = f"documents_{session_id}"
        try:
            collection = self._get_collection_for_session(session_id)
            count = 0
            try:
                count = collection.count()
            except Exception:
                # Fallback via get (may be slower)
                batch = collection.get(include=["ids"]) or {}
                ids = batch.get("ids") or []
                count = len(ids)
            status = "ready" if count > 0 else "empty"
            return {
                "collection_name": name,
                "total_chunks": count,
                "status": status
            }
        except Exception as e:
            return {
                "collection_name": name,
                "total_chunks": 0,
                "status": f"not_found: {str(e)}"
            }

    def search_documents_compact(self, session_id: str, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Compact search returning minimal fields. Kept for internal use; prefer search_documents()."""
        res = self.query_documents(session_id, query, n_results=max_results)
        documents = (res.get("documents") or [[]])[0] if isinstance(res.get("documents"), list) else []
        metadatas = (res.get("metadatas") or [[]])[0] if isinstance(res.get("metadatas"), list) else []
        distances = (res.get("distances") or [[]])[0] if isinstance(res.get("distances"), list) else []
        items: List[Dict[str, Any]] = []
        for idx in range(min(len(documents), len(metadatas))):
            doc = documents[idx] if isinstance(documents[idx], str) else ""
            meta = metadatas[idx] or {}
            dist = None
            if idx < len(distances):
                try:
                    dist = float(distances[idx])
                except Exception:
                    dist = None
            score = None
            if dist is not None:
                try:
                    score = 1.0 / (1.0 + max(0.0, dist))
                except Exception:
                    score = None
            items.append({
                "content": doc,
                "source": meta.get("source"),
                "page_number": meta.get("page_number"),
                "chunk_index": meta.get("chunk_index"),
                "relevance_score": score
            })
        return items

    def search_documents(self, session_id: str, query: str, max_results: int = 5):
        """High-level semantic search wrapper returning normalized results for the UI."""
        try:
            if not query or not query.strip():
                return []

            # Run semantic search via embeddings
            raw = self.query_documents(session_id, query, n_results=max_results)

            # Chroma returns lists per query; we queried once
            docs_list = raw.get("documents", []) or []
            metas_list = raw.get("metadatas", []) or []
            ids_list = raw.get("ids", []) or []
            dists_list = raw.get("distances", []) or []

            # Flatten first dimension if present
            docs = docs_list[0] if docs_list and isinstance(docs_list[0], list) else docs_list
            metas = metas_list[0] if metas_list and isinstance(metas_list[0], list) else metas_list
            ids = ids_list[0] if ids_list and isinstance(ids_list[0], list) else ids_list
            dists = dists_list[0] if dists_list and isinstance(dists_list[0], list) else dists_list

            results = []
            count = min(len(docs or []), len(ids or []))
            for i in range(count):
                content = docs[i]
                meta = metas[i] if i < len(metas) else {}
                score = None
                if dists and i < len(dists):
                    try:
                        score = float(dists[i])
                    except Exception:
                        score = None

                results.append({
                    "id": ids[i],
                    "content": content,
                    "source": (meta or {}).get("source"),
                    "page_number": (meta or {}).get("page_number"),
                    "chunk_index": (meta or {}).get("chunk_index"),
                    "session_id": (meta or {}).get("session_id", session_id),
                    "distance": score,
                    "relevance_score": score
                })

            return results
        except Exception as e:
            raise Exception(f"Error during semantic search: {str(e)}")

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