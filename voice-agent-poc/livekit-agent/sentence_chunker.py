"""
Sentence Chunker for TTS Streaming
Based on LiveKit Agents patterns from livekit-agents/tokenize/_basic_sent.py

Rule-based segmentation that buffers partial sentences until minimum length reached.
"""

import re
from dataclasses import dataclass, field
from typing import Generator, List, Optional


@dataclass
class ChunkerConfig:
    """Configuration for sentence chunking"""
    min_sentence_length: int = 20    # Buffer until 20 chars
    min_context_length: int = 10     # Minimum context before tokenizing
    max_batch_length: int = 300      # Max chars per TTS request


class SentenceChunker:
    """
    Rule-based sentence chunker for TTS streaming.

    Based on LiveKit Agents implementation:
    - Splits on sentence boundaries (.!?)
    - Handles abbreviations (Mr., Dr., etc.)
    - Buffers short sentences together
    - Maintains context for proper splitting

    Usage:
        chunker = SentenceChunker()
        for chunk in chunker.process("Hello. How are you? I'm doing well!"):
            print(chunk)  # Yields complete sentences
    """

    def __init__(self, config: Optional[ChunkerConfig] = None):
        self.config = config or ChunkerConfig()
        self._buffer = ""

        # Regex patterns from LiveKit
        self._alphabets = r"([A-Za-z])"
        self._prefixes = r"(Mr|St|Mrs|Ms|Dr|Prof|Capt|Cpt|Lt|Mt|Inc|Ltd|Jr|Sr|Co|Corp)"
        self._suffixes = r"(Inc|Ltd|Jr|Sr|Co|Corp)"
        self._starters = r"(Mr|Mrs|Ms|Dr|Prof|Capt|Cpt|Lt|He\s|She\s|It\s|They\s|Their\s|Our\s|We\s|But\s|However\s|That\s|This\s|Wherever)"
        self._acronyms = r"([A-Z][.][A-Z][.](?:[A-Z][.])?)"
        self._websites = r"[.](com|net|org|io|gov|edu|me|co|uk|ca|de|jp|fr|au|us|ru|ch|it|nl|se|no|es|mil)"
        self._digits = r"([0-9])"

        # Stop marker for sentence endings
        self._stop_marker = "<STOP>"

    def _preprocess(self, text: str) -> str:
        """
        Preprocess text to protect special cases from splitting.
        Adds <STOP> markers at actual sentence boundaries.
        """
        # Protect abbreviations
        text = re.sub(self._prefixes + r"[.]", "\\1<prd>", text)
        text = re.sub(self._websites, "<prd>\\1", text)

        # Protect decimal numbers
        text = re.sub(self._digits + r"[.]" + self._digits, "\\1<prd>\\2", text)

        # Protect acronyms
        text = re.sub(self._acronyms, lambda m: m.group(0).replace(".", "<prd>"), text)

        # Protect ellipsis
        text = re.sub(r"\.{3}", "<ellip>", text)

        # Mark sentence endings with <STOP>
        # Handle quotes after punctuation
        text = re.sub(r'([.!?][""])', f"\\1{self._stop_marker}", text)
        # Handle punctuation without quotes
        text = re.sub(r'([.!?])(?![""])', f"\\1{self._stop_marker}", text)

        return text

    def _postprocess(self, text: str) -> str:
        """Restore protected characters"""
        text = text.replace("<prd>", ".")
        text = text.replace("<ellip>", "...")
        text = text.replace(self._stop_marker, "")
        return text.strip()

    def split_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.

        Returns complete sentences, buffering partials until minimum length.
        """
        processed = self._preprocess(text)
        raw_sentences = processed.split(self._stop_marker)

        sentences = []
        buffer = ""

        for raw in raw_sentences:
            sentence = self._postprocess(raw)
            if not sentence:
                continue

            buffer = f"{buffer} {sentence}".strip() if buffer else sentence

            # Only yield when buffer exceeds minimum length
            if len(buffer) >= self.config.min_sentence_length:
                sentences.append(buffer)
                buffer = ""

        # Keep remaining buffer for next call
        if buffer:
            sentences.append(buffer)

        return sentences

    def process(self, text: str) -> Generator[str, None, None]:
        """
        Process text and yield complete sentence chunks.

        Maintains internal buffer for streaming use case.
        """
        # Add to buffer
        self._buffer = f"{self._buffer} {text}".strip() if self._buffer else text

        # Check if we have enough content
        if len(self._buffer) < self.config.min_context_length:
            return

        # Split and yield complete sentences
        sentences = self.split_sentences(self._buffer)

        # Yield all but the last sentence (might be incomplete)
        for sentence in sentences[:-1]:
            yield sentence

        # Keep last sentence in buffer (might be incomplete)
        if sentences:
            self._buffer = sentences[-1]

    def flush(self) -> Optional[str]:
        """
        Flush any remaining content in the buffer.
        Call at end of stream.
        """
        if self._buffer and len(self._buffer) >= self.config.min_context_length:
            result = self._postprocess(self._buffer)
            self._buffer = ""
            return result
        return None


class TTSBatcher:
    """
    Batches sentences for TTS requests.

    From LiveKit stream_pacer.py:
    - First sentence sent immediately (minimize TTFB)
    - Subsequent batches wait until audio buffer is low
    - Max batch size of 300 chars
    """

    def __init__(self, max_batch_length: int = 300):
        self.max_batch_length = max_batch_length
        self._sentences: List[str] = []
        self._first_sentence_sent = False

    def add_sentence(self, sentence: str) -> None:
        """Add a sentence to the queue"""
        self._sentences.append(sentence)

    def should_send_now(self, remaining_audio_sec: float = 0.0) -> bool:
        """
        Determine if we should send a batch now.

        Args:
            remaining_audio_sec: Seconds of audio remaining in playback buffer

        Returns:
            True if we should send a batch
        """
        if not self._sentences:
            return False

        # First sentence: send immediately
        if not self._first_sentence_sent:
            return True

        # After first: wait until audio buffer is low
        return remaining_audio_sec <= 5.0

    def get_batch(self) -> Optional[str]:
        """
        Get the next batch of text for TTS.

        Returns text up to max_batch_length chars.
        """
        if not self._sentences:
            return None

        batch = []
        total_length = 0

        while self._sentences:
            sentence = self._sentences[0]

            # Check if adding this sentence would exceed limit
            if total_length + len(sentence) > self.max_batch_length and batch:
                break

            batch.append(self._sentences.pop(0))
            total_length += len(sentence) + 1  # +1 for space

            # For first sentence, send immediately without batching
            if not self._first_sentence_sent:
                self._first_sentence_sent = True
                break

        return " ".join(batch) if batch else None

    def has_pending(self) -> bool:
        """Check if there are pending sentences"""
        return len(self._sentences) > 0

    def clear(self) -> None:
        """Clear all pending sentences (e.g., on interruption)"""
        self._sentences.clear()
