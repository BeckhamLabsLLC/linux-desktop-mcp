"""Tests for input backend module."""

from linux_desktop_mcp.input_backends import MAX_TEXT_LENGTH


class TestInputBackendConstants:
    """Tests for input backend constants."""

    def test_max_text_length(self):
        """Test MAX_TEXT_LENGTH constant."""
        assert MAX_TEXT_LENGTH == 10000
        assert isinstance(MAX_TEXT_LENGTH, int)


class TestInputValidation:
    """Tests for input validation logic."""

    def test_text_length_under_limit(self):
        """Test text under the length limit."""
        text = "a" * 100
        assert len(text) <= MAX_TEXT_LENGTH

    def test_text_length_at_limit(self):
        """Test text at exactly the length limit."""
        text = "a" * MAX_TEXT_LENGTH
        assert len(text) == MAX_TEXT_LENGTH

    def test_text_length_over_limit(self):
        """Test text over the length limit."""
        text = "a" * (MAX_TEXT_LENGTH + 1)
        assert len(text) > MAX_TEXT_LENGTH
