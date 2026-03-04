import re

TELEGRAM_MAX_LENGTH = 4096

# Characters that need escaping in MarkdownV2 (outside code blocks)
_ESCAPE_CHARS = r"_*[]()~`>#\+\-=|{}.!"


def _escape_markdown_v2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2, preserving formatting."""
    return re.sub(r"([_*\[\]()~`>#\+\-=|{}.!\\])", r"\\\1", text)


def format_for_telegram(text: str) -> list[str]:
    """Convert Claude's markdown to Telegram MarkdownV2 and split if needed.

    Returns a list of message chunks, each within Telegram's 4096 char limit.
    """
    if not text:
        return [""]

    lines = text.split("\n")
    result_lines = []
    in_code_block = False

    for line in lines:
        # Track code blocks
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            result_lines.append(line)
            continue

        if in_code_block:
            # Don't escape inside code blocks
            result_lines.append(line)
            continue

        # Convert headers to bold
        header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if header_match:
            header_text = _escape_markdown_v2(header_match.group(2))
            result_lines.append(f"*{header_text}*")
            continue

        # Process inline elements
        processed = _process_inline(line)
        result_lines.append(processed)

    full_text = "\n".join(result_lines)
    return _split_message(full_text)


def _process_inline(line: str) -> str:
    """Process inline formatting, escaping non-format characters."""
    parts = []
    i = 0

    while i < len(line):
        # Inline code
        if line[i] == "`" and not (i > 0 and line[i - 1] == "\\"):
            end = line.find("`", i + 1)
            if end != -1:
                parts.append(line[i : end + 1])  # Keep inline code as-is
                i = end + 1
                continue

        # Bold **text**
        if line[i : i + 2] == "**":
            end = line.find("**", i + 2)
            if end != -1:
                inner = _escape_markdown_v2(line[i + 2 : end])
                parts.append(f"*{inner}*")
                i = end + 2
                continue

        # Links [text](url)
        link_match = re.match(r"\[([^\]]+)\]\(([^)]+)\)", line[i:])
        if link_match:
            text = _escape_markdown_v2(link_match.group(1))
            url = link_match.group(2)
            parts.append(f"[{text}]({url})")
            i += link_match.end()
            continue

        # Regular character — escape if special
        if line[i] in "_*[]()~`>#+-=|{}.!\\":
            parts.append(f"\\{line[i]}")
        else:
            parts.append(line[i])
        i += 1

    return "".join(parts)


def _split_message(text: str, max_length: int = TELEGRAM_MAX_LENGTH) -> list[str]:
    """Split a message into chunks that fit within Telegram's limit."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        # Try to split at a newline
        split_at = text.rfind("\n", 0, max_length)
        if split_at == -1 or split_at < max_length // 2:
            # Fall back to splitting at space
            split_at = text.rfind(" ", 0, max_length)
        if split_at == -1:
            split_at = max_length

        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")

    return chunks


def plain_text_fallback(text: str) -> list[str]:
    """Strip all markdown and return plain text chunks. Used when MarkdownV2 parsing fails."""
    # Remove markdown formatting
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # Bold
    text = re.sub(r"\*(.+?)\*", r"\1", text)  # Italic
    text = re.sub(r"`{3}[\w]*\n?", "", text)  # Code block markers
    text = re.sub(r"`(.+?)`", r"\1", text)  # Inline code
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)  # Links
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # Headers
    return _split_message(text)
