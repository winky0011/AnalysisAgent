import os
from typing import Annotated, Any, Dict, Optional

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from common.memory_backend import MemoryBackend, init_memory_backend


def _ns_from_state(default_prefix: str, state: Dict[str, Any]) -> str:
	user_id = state.get("user_id") or state.get("langgraph_user_id") or "anonymous"
	return f"{default_prefix}/{user_id}"


def create_supervisor_memory_tools(
	default_namespace_prefix: str = "supervisor_memories",
	backend: Optional[MemoryBackend] = None,
):
	be = backend or init_memory_backend()

	@tool("memory_search", return_direct=False)
	def memory_search(
		query: str,
		top_k: int = 5,
		min_score: float = 0.3,
		state: Annotated[Dict[str, Any], InjectedState] = {},  # type: ignore[assignment]
		namespace: Optional[str] = None,
	):
		"""Search memory items by semantic similarity within a namespace."""
		ns = namespace or _ns_from_state(default_namespace_prefix, state)
		results = be.search(ns, query, top_k=top_k, min_score=min_score)
		return {"namespace": ns, "results": results}

	@tool("memory_write", return_direct=False)
	def memory_write(
		content: str,
		metadata: Optional[Dict[str, Any]] = None,
		state: Annotated[Dict[str, Any], InjectedState] = {},  # type: ignore[assignment]
		namespace: Optional[str] = None,
	):
		"""Write a new memory item with optional metadata into a namespace."""
		ns = namespace or _ns_from_state(default_namespace_prefix, state)
		res = be.write(ns, content, metadata or {})
		return {"namespace": ns, **res}

	@tool("memory_update", return_direct=False)
	def memory_update(
		item_id: str,
		content: Optional[str] = None,
		metadata: Optional[Dict[str, Any]] = None,
		state: Annotated[Dict[str, Any], InjectedState] = {},  # type: ignore[assignment]
		namespace: Optional[str] = None,
	):
		"""Update an existing memory item by id; supports content and metadata updates."""
		ns = namespace or _ns_from_state(default_namespace_prefix, state)
		res = be.update(ns, item_id, content=content, metadata=metadata)
		return {"namespace": ns, **res}

	@tool("memory_delete", return_direct=False)
	def memory_delete(
		item_id: Optional[str] = None,
		filters: Optional[Dict[str, Any]] = None,
		state: Annotated[Dict[str, Any], InjectedState] = {},  # type: ignore[assignment]
		namespace: Optional[str] = None,
	):
		"""Delete a memory item by id or by filters within a namespace."""
		ns = namespace or _ns_from_state(default_namespace_prefix, state)
		res = be.delete(ns, item_id=item_id, filters=filters)
		return {"namespace": ns, **res}

	# Minimal routing: simple heuristics
	@tool("memory_route", return_direct=False)
	def memory_route(
		message: str,
		state: Annotated[Dict[str, Any], InjectedState] = {},  # type: ignore[assignment]
	):
		"""Heuristically decide whether to read or write memory based on the message."""
		text = message.lower()
		should_write = any(x in text for x in ["记住", "默认", "以后都", "偏好", "习惯"])
		should_read = any(x in text for x in ["以前", "之前", "上次", "你知道我", "我的偏好"])
		namespaces = [_ns_from_state(default_namespace_prefix, state)]
		return {"should_read": should_read, "should_write": should_write, "namespaces": namespaces}

	# Minimal summarize: join strings
	@tool("memory_summarize", return_direct=False)
	def memory_summarize(
		items: list[str],
		goal: str = "summarize context",
	):
		"""Create a short bullet-list summary for given items aligned to a goal."""
		summary = f"{goal}:\n" + "\n".join(f"- {x}" for x in items[:10])
		return {"summary": summary}

	return [memory_search, memory_write, memory_update, memory_delete, memory_route, memory_summarize]


