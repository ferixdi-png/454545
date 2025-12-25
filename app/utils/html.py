"""
HTML utilities for safe message formatting in Telegram.

MASTER PROMPT compliance: Security - prevent XSS in HTML messages.
"""
import html


def escape_html(text: str) -> str:
    """
    Escape HTML special characters to prevent XSS.
    
    Use this ALWAYS when inserting user input into HTML-formatted messages.
    
    Args:
        text: User input text
        
    Returns:
        Escaped text safe for HTML
        
    Example:
        >>> escape_html("<script>alert('XSS')</script>")
        "&lt;script&gt;alert('XSS')&lt;/script&gt;"
    """
    if text is None:
        return ""
    return html.escape(str(text), quote=True)


def escape_markdown(text: str) -> str:
    """
    Escape Markdown special characters for MarkdownV2.
    
    Args:
        text: User input text
        
    Returns:
        Escaped text safe for MarkdownV2
    """
    if text is None:
        return ""
    # MarkdownV2 special chars: _*[]()~`>#+-=|{}.!
    special_chars = '_*[]()~`>#+-=|{}.!'
    result = str(text)
    for char in special_chars:
        result = result.replace(char, f'\\{char}')
    return result
