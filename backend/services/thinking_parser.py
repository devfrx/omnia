"""O.M.N.I.A. — Streaming parser for ``<think>…</think>`` reasoning tags."""

from __future__ import annotations


class ThinkTagParser:
    """Separate ``<think>…</think>`` blocks from regular content in a stream.

    Designed for models (QwQ, DeepSeek-R1, …) that emit reasoning tokens
    wrapped in ``<think>`` tags inline with the answer.  The parser handles
    tags that span chunk boundaries by holding back ambiguous suffixes until
    the next chunk arrives.

    Example::

        parser = ThinkTagParser()
        for chunk in stream:
            for kind, text in parser.feed(chunk):
                if kind == "thinking":
                    yield {"type": "thinking", "content": text}
                else:
                    yield {"type": "token", "content": text}
        # After stream ends, flush any remaining buffer.
        for kind, text in parser.flush():
            ...
    """

    _OPEN: str = "<think>"
    _CLOSE: str = "</think>"

    def __init__(self) -> None:
        self._in_thinking: bool = False
        self._buffer: str = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def feed(self, text: str) -> list[tuple[str, str]]:
        """Feed the next streamed chunk and extract tagged segments.

        Args:
            text: A piece of streamed text that may contain partial or
                complete ``<think>`` / ``</think>`` tags.

        Returns:
            A list of ``(kind, text)`` tuples where *kind* is
            ``"thinking"`` for content inside tags, or ``"content"``
            for everything else.  May be empty if the chunk is held
            back while waiting for a possible partial tag.
        """
        self._buffer += text
        results: list[tuple[str, str]] = []

        while self._buffer:
            tag = self._CLOSE if self._in_thinking else self._OPEN

            idx = self._buffer.find(tag)
            if idx == -1:
                # No complete tag — emit the safe prefix, keep the rest.
                safe, held = self._split_at_partial(self._buffer, tag)
                if safe:
                    kind = "thinking" if self._in_thinking else "content"
                    results.append((kind, safe))
                self._buffer = held
                break

            # Emit everything before the tag.
            if idx > 0:
                kind = "thinking" if self._in_thinking else "content"
                results.append((kind, self._buffer[:idx]))

            # Advance past the tag and flip state.
            self._buffer = self._buffer[idx + len(tag) :]
            self._in_thinking = not self._in_thinking

        return results

    def flush(self) -> list[tuple[str, str]]:
        """Flush any remaining buffered text after the stream ends.

        Returns:
            A (possibly empty) list of ``(kind, text)`` tuples for
            whatever content was being held back.
        """
        if not self._buffer:
            return []

        kind = "thinking" if self._in_thinking else "content"
        result = [(kind, self._buffer)]
        self._buffer = ""
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _split_at_partial(text: str, tag: str) -> tuple[str, str]:
        """Split *text* so that a trailing prefix of *tag* is held back.

        If the end of *text* matches the beginning of *tag*, that suffix
        might be the start of an incoming tag and must not be emitted yet.

        Args:
            text: The text to split.
            tag:  The tag we are currently watching for.

        Returns:
            ``(safe, held)`` where ``safe + held == text``.
        """
        max_check = min(len(text), len(tag) - 1)
        for length in range(max_check, 0, -1):
            if tag.startswith(text[-length:]):
                return text[:-length], text[-length:]
        return text, ""
