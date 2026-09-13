"""Nexus-Alpha — Cognition module (Chain-of-Thought + RAG ativo + NER + memória local + reflexão)."""
from .reasoning import ChainOfThought, ReasoningStep
from .reasoning_engine import ReasoningEngine, ActionPlan, Thought
from .rag_engine import RAGEngine
from .extractor import EntityExtractor, Triple
from .nlp_extractor import NLPExtractor
from .memory import LocalMemory
from .reflection import ReflectionWorker
from .llm_provider import ExtractiveResponder, OpenAICompatibleLLM, get_llm_provider
from .chat_service import ChatService
from .embeddings import hash_embedding

__all__ = [
    "ChainOfThought", "ReasoningStep",
    "ReasoningEngine", "ActionPlan", "Thought",
    "RAGEngine", "EntityExtractor", "Triple", "NLPExtractor",
    "LocalMemory", "ReflectionWorker",
    "ExtractiveResponder", "OpenAICompatibleLLM", "get_llm_provider",
    "ChatService", "hash_embedding",
]