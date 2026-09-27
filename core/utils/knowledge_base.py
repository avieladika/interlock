import os
import shutil
from typing import List, Optional, Dict, Any

import chromadb
from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    StorageContext,
    Settings,
    Document
)
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.groq import Groq

class KnowledgeBase:
    """
    Manages RAG operations: Indexing codebase/docs and querying them.
    Uses ChromaDB as the vector store and LlamaIndex for orchestration.
    Uses local HuggingFace embeddings (free) and Groq for LLM.
    """

    def __init__(self, persist_dir: str = "./chroma_db", collection_name: str = "interlock_codebase"):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        
        # --- Configure LlamaIndex Settings ---
        Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
        
        groq_api_key = os.getenv("GROQ_API")
        if groq_api_key:
            Settings.llm = Groq(model="llama-3.3-70b-versatile", api_key=groq_api_key)
        else:
            print("⚠️ Warning: GROQ_API not found. RAG synthesis might fail.")

        # --- Initialize ChromaDB ---
        self.chroma_client = chromadb.PersistentClient(path=persist_dir)
        self.chroma_collection = self.chroma_client.get_or_create_collection(collection_name)
        
        self.vector_store = ChromaVectorStore(chroma_collection=self.chroma_collection)
        self.storage_context = StorageContext.from_defaults(vector_store=self.vector_store)
        
        self.index = None
        self._load_index()

    def _load_index(self):
        try:
            if self.chroma_collection.count() > 0:
                self.index = VectorStoreIndex.from_vector_store(
                    self.vector_store,
                    storage_context=self.storage_context,
                )
            else:
                self.index = None
        except Exception:
            self.index = None

    def index_codebase(self, root_dir: str, extensions: List[str] = [".py", ".md", ".txt"]):
        """
        Scans the codebase and indexes files.
        """
        print(f"📚 Indexing codebase from: {root_dir}...")
        
        if not os.path.exists(root_dir):
            print(f"❌ Directory not found: {root_dir}")
            return

        try:
            # Load documents
            # We simplify exclude to avoid issues
            reader = SimpleDirectoryReader(
                input_dir=root_dir,
                recursive=True,
                required_exts=extensions,
                exclude=["**/__pycache__/**", "**/.git/**"]
            )
            
            documents = reader.load_data()
            
            if not documents:
                print(f"⚠️ No documents found in {root_dir} with extensions {extensions}. Skipping index.")
                return

            print(f"   Found {len(documents)} documents to index.")
            
            # Create or update index
            if self.index:
                self.index = VectorStoreIndex.from_documents(
                    documents, 
                    storage_context=self.storage_context,
                    show_progress=True
                )
            else:
                self.index = VectorStoreIndex.from_documents(
                    documents, 
                    storage_context=self.storage_context,
                    show_progress=True
                )
                
            print("✅ Codebase indexing complete.")
            
        except Exception as e:
            print(f"❌ Indexing failed: {e}")

    def add_documents(self, texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None):
        """
        Adds raw text (e.g., from Confluence) to the index.
        """
        docs = []
        for i, text in enumerate(texts):
            meta = metadatas[i] if metadatas and i < len(metadatas) else {}
            docs.append(Document(text=text, metadata=meta))
        
        if not self.index:
            self.index = VectorStoreIndex.from_documents(
                docs, storage_context=self.storage_context
            )
        else:
            for doc in docs:
                self.index.insert(doc)

    def query(self, question: str, k: int = 5) -> str:
        if not self.index:
            return "Knowledge base is empty. Please index data first."
        
        retriever = self.index.as_retriever(similarity_top_k=k)
        query_engine = self.index.as_query_engine(retriever=retriever)
        
        response = query_engine.query(question)
        return str(response)

    def clear_index(self):
        try:
            self.chroma_client.delete_collection(self.collection_name)
            self.chroma_collection = self.chroma_client.get_or_create_collection(self.collection_name)
            self.index = None
            print("🗑️ Knowledge base cleared.")
        except Exception as e:
            print(f"❌ Failed to clear index: {e}")
