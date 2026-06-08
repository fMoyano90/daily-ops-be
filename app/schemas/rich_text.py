from typing import Any
from uuid import UUID

from pydantic import BaseModel


ALLOWED_NODE_TYPES = {
    "doc",
    "paragraph",
    "text",
    "heading",
    "bulletList",
    "orderedList",
    "listItem",
    "hardBreak",
    "blockquote",
    "codeBlock",
    "image",
}
ALLOWED_MARK_TYPES = {"bold", "italic", "code", "link", "strike", "underline"}
ALLOWED_LINK_PREFIXES = ("http://", "https://")
ALLOWED_URI_SCHEMES = ("mailto:", "tel:", "#")


def validate_rich_text_doc(value: Any) -> Any:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("description_doc must be an object")
    _validate_node(value)
    return _clean_node(value)


def _clean_node(node: dict[str, Any]) -> dict[str, Any]:
    next_node = dict(node)
    if node.get("type") == "image":
        attrs = node.get("attrs") or {}
        next_node["attrs"] = {
            key: attrs[key]
            for key in ("attachmentId", "alt", "title")
            if key in attrs and attrs[key] is not None
        }
    if isinstance(node.get("content"), list):
        next_node["content"] = [_clean_node(child) for child in node["content"] if isinstance(child, dict)]
    return next_node


def _validate_node(node: dict[str, Any]) -> None:
    node_type = node.get("type")
    if node_type not in ALLOWED_NODE_TYPES:
        raise ValueError(f"Unsupported rich text node: {node_type}")

    attrs = node.get("attrs")
    if attrs is not None and not isinstance(attrs, dict):
        raise ValueError("Rich text attrs must be an object")

    if node_type == "link":
        raise ValueError("Links must be marks, not nodes")

    if node_type == "image":
        attachment_id = (attrs or {}).get("attachmentId")
        if not attachment_id or not isinstance(attachment_id, str):
            raise ValueError("Images must reference an attachmentId")

    marks = node.get("marks") or []
    if not isinstance(marks, list):
        raise ValueError("Rich text marks must be a list")
    for mark in marks:
        if not isinstance(mark, dict):
            raise ValueError("Rich text mark must be an object")
        mark_type = mark.get("type")
        if mark_type not in ALLOWED_MARK_TYPES:
            raise ValueError(f"Unsupported rich text mark: {mark_type}")
        if mark_type == "link":
            href = ((mark.get("attrs") or {}).get("href") or "").strip()
            if not href:
                continue
            if href.startswith(ALLOWED_LINK_PREFIXES + ALLOWED_URI_SCHEMES):
                continue
            if "://" in href:
                raise ValueError("Links must start with http:// or https://")
            mark.setdefault("attrs", {})["href"] = "https://" + href

    content = node.get("content") or []
    if not isinstance(content, list):
        raise ValueError("Rich text content must be a list")
    for child in content:
        if not isinstance(child, dict):
            raise ValueError("Rich text child must be an object")
        _validate_node(child)


def rich_text_to_plain_text(doc: Any) -> str | None:
    if not isinstance(doc, dict):
        return None
    parts: list[str] = []
    _collect_plain_text(doc, parts)
    text = "".join(parts)
    return text.strip() or None


def _collect_plain_text(node: dict[str, Any], parts: list[str]) -> None:
    node_type = node.get("type")
    if node_type == "text":
        parts.append(str(node.get("text") or ""))
        return
    if node_type == "image":
        alt = ((node.get("attrs") or {}).get("alt") or "imagen").strip()
        parts.append(f"[{alt}]")
        return
    for child in node.get("content") or []:
        if isinstance(child, dict):
            _collect_plain_text(child, parts)
    if node_type in {"paragraph", "heading", "listItem"}:
        parts.append("\n")


def plain_text_to_rich_text(text: str | None) -> dict[str, Any] | None:
    if not text or not text.strip():
        return None
    paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
    return {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": paragraph}]}
            for paragraph in paragraphs
        ],
    }


class RichTextAttachmentResponse(BaseModel):
    id: UUID
    kind: str
    file_name: str
    mime_type: str
    size_bytes: int

    model_config = {"from_attributes": True}
