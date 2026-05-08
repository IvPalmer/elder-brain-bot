"""Text-to-Speech handler using Kokoro TTS for Telegram voice replies."""

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class TTSConfig:
    """TTS configuration."""

    enabled: bool = True
    voice: str = "pm_alex"
    rate: str = "-5%"  # kept for config compat, not used by Kokoro
    pitch: str = "-3%"  # kept for config compat, not used by Kokoro
    max_chars: int = 4000
    base_url: str = "http://localhost:8880/v1"
    model: str = "kokoro"


class TTSHandler:
    """Generate voice replies using Kokoro TTS (local, OpenAI-compatible)."""

    def __init__(self, config: TTSConfig):
        self.config = config
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key="not-needed",
                base_url=self.config.base_url,
            )
            return self._client
        except ModuleNotFoundError:
            raise RuntimeError(
                "openai is not installed. Install with: pip install openai"
            )

    async def text_to_voice(self, text: str) -> Optional[Path]:
        """Convert text to an OGG voice file suitable for Telegram.

        Returns path to the generated audio file, or None on failure.
        """
        if not text or not text.strip():
            return None

        # Truncate if too long
        if len(text) > self.config.max_chars:
            text = text[: self.config.max_chars] + "..."
            logger.info(
                "TTS text truncated",
                original_length=len(text),
                max_chars=self.config.max_chars,
            )

        # Strip markdown formatting for cleaner speech
        clean_text = self._strip_markdown(text)
        if not clean_text.strip():
            return None

        tmp_ogg = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False)
        tmp_ogg.close()

        try:
            client = self._get_client()

            # Kokoro outputs OGG/Opus natively — no ffmpeg needed
            response = await client.audio.speech.create(
                model=self.config.model,
                input=clean_text,
                voice=self.config.voice,
                response_format="opus",
            )

            # Write audio bytes to file
            audio_bytes = response.content
            ogg_path = Path(tmp_ogg.name)
            ogg_path.write_bytes(audio_bytes)

            logger.info(
                "TTS audio generated via Kokoro",
                text_length=len(clean_text),
                file_size=ogg_path.stat().st_size,
                voice=self.config.voice,
            )
            return ogg_path

        except Exception as e:
            logger.error("TTS generation failed", error=str(e))
            Path(tmp_ogg.name).unlink(missing_ok=True)
            return None

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Remove markdown formatting for cleaner TTS output."""
        import re

        # Remove code blocks
        text = re.sub(r"```[\s\S]*?```", "", text)
        # Remove inline code
        text = re.sub(r"`[^`]+`", "", text)
        # Remove bold/italic markers
        text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
        text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
        # Remove headers
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        # Remove links, keep text
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Collapse whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
