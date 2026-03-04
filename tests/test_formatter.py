import pytest

from core.formatter import (
    format_for_telegram,
    plain_text_fallback,
    _escape_markdown_v2,
    _split_message,
)


def test_empty_input():
    assert format_for_telegram("") == [""]


def test_plain_text_escaped():
    result = format_for_telegram("Hello world.")
    assert result == ["Hello world\\."]


def test_headers_become_bold():
    result = format_for_telegram("## My Header")
    assert result == ["*My Header*"]


def test_code_block_preserved():
    text = "```python\nprint('hello')\n```"
    result = format_for_telegram(text)
    assert "```python" in result[0]
    assert "print('hello')" in result[0]


def test_inline_code_preserved():
    result = format_for_telegram("Use `pip install` to install")
    assert "`pip install`" in result[0]


def test_bold_converted():
    result = format_for_telegram("This is **bold** text")
    # **bold** in Claude markdown becomes *bold* in Telegram MarkdownV2
    assert "*bold*" in result[0]


def test_link_preserved():
    result = format_for_telegram("Visit [Google](https://google.com)")
    assert "[Google](https://google.com)" in result[0]


def test_split_long_message():
    chunks = _split_message("a" * 5000, max_length=4096)
    assert len(chunks) == 2
    assert all(len(c) <= 4096 for c in chunks)


def test_split_at_newline():
    text = "line1\n" * 1000
    chunks = _split_message(text, max_length=100)
    assert all(len(c) <= 100 for c in chunks)


def test_escape_special_chars():
    result = _escape_markdown_v2("hello_world (test) [1+2=3]")
    assert "\\_" in result
    assert "\\(" in result
    assert "\\+" in result
    assert "\\=" in result


def test_plain_text_fallback():
    text = "**Bold** and `code` and [link](http://x.com)"
    result = plain_text_fallback(text)
    assert "Bold" in result[0]
    assert "code" in result[0]
    assert "link" in result[0]
    assert "**" not in result[0]
    assert "`" not in result[0]
