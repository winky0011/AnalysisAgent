import os
import time
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

load_dotenv()

try:
	# Optional dependency; we guard its usage
	from qdrant_client import QdrantClient
	from qdrant_client.http import models as qmodels
	_HAS_QDRANT = True
except Exception:
	_HAS_QDRANT = False
	QdrantClient = None  # type: ignore
	qmodels = None  # type: ignore

try:
	from common.get_models import get_embeddings_model
	_HAS_EMBED = True
except Exception:
	_HAS_EMBED = False
	get_embeddings_model = None  # type: ignore


class MemoryBackend:
	"""Abstract memory backend interface."""

	def search(self, namespace: str, query: str, top_k: int = 5, min_score: float = 0.3) -> List[Dict[str, Any]]:
		raise NotImplementedError

	def write(self, namespace: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		raise NotImplementedError

	def update(self, namespace: str, item_id: str, content: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		raise NotImplementedError

	def delete(self, namespace: str, item_id: Optional[str] = None, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		raise NotImplementedError


class InMemoryBackend(MemoryBackend):
	"""Simple in-process backend; suitable as a safe fallback."""

	def __init__(self) -> None:
		self._store: Dict[str, Dict[str, Dict[str, Any]]] = {}
		self._id_counter: int = 0
		self._embedding = self._init_embedder()

	def _init_embedder(self):
		if not _HAS_EMBED:
			return None
		try:
			return get_embeddings_model()
		except Exception:
			return None

	def _ensure_ns(self, namespace: str) -> Dict[str, Dict[str, Any]]:
		if namespace not in self._store:
			self._store[namespace] = {}
		return self._store[namespace]

	def _embed(self, text: str) -> Optional[List[float]]:
		if self._embedding is None:
			return None
		try:
			vec = self._embedding.embed_documents([text])  # returns List[List[float]]
			return vec[0] if vec else None
		except Exception:
			return None

	def search(self, namespace: str, query: str, top_k: int = 5, min_score: float = 0.3) -> List[Dict[str, Any]]:
		# naive semantic search: cosine via embeddings when available; otherwise keyword overlap
		ns = self._ensure_ns(namespace)
		query_vec = self._embed(query)
		results: List[Tuple[str, Dict[str, Any], float]] = []
		for item_id, item in ns.items():
			score = 0.0
			if query_vec is not None and "embedding" in item and item["embedding"] is not None:
				# cosine similarity
				a = query_vec
				b = item["embedding"]
				dot = sum(x * y for x, y in zip(a, b))
				norm_a = sum(x * x for x in a) ** 0.5
				norm_b = sum(x * x for x in b) ** 0.5
				score = dot / (norm_a * norm_b + 1e-9)
			else:
				# fallback keyword score
				q_words = set(query.lower().split())
				score = len([w for w in q_words if w in item["content"].lower().split()]) / (len(q_words) + 1e-9)
			if score >= min_score:
				results.append((item_id, item, float(score)))
		results.sort(key=lambda x: x[2], reverse=True)
		out: List[Dict[str, Any]] = []
		for item_id, item, score in results[:top_k]:
			out.append({"id": item_id, "content": item["content"], "metadata": item.get("metadata", {}), "score": score})
		return out

	def write(self, namespace: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		ns = self._ensure_ns(namespace)
		self._id_counter += 1
		item_id = f"{int(time.time())}_{self._id_counter}"
		item = {
			"id": item_id,
			"content": content,
			"metadata": metadata or {},
			"created_at": int(time.time()),
			"updated_at": int(time.time()),
			"embedding": self._embed(content),
		}
		ns[item_id] = item
		return {"id": item_id, "status": "ok"}

	def update(self, namespace: str, item_id: str, content: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		ns = self._ensure_ns(namespace)
		if item_id not in ns:
			return {"id": item_id, "status": "not_found"}
		if content is not None:
			ns[item_id]["content"] = content
			ns[item_id]["embedding"] = self._embed(content)
		if metadata is not None:
			ns[item_id]["metadata"] = {**ns[item_id].get("metadata", {}), **metadata}
		ns[item_id]["updated_at"] = int(time.time())
		return {"id": item_id, "status": "ok"}

	def delete(self, namespace: str, item_id: Optional[str] = None, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		ns = self._ensure_ns(namespace)
		if item_id:
			if item_id in ns:
				del ns[item_id]
				return {"deleted": 1}
			return {"deleted": 0}
		# simple filter delete on metadata equality
		if filters:
			keys = [k for k, v in ns.items() if all(v.get("metadata", {}).get(fk) == fv for fk, fv in filters.items())]
			for k in keys:
				del ns[k]
			return {"deleted": len(keys)}
		count = len(ns)
		self._store[namespace] = {}
		return {"deleted": count}


class QdrantBackend(MemoryBackend):
	"""Qdrant-backed persistent memory store."""

	def __init__(self) -> None:
		if not _HAS_QDRANT:
			raise RuntimeError("qdrant-client is not installed")
		self._client = QdrantClient(
			url=os.getenv("QDRANT_URL"),
			api_key=os.getenv("QDRANT_KEY"),
		)
		# Validate connectivity early so factory can gracefully fall back
		try:
			# Lightweight call; will raise on bad URL (404/conn error)
			self._client.get_collections()
		except Exception as exc:
			# Re-raise to let init_memory_backend choose InMemoryBackend
			raise RuntimeError(f"Qdrant not reachable: {exc}")
		self._embedding = self._init_embedder()
		self._dims = int(os.getenv("EMBEDDING_DIM", "768"))

	def _init_embedder(self):
		if not _HAS_EMBED:
			raise RuntimeError("langchain embeddings not available")
		return get_embeddings_model()

	def _ensure_collection(self, collection: str) -> None:
		exists = False
		try:
			info = self._client.get_collection(collection_name=collection)
			exists = bool(info)
		except Exception:
			exists = False
		if not exists:
			# If collection doesn't exist, create it (avoid recreate which deletes first and may 404)
			try:
				self._client.create_collection(
					collection_name=collection,
					vectors_config=qmodels.VectorParams(size=self._dims, distance=qmodels.Distance.COSINE),
				)
			except Exception as exc:
				# Surface clearer guidance if server path/URL is wrong (common 404 case)
				raise RuntimeError(
					f"Failed to create Qdrant collection '{collection}'. "
					f"Check QDRANT_URL (e.g., 'http://localhost:6333') and API compatibility. Error: {exc}"
				)

	def _embed(self, text: str) -> List[float]:
		vec = self._embedding.embed_documents([text])
		return vec[0]

	def search(self, namespace: str, query: str, top_k: int = 5, min_score: float = 0.3) -> List[Dict[str, Any]]:
		self._ensure_collection(namespace)
		query_vec = self._embed(query)
		res = self._client.search(
			collection_name=namespace,
			query_vector=query_vec,
			limit=top_k,
		)
		out: List[Dict[str, Any]] = []
		for p in res:
			score = float(p.score or 0.0)
			if score < min_score:
				continue
			out.append({"id": str(p.id), "content": p.payload.get("content", ""), "metadata": p.payload.get("metadata", {}), "score": score})
		return out

	def write(self, namespace: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		self._ensure_collection(namespace)
		vec = self._embed(content)
		payload = {
			"content": content,
			"metadata": metadata or {},
			"created_at": int(time.time()),
			"updated_at": int(time.time()),
		}
		points = [
			qmodels.PointStruct(id=None, vector=vec, payload=payload),
		]
		self._client.upsert(collection_name=namespace, points=points)
		return {"id": "auto", "status": "ok"}

	def update(self, namespace: str, item_id: str, content: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		# Qdrant doesn't support partial update of vector easily without fetching; we perform overwrite by re-writing payload and vector if content changes
		# Fetch existing
		self._ensure_collection(namespace)
		# Best effort: set payload fields; if content provided, set vector too
		set_payload = {}
		if metadata is not None:
			set_payload["metadata"] = metadata
		if content is not None:
			set_payload["content"] = content
			set_payload["updated_at"] = int(time.time())
			vec = self._embed(content)
			self._client.upsert(
				collection_name=namespace,
				points=[qmodels.PointStruct(id=item_id, vector=vec, payload=set_payload)],
			)
		else:
			self._client.set_payload(collection_name=namespace, payload=set_payload, points=[item_id])
		return {"id": item_id, "status": "ok"}

	def delete(self, namespace: str, item_id: Optional[str] = None, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		self._ensure_collection(namespace)
		if item_id:
			self._client.delete(collection_name=namespace, points_selector=qmodels.PointIdsList(points=[item_id]))
			return {"deleted": 1}
		if filters:
			# Basic filter by payload equality
			conditions = []
			for k, v in filters.items():
				conditions.append(qmodels.FieldCondition(key=f"{k}", match=qmodels.MatchValue(value=v)))
			flt = qmodels.Filter(must=conditions)
			self._client.delete(collection_name=namespace, points_selector=qmodels.FilterSelector(filter=flt))
			# Qdrant doesn't return deleted count; return -1 as unknown
			return {"deleted": -1}
		# Dangerous: delete entire collection contents
		self._client.delete(collection_name=namespace, points_selector=qmodels.FilterSelector(filter=qmodels.Filter(must=[])))
		return {"deleted": -1}


def init_memory_backend() -> MemoryBackend:
	"""Factory to choose Qdrant if configured; otherwise fallback to in-memory."""
	q_url = os.getenv("QDRANT_URL")
	q_key = os.getenv("QDRANT_KEY")
	if q_url and q_key and _HAS_QDRANT and _HAS_EMBED:
		try:
			return QdrantBackend()
		except Exception:
			return InMemoryBackend()
	return InMemoryBackend()


