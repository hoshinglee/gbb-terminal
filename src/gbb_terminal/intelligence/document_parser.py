from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser


DOCUMENT_PARSER_VERSION = "sec_html_ixbrl_v3"


class UnsupportedDocumentFormat(ValueError):
    pass


@dataclass(frozen=True)
class ParsedTextBlock:
    text: str
    section: str | None
    start_offset: int
    end_offset: int
    kind: str


@dataclass(frozen=True)
class ParsedXBRLContext:
    context_id: str
    period_start: date | None
    period_end: date | None
    dimensions: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedXBRLFact:
    concept: str
    raw_value: str
    value: float | None
    unit: str | None
    context_id: str
    context: ParsedXBRLContext | None
    decimals: str | None
    start_offset: int
    end_offset: int
    block_index: int | None


@dataclass(frozen=True)
class ParsedEvidenceDocument:
    blocks: list[ParsedTextBlock]
    facts: list[ParsedXBRLFact]
    warnings: list[str] = field(default_factory=list)
    parser_version: str = DOCUMENT_PARSER_VERSION


@dataclass
class _OpenDiv:
    start_offset: int
    content_offset: int
    contains_div: bool = False


class _LeafDivCollector(HTMLParser):
    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=False)
        self.source = source
        self.line_offsets = [0]
        self.line_offsets.extend(match.end() for match in re.finditer(r"\n", source))
        self.stack: list[_OpenDiv] = []
        self.blocks: list[tuple[int, int, str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.casefold() != "div":
            return
        if self.stack:
            self.stack[-1].contains_div = True
        start = self._offset()
        raw_tag = self.get_starttag_text() or ""
        self.stack.append(_OpenDiv(start_offset=start, content_offset=start + len(raw_tag)))

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() != "div" or not self.stack:
            return
        opened = self.stack.pop()
        close_start = self._offset()
        close_end = self.source.find(">", close_start)
        if close_end < 0:
            close_end = close_start
        else:
            close_end += 1
        if not opened.contains_div:
            self.blocks.append(
                (
                    opened.start_offset,
                    close_end,
                    self.source[opened.content_offset:close_start],
                    "div",
                )
            )

    def _offset(self) -> int:
        line, column = self.getpos()
        line_index = max(0, min(line - 1, len(self.line_offsets) - 1))
        return self.line_offsets[line_index] + column


class PublicDocumentParser:
    _attribute_pattern = re.compile(r"([A-Za-z_:][\w:.-]*)\s*=\s*(['\"])(.*?)\2", re.DOTALL)
    _heading_pattern = re.compile(r"<(h[1-6])\b[^>]*>(.*?)</\1\s*>", re.IGNORECASE | re.DOTALL)
    _semantic_block_pattern = re.compile(
        r"<(p|li|tr|blockquote|h[1-6])\b[^>]*>(.*?)</\1\s*>",
        re.IGNORECASE | re.DOTALL,
    )
    _context_pattern = re.compile(
        r"<(?:[A-Za-z_][\w.-]*:)?context\b(?P<attrs>[^>]*)>(?P<body>.*?)"
        r"</(?:[A-Za-z_][\w.-]*:)?context\s*>",
        re.IGNORECASE | re.DOTALL,
    )
    _unit_pattern = re.compile(
        r"<(?:[A-Za-z_][\w.-]*:)?unit\b(?P<attrs>[^>]*)>(?P<body>.*?)"
        r"</(?:[A-Za-z_][\w.-]*:)?unit\s*>",
        re.IGNORECASE | re.DOTALL,
    )
    _inline_fact_pattern = re.compile(
        r"<ix:(?P<tag>nonfraction|nonnumeric)\b(?P<attrs>[^>]*)>(?P<body>.*?)</ix:(?P=tag)\s*>",
        re.IGNORECASE | re.DOTALL,
    )
    _instance_fact_pattern = re.compile(
        r"<(?P<tag>[A-Za-z_][\w.-]*:[A-Za-z_][\w.-]*)\b(?P<attrs>[^>]*\bcontextref\s*=\s*['\"][^'\"]+['\"][^>]*)>"
        r"(?P<body>.*?)</(?P=tag)\s*>",
        re.IGNORECASE | re.DOTALL,
    )

    def parse(self, content: bytes, mime_type: str) -> ParsedEvidenceDocument:
        normalized_mime = mime_type.split(";", 1)[0].strip().casefold()
        if normalized_mime in {"application/pdf", "application/octet-stream"}:
            raise UnsupportedDocumentFormat(f"The deterministic parser does not support {normalized_mime} documents.")
        if normalized_mime not in {
            "text/html",
            "application/xhtml+xml",
            "application/xml",
            "text/xml",
            "text/plain",
        }:
            raise UnsupportedDocumentFormat(f"The deterministic parser does not recognize {normalized_mime} documents.")
        source = self._decode(content)
        if normalized_mime == "text/plain":
            blocks = self._plain_blocks(source)
            return ParsedEvidenceDocument(blocks=blocks, facts=[], warnings=[])
        blocks = self._html_blocks(source)
        contexts = self._contexts(source)
        units = self._units(source)
        facts = self._facts(source, blocks, contexts, units)
        warnings = []
        if not blocks:
            warnings.append("The document parsed without readable narrative blocks.")
        if "ix:" in source.casefold() and not facts:
            warnings.append("Inline XBRL markup was present but no supported facts were parsed.")
        return ParsedEvidenceDocument(blocks=blocks, facts=facts, warnings=warnings)

    @staticmethod
    def _decode(content: bytes) -> str:
        head = content[:2048].decode("ascii", errors="ignore")
        match = re.search(r"charset\s*=\s*['\"]?([A-Za-z0-9_.-]+)", head, re.IGNORECASE)
        encodings = [match.group(1)] if match else []
        encodings.extend(["utf-8", "windows-1252"])
        for encoding in encodings:
            try:
                return content.decode(encoding).replace("\x00", "")
            except (LookupError, UnicodeDecodeError):
                continue
        return content.decode("utf-8", errors="replace").replace("\x00", "")

    def _html_blocks(self, source: str) -> list[ParsedTextBlock]:
        headings = [
            (match.start(), self._text(match.group(2))[:500])
            for match in self._heading_pattern.finditer(source)
            if self._text(match.group(2))
        ]
        matches = [
            (match.start(), match.end(), match.group(2), match.group(1).casefold())
            for match in self._semantic_block_pattern.finditer(source)
        ]
        matches.extend(self._leaf_div_blocks(source))
        matches.sort(key=lambda match: (match[0], match[1] - match[0]))
        blocks: list[ParsedTextBlock] = []
        seen: set[tuple[str, str | None]] = set()
        for start_offset, end_offset, body, kind in matches:
            text = self._text(body)
            if len(text) < 2 or len(text) > 20_000:
                continue
            section = next((label for offset, label in reversed(headings) if offset <= start_offset), None)
            key = (text.casefold(), section)
            if key in seen:
                continue
            seen.add(key)
            blocks.append(
                ParsedTextBlock(
                    text=text,
                    section=section,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    kind=kind,
                )
            )
        if not blocks:
            return self._plain_blocks(self._text(source))
        return blocks

    @staticmethod
    def _leaf_div_blocks(source: str) -> list[tuple[int, int, str, str]]:
        parser = _LeafDivCollector(source)
        parser.feed(source)
        parser.close()
        return parser.blocks

    @staticmethod
    def _plain_blocks(source: str) -> list[ParsedTextBlock]:
        blocks = []
        for match in re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", source, re.DOTALL):
            text = " ".join(match.group(0).split())
            if 2 <= len(text) <= 20_000:
                blocks.append(
                    ParsedTextBlock(
                        text=text,
                        section=None,
                        start_offset=match.start(),
                        end_offset=match.end(),
                        kind="text",
                    )
                )
        return blocks

    def _contexts(self, source: str) -> dict[str, ParsedXBRLContext]:
        contexts = {}
        for match in self._context_pattern.finditer(source):
            attrs = self._attributes(match.group("attrs"))
            context_id = attrs.get("id")
            if not context_id:
                continue
            body = match.group("body")
            start = self._date_tag(body, "startdate")
            end = self._date_tag(body, "enddate") or self._date_tag(body, "instant")
            dimensions = {}
            for member in re.finditer(
                r"<(?:[A-Za-z_][\w.-]*:)?(?:explicitmember|typedmember)\b(?P<attrs>[^>]*)>"
                r"(?P<body>.*?)</(?:[A-Za-z_][\w.-]*:)?(?:explicitmember|typedmember)\s*>",
                body,
                re.IGNORECASE | re.DOTALL,
            ):
                member_attrs = self._attributes(member.group("attrs"))
                axis = member_attrs.get("dimension") or "typed_dimension"
                value = self._text(member.group("body"))
                if value:
                    dimensions[axis] = value
            contexts[context_id] = ParsedXBRLContext(
                context_id=context_id,
                period_start=start,
                period_end=end,
                dimensions=dimensions,
            )
        return contexts

    def _units(self, source: str) -> dict[str, str]:
        units = {}
        for match in self._unit_pattern.finditer(source):
            unit_id = self._attributes(match.group("attrs")).get("id")
            if not unit_id:
                continue
            measures = re.findall(
                r"<(?:[A-Za-z_][\w.-]*:)?measure\b[^>]*>(.*?)</(?:[A-Za-z_][\w.-]*:)?measure\s*>",
                match.group("body"),
                re.IGNORECASE | re.DOTALL,
            )
            normalized = [self._normalize_unit(self._text(value)) for value in measures if self._text(value)]
            units[unit_id] = "/".join(normalized) if normalized else unit_id
        return units

    def _facts(
        self,
        source: str,
        blocks: list[ParsedTextBlock],
        contexts: dict[str, ParsedXBRLContext],
        units: dict[str, str],
    ) -> list[ParsedXBRLFact]:
        matches = [*self._inline_fact_pattern.finditer(source), *self._instance_fact_pattern.finditer(source)]
        matches.sort(key=lambda match: match.start())
        result = []
        seen: set[tuple[str, str, int, int]] = set()
        for match in matches:
            attrs = self._attributes(match.group("attrs"))
            tag = match.groupdict().get("tag") or ""
            if tag.casefold().startswith(("ix:", "xbrli:", "xbrldi:", "link:")):
                continue
            concept = attrs.get("name") or tag
            context_id = attrs.get("contextref")
            if not concept or not context_id:
                continue
            raw_value = self._text(match.group("body"))
            key = (concept.casefold(), context_id, match.start(), match.end())
            if key in seen:
                continue
            seen.add(key)
            block_index = self._containing_block(blocks, match.start(), match.end())
            result.append(
                ParsedXBRLFact(
                    concept=concept,
                    raw_value=raw_value,
                    value=self._number(raw_value, attrs),
                    unit=units.get(attrs.get("unitref", ""), attrs.get("unitref")),
                    context_id=context_id,
                    context=contexts.get(context_id),
                    decimals=attrs.get("decimals"),
                    start_offset=match.start(),
                    end_offset=match.end(),
                    block_index=block_index,
                )
            )
        return result

    @staticmethod
    def _containing_block(blocks: list[ParsedTextBlock], start: int, end: int) -> int | None:
        candidates = [
            (index, block.end_offset - block.start_offset)
            for index, block in enumerate(blocks)
            if block.start_offset <= start and block.end_offset >= end
        ]
        return min(candidates, key=lambda item: item[1])[0] if candidates else None

    @classmethod
    def _attributes(cls, source: str) -> dict[str, str]:
        return {match.group(1).casefold(): html.unescape(match.group(3)) for match in cls._attribute_pattern.finditer(source)}

    @staticmethod
    def _date_tag(source: str, local_name: str) -> date | None:
        match = re.search(
            rf"<(?:[A-Za-z_][\w.-]*:)?{local_name}\b[^>]*>(.*?)</(?:[A-Za-z_][\w.-]*:)?{local_name}\s*>",
            source,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None
        try:
            return date.fromisoformat(PublicDocumentParser._text(match.group(1))[:10])
        except ValueError:
            return None

    @staticmethod
    def _text(source: str) -> str:
        without_hidden = re.sub(r"<(script|style)\b[^>]*>.*?</\1\s*>", " ", source, flags=re.IGNORECASE | re.DOTALL)
        without_tags = re.sub(r"<[^>]+>", " ", without_hidden)
        return " ".join(html.unescape(without_tags).replace("\xa0", " ").split())

    @staticmethod
    def _normalize_unit(value: str) -> str:
        local = value.rsplit(":", 1)[-1]
        return {"usd": "USD", "shares": "shares", "pure": "ratio"}.get(local.casefold(), local)

    @staticmethod
    def _number(raw_value: str, attrs: dict[str, str]) -> float | None:
        if attrs.get("xsi:nil", "").casefold() == "true" or attrs.get("nil", "").casefold() == "true":
            return None
        normalized = raw_value.strip()
        negative_parentheses = normalized.startswith("(") and normalized.endswith(")")
        normalized = normalized.replace(",", "").replace("$", "").replace("%", "").strip("() ")
        if normalized in {"", "—", "-", "–", "n/a", "N/A"}:
            return None
        try:
            value = float(normalized)
        except ValueError:
            return None
        try:
            value *= 10 ** int(attrs.get("scale", "0"))
        except ValueError:
            pass
        if negative_parentheses or attrs.get("sign") == "-":
            value = -abs(value)
        return value
