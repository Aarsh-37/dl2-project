"""Tests never hit the network: LLM calls are disabled by default.

Set CAREERPILOT_LLM=1 explicitly to run a live-LLM test locally.
"""
import os

os.environ.setdefault("CAREERPILOT_LLM", "0")
os.environ.setdefault("CAREERPILOT_KB", "0")  # curated fallback, no DB reads
os.environ.setdefault("CAREERPILOT_SEMANTIC", "0")  # hermetic: skip embeddings
os.environ.setdefault("LLM_TASK_PROVIDERS", "")  # no per-agent override in tests
