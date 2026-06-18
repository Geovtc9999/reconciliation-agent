"""Observabilité Langfuse — optionnelle, dégradée proprement si non configurée."""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache

from .config import settings


@lru_cache(maxsize=1)
def _client():
    if not settings.langfuse_configured:
        return None
    try:
        from langfuse import Langfuse
        return Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception:
        return None


@contextmanager
def observe(name: str, metadata: dict | None = None, input: object | None = None):
    cli = _client()
    if cli is None:
        yield None
        return
    trace = None
    try:
        trace = cli.trace(name=name, metadata=metadata or {}, input=input)
    except Exception:
        trace = None
    try:
        yield trace
    finally:
        try:
            cli.flush()
        except Exception:
            pass


def log_generation(trace, *, name, model, input, output, usage=None,
                   start_time=None, end_time=None) -> None:
    if trace is None:
        return
    try:
        kwargs = {"name": name, "model": model, "input": input,
                  "output": output, "usage": usage or None}
        if start_time is not None:
            kwargs["start_time"] = start_time
        if end_time is not None:
            kwargs["end_time"] = end_time
        trace.generation(**kwargs)
    except Exception:
        pass


def log_event(trace, *, name: str, metadata: dict | None = None) -> None:
    if trace is None:
        return
    try:
        trace.event(name=name, metadata=metadata or {})
    except Exception:
        pass


def healthcheck() -> dict:
    return {
        "configured": settings.langfuse_configured,
        "host": settings.langfuse_host if settings.langfuse_configured else None,
        "client": _client() is not None,
    }
