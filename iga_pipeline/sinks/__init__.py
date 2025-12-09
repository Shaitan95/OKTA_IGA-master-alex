"""Sink implementations for the lightweight pipeline."""

from .file_sink import FileSink, LoggingSink

__all__ = ["FileSink", "LoggingSink"]
