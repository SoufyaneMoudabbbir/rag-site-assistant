"""Turn web pages, PDFs and text files into chunks ready for embedding.

A chunk is one self-contained passage (a product card, a FAQ entry, a section
under a heading) prefixed with its page title and heading, so it still makes
sense when retrieved on its own.
"""

import io
import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag
from pypdf import PdfReader

# Small passages keep each fact sharp: a price inside a long section gets diluted otherwise.
MAX_CHUNK_CHARS = 400
OVERLAP_CHARS = 100
MIN_CHUNK_CHARS = 12  # short facts ("Horaires : 9h-18h") matter too

USER_AGENT = "Mozilla/5.0 (compatible; SiteAssistantBot/1.0)"


@dataclass
class Chunk:
    heading: str
    text: str
    url: str | None = None


@dataclass
class Product:
    name: str
    price: str | None = None
    currency: str | None = None
    image: str | None = None
    url: str | None = None
    description: str | None = None


@dataclass
class ParsedDocument:
    title: str
    kind: str  # page | pdf | text
    chunks: list[Chunk]
    products: list[Product] = field(default_factory=list)

    @property
    def chars(self) -> int:
        return sum(len(c.text) for c in self.chunks)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_long(text: str) -> list[str]:
    """Split text longer than MAX_CHUNK_CHARS on sentence boundaries, with overlap."""
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    parts, current = [], ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > MAX_CHUNK_CHARS:
            parts.append(current)
            current = current[-OVERLAP_CHARS:].split(" ", 1)[-1] + " " + sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        parts.append(current)
    return parts


def _make_chunks(title: str, heading: str, body: str, url: str | None) -> list[Chunk]:
    body = _clean(body)
    if len(body) < MIN_CHUNK_CHARS:
        return []
    label = f"{title} — {heading}" if heading and heading != title else title
    return [Chunk(heading=heading or title, text=f"{label}\n{part}", url=url) for part in split_long(body)]


# ---------------------------------------------------------------- products


def _ld_nodes(data):
    """Every JSON object in a JSON-LD block, including @graph and ItemList entries."""
    if isinstance(data, list):
        for item in data:
            yield from _ld_nodes(item)
    elif isinstance(data, dict):
        yield data
        for value in data.values():
            if isinstance(value, (dict, list)):
                yield from _ld_nodes(value)


def _first(value):
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        value = value.get("url") or value.get("contentUrl")
    return value if isinstance(value, str) else None


def extract_products(soup: BeautifulSoup, base_url: str) -> list[Product]:
    """Products described with schema.org JSON-LD, as Shopify, WooCommerce and most
    shop platforms publish them: name, price, photo and link."""
    products: dict[str, Product] = {}
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except ValueError:
            continue
        for node in _ld_nodes(data):
            types = node.get("@type")
            if "Product" not in (types if isinstance(types, list) else [types]) or not node.get("name"):
                continue
            offer = node.get("offers") or {}
            if isinstance(offer, list):
                offer = offer[0] if offer else {}
            price = offer.get("price") or offer.get("lowPrice")
            image, link = _first(node.get("image")), _first(node.get("url"))
            name = _clean(str(node["name"]))
            products[name.lower()] = Product(
                name=name,
                price=str(price) if price is not None else None,
                currency=offer.get("priceCurrency"),
                image=urljoin(base_url, image) if image else None,
                url=urljoin(base_url, link) if link else base_url,
                description=_clean(str(node.get("description") or ""))[:300] or None,
            )
    return list(products.values())


# ---------------------------------------------------------------- HTML


def parse_html(html: str, url: str) -> ParsedDocument:
    soup = BeautifulSoup(html, "html.parser")
    products = extract_products(soup, url)  # before scripts are stripped below
    for tag in soup(["script", "style", "noscript", "svg", "nav", "header", "footer", "form", "iframe", "template"]):
        tag.decompose()
    for tag in soup.select(".demo-banner, [aria-hidden='true'], [hidden]"):
        tag.decompose()

    title = _clean(soup.title.get_text()) if soup.title else urlparse(url).path or url
    title = re.split(r"\s+[·|–-]\s+", title)[0] or title
    root = soup.find("main") or soup.body or soup
    chunks: list[Chunk] = []

    def anchor_url(el: Tag) -> str:
        holder = el if el.get("id") else el.find_parent(attrs={"id": True})
        return f"{url}#{holder['id']}" if holder is not None and holder.get("id") else url

    # Self-contained blocks first: product cards and FAQ entries.
    for block in root.find_all(["article", "details"]):
        head = block.find(["summary", "h1", "h2", "h3", "h4"])
        heading = _clean(head.get_text()) if head else title
        chunks += _make_chunks(title, heading, block.get_text(" "), anchor_url(block))
        block.decompose()

    # Everything else: sections delimited by headings.
    heading, heading_url, buffer = title, url, []

    def flush():
        if buffer:
            chunks.extend(_make_chunks(title, heading, " ".join(buffer), heading_url))
            buffer.clear()

    for el in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "tr", "dt", "dd", "blockquote"]):
        if el.name in ("h1", "h2", "h3", "h4"):
            flush()
            heading, heading_url = _clean(el.get_text()), anchor_url(el)
        elif el.name == "tr":
            buffer.append(" | ".join(_clean(c.get_text()) for c in el.find_all(["td", "th"])) + ".")
        elif not el.find_parent(["p", "li", "blockquote"]):
            buffer.append(el.get_text(" "))
    flush()
    return ParsedDocument(title=title, kind="page", chunks=chunks, products=products)


async def fetch_page(url: str) -> ParsedDocument:
    if urlparse(url).scheme not in ("http", "https"):
        raise ValueError("Only http(s) URLs can be imported")
    async with httpx.AsyncClient(follow_redirects=True, timeout=20, headers={"User-Agent": USER_AGENT}) as client:
        resp = await client.get(url)
    resp.raise_for_status()
    if "html" not in resp.headers.get("content-type", "html"):
        raise ValueError("This URL is not an HTML page")
    return parse_html(resp.text, str(resp.url))


def same_site_links(html: str, base_url: str, limit: int = 30) -> list[str]:
    """Internal links of a page, used to import a whole small site from its homepage."""
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(base_url).netloc
    seen: list[str] = []
    for a in soup.find_all("a", href=True):
        link = urljoin(base_url, a["href"]).split("#")[0]
        if urlparse(link).netloc == host and link not in seen and not re.search(r"\.(pdf|jpe?g|png|zip)$", link, re.I):
            seen.append(link)
    return seen[:limit]


# ---------------------------------------------------------------- PDF and text


def parse_pdf(data: bytes, filename: str) -> ParsedDocument:
    reader = PdfReader(io.BytesIO(data))
    title = (reader.metadata.title if reader.metadata and reader.metadata.title else None) or filename
    chunks: list[Chunk] = []
    for number, page in enumerate(reader.pages, start=1):
        chunks += _make_chunks(title, f"page {number}", page.extract_text() or "", None)
    return ParsedDocument(title=title, kind="pdf", chunks=chunks)


def parse_text(text: str, filename: str) -> ParsedDocument:
    """Plain text or Markdown: Markdown headings start new chunks, otherwise paragraphs."""
    title, chunks = filename, []
    heading, buffer = filename, []
    for line in text.splitlines():
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            chunks += _make_chunks(title, heading, " ".join(buffer), None)
            heading, buffer = m.group(2).strip(), []
            if m.group(1) == "#" and title == filename:
                title = heading
        elif line.strip():
            buffer.append(line.strip())
        else:
            buffer.append("\n")
    chunks += _make_chunks(title, heading, " ".join(buffer), None)
    return ParsedDocument(title=title, kind="text", chunks=chunks)


def parse_upload(data: bytes, filename: str) -> ParsedDocument:
    name = filename.lower()
    if name.endswith(".pdf"):
        return parse_pdf(data, filename)
    text = data.decode("utf-8", errors="replace")
    if name.endswith((".html", ".htm")):
        return parse_html(text, filename)
    return parse_text(text, filename)
