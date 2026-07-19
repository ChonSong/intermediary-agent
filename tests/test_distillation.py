"""
Tests for DistillationBuffer and distill logic.

Validates:
- Sentence boundary detection for 1-4 char SSE deltas
- Multi-sentence stream splitting
- Safety yield at >150 chars
- Markdown stripping
- Distill limits to first 1-2 sentences
"""

import pytest

from intermediary.distillation import DistillationBuffer, strip_markdown, distill


class TestDistillationBuffer:
    """Tests for the sentence boundary detection buffer."""
    
    def test_single_sentence(self):
        """1-char deltas for 'First, let me check.' should emit at period."""
        buf = DistillationBuffer()
        deltas = ["F", "ir", "st", ", ", "le", "t ", "me", " ch", "ec", "k."]
        
        emitted = []
        for delta in deltas:
            result = buf.feed(delta)
            if result:
                emitted.append(result)
        
        assert emitted == ["First, let me check."]
    
    def test_multi_sentence(self):
        """Two sentences should emit separately."""
        buf = DistillationBuffer()
        deltas = ["F", "ir", "st", ". ", "Se", "co", "nd", "."]
        
        emitted = []
        for delta in deltas:
            result = buf.feed(delta)
            if result:
                emitted.append(result)
        
        assert emitted == ["First.", "Second."]
    
    def test_4char_deltas(self):
        """4-char deltas (max SSE chunk) should still work."""
        buf = DistillationBuffer()
        deltas = ["Firs", "t, l", "et m", "e ch", "eck."]
        
        emitted = []
        for delta in deltas:
            result = buf.feed(delta)
            if result:
                emitted.append(result)
        
        assert emitted == ["First, let me check."]
    
    def test_colon_boundary(self):
        """Colon should be treated as a boundary (often precedes explanation)."""
        buf = DistillationBuffer()
        deltas = ["Ch", "ec", "k:", " do", "ck", "."]
        
        emitted = []
        for delta in deltas:
            result = buf.feed(delta)
            if result:
                emitted.append(result)
        
        assert emitted == ["Check:", "dock."]
    
    def test_newline_boundary(self):
        """Newline should trigger emission when there's text before it."""
        buf = DistillationBuffer()
        result = buf.feed("First paragraph")
        assert result is None  # No boundary yet
        assert buf.buffer == "First paragraph"
        
        # Now feed newline — should trigger emission
        result = buf.feed("\n")
        assert result == "First paragraph"
    
    def test_safety_yield_at_150(self):
        """Long text without punctuation should force-emit at >150 chars."""
        buf = DistillationBuffer()
        text = "x" * 160
        
        emitted = []
        for c in text:
            result = buf.feed(c)
            if result:
                emitted.append(result)
        
        assert len(emitted) >= 1
        assert len(emitted[0]) > 100
    
    def test_flush_at_stream_end(self):
        """Flush should emit remaining buffer at stream end."""
        buf = DistillationBuffer()
        for c in "Incomplete sentence without ending":
            result = buf.feed(c)
            assert result is None  # No boundary yet
        
        result = buf.flush()
        assert result == "Incomplete sentence without ending"
    
    def test_flush_empty(self):
        """Flush on empty buffer should return None."""
        buf = DistillationBuffer()
        assert buf.flush() is None
    
    def test_empty_delta(self):
        """Empty deltas should not trigger emission."""
        buf = DistillationBuffer()
        assert buf.feed("") is None
        assert buf.feed(".") == "."  # Just a period is a valid sentence


class TestStripMarkdown:
    """Tests for spoken-text markdown stripping."""
    
    def test_bold(self):
        assert strip_markdown("**Docker** is great.") == "Docker is great."
    
    def test_italic(self):
        assert strip_markdown("*Docker* is great.") == "Docker is great."
    
    def test_inline_code(self):
        assert strip_markdown("Run `sudo usermod` now.") == "Run sudo usermod now."
    
    def test_links(self):
        assert strip_markdown("[click here](http://example.com)") == "click here"
    
    def test_nested(self):
        assert strip_markdown("**bold** and *italic* and `code`") == "bold and italic and code"
    
    def test_no_markdown(self):
        assert strip_markdown("Plain text here.") == "Plain text here."


class TestDistill:
    """Tests for distill function (rewrites for speech)."""
    
    @pytest.mark.asyncio
    async def test_distill_basic(self):
        """Distill should just cleanup text for speech."""
        result = await distill("First, let me check the Docker logs.")
        assert result == "First, let me check the Docker logs."
    
    @pytest.mark.asyncio
    async def test_distill_strips_markdown(self):
        """Distill should strip markdown formatting."""
        result = await distill("**Docker** is great.")
        assert result == "Docker is great."
    
    @pytest.mark.asyncio
    async def test_distill_keeps_first_two_sentences(self):
        """Distill should keep only first 1-2 sentences."""
        text = "First sentence. Second sentence. Third sentence."
        result = await distill(text)
        assert result == "First sentence. Second sentence."
    
    @pytest.mark.asyncio
    async def test_distill_strips_tool_use_json(self):
        """Distill should strip embedded tool use JSON."""
        text = "Check the logs. {\"tool\": \"read_file\", \"args\": {\"path\": \"/var/log/syslog\"}} Done."
        result = await distill(text)
        assert "tool" not in result
        assert "Done" in result


class TestHasSentenceBoundary:
    """Test sentence boundary detection rules directly."""
    
    def test_period(self):
        assert DistillationBuffer._has_sentence_boundary("Hello.") is True
    
    def test_exclamation(self):
        assert DistillationBuffer._has_sentence_boundary("Hello!") is True
    
    def test_question(self):
        assert DistillationBuffer._has_sentence_boundary("Hello?") is True
    
    def test_colon(self):
        assert DistillationBuffer._has_sentence_boundary("Note:") is True
    
    def test_newline(self):
        assert DistillationBuffer._has_sentence_boundary("Line one\nLine two") is True
    
    def test_no_boundary(self):
        assert DistillationBuffer._has_sentence_boundary("Hello") is False
    
    def test_empty(self):
        assert DistillationBuffer._has_sentence_boundary("") is False
    
    def test_comma_not_boundary(self):
        """Comma alone should NOT be a boundary (changed from earlier behavior)."""
        assert DistillationBuffer._has_sentence_boundary("Hello, world") is False
    
    def test_long_text_is_boundary(self):
        """>150 chars should force-emit even without punctuation."""
        assert DistillationBuffer._has_sentence_boundary("x" * 151) is True
        assert DistillationBuffer._has_sentence_boundary("x" * 100) is False
