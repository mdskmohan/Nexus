"""Research tools over one matter's documents, shared by every agent.

Every tool is bound to a single matter when it is built. There is no
parameter through which the model could reach another matter, and the
database would refuse another firm's rows even if there were.
"""

from nexus import search as search_index
from nexus.agents.base import Agent, Tool, ToolError, ToolOutcome, dumps, passage_ref, valid_uuid
from nexus.db import rows

MAX_READ = 8


def _quote(text: str, limit: int = 60) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def matter_tools(agent: Agent, only_document: str | None = None) -> list[Tool]:
    """`only_document` pins every tool to one document (used by contract review)."""
    seen: dict[str, dict] = {}
    agent.seen_passages = seen  # type: ignore[attr-defined]

    def remember(found: list[dict]) -> None:
        for p in found:
            seen[str(p["id"])] = p

    def list_documents(_: dict) -> ToolOutcome:
        with agent.session() as s:
            docs = rows(
                s,
                """SELECT d.id, d.filename, d.page_count, d.status,
                          (SELECT count(*) FROM passages p WHERE p.document_id = d.id) AS passages
                   FROM documents d WHERE d.matter_id = :m
                   ORDER BY d.created_at""",
                m=agent.matter_id,
            )
        if only_document:
            docs = [d for d in docs if str(d["id"]) == only_document]
        listing = [
            {"document_id": str(d["id"]), "name": d["filename"], "pages": d["page_count"],
             "passages": d["passages"], "status": d["status"]}
            for d in docs
        ]
        return ToolOutcome(dumps(listing), f"Looked at the list of documents ({len(listing)}).",
                           kind="read")

    def search(args: dict) -> ToolOutcome:
        query = (args.get("query") or "").strip()
        if not query:
            raise ToolError("Give a search query.")
        document_id = only_document or args.get("document_id")
        if document_id:
            valid_uuid(document_id, "document")
        with agent.session() as s:
            found = search_index.search(s, agent.matter_id, query, document_id, limit=8)
        remember(found)
        names = sorted({p["filename"] for p in found})
        title = (f"Searched for “{_quote(query)}”. {len(found)} passage"
                 f"{'s' if len(found) != 1 else ''} found"
                 + (f" in {', '.join(names)}." if names else "."))
        return ToolOutcome(dumps([passage_ref(p) for p in found]) if found else
                           "No passages matched. Try different wording or a synonym.",
                           title, kind="search",
                           detail={"passages": [str(p["id"]) for p in found]})

    def read(args: dict) -> ToolOutcome:
        document_id = only_document or valid_uuid(args.get("document_id"), "document")
        start = max(0, int(args.get("start_position", 0)))
        count = min(MAX_READ, max(1, int(args.get("count", 4))))
        with agent.session() as s:
            found = search_index.passages_by_position(s, agent.matter_id, document_id, start, count)
        if not found:
            raise ToolError("No passages at that position. Positions start at 0; check the document's passage count.")
        remember(found)
        pages = sorted({p["page"] for p in found})
        where = f"page {pages[0]}" if len(pages) == 1 else f"pages {pages[0]}–{pages[-1]}"
        return ToolOutcome(dumps([passage_ref(p) for p in found]),
                           f"Read {found[0]['filename']}, {where}.", kind="read",
                           detail={"passages": [str(p["id"]) for p in found]})

    doc_param = {} if only_document else {
        "document_id": {"type": "string",
                        "description": "Limit to one document (its document_id), or \"\" for all documents."}
    }
    return [
        Tool(
            "list_documents",
            "List the documents in this matter with their ids and sizes.",
            {"type": "object", "properties": {}, "required": []},
            list_documents,
        ),
        Tool(
            "search",
            "Keyword search over the matter's documents. Returns the best-matching passages with "
            "their passage_id, document, page and full text. Search several times with different "
            "wording (synonyms, defined terms, clause names) before concluding something is absent.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Words to search for."},
                    **doc_param,
                },
                "required": ["query"] if only_document else ["query", "document_id"],
            },
            search,
        ),
        Tool(
            "read",
            "Read consecutive passages of one document, starting at a position (0-based). Use it "
            "to read around a search hit, or to read a whole document in order.",
            {
                "type": "object",
                "properties": {
                    **({} if only_document else {
                        "document_id": {"type": "string", "description": "The document's id."}}),
                    "start_position": {"type": "integer", "description": "First passage position, 0-based."},
                    "count": {"type": "integer", "description": f"How many passages (1-{MAX_READ})."},
                },
                "required": (["start_position", "count"] if only_document
                             else ["document_id", "start_position", "count"]),
            },
            read,
        ),
    ]


def matter_context(agent: Agent) -> str:
    """Firm preferences and matter details, for the system prompt."""
    with agent.session() as s:
        info = rows(
            s,
            """SELECT f.name AS firm, f.preferences, m.name AS matter, m.client_name, m.description
               FROM matters m JOIN firms f ON f.id = m.firm_id WHERE m.id = :m""",
            m=agent.matter_id,
        )[0]
    lines = [f"Firm: {info['firm']}", f"Matter: {info['matter']}"]
    if info["client_name"]:
        lines.append(f"Client: {info['client_name']}")
    if info["description"]:
        lines.append(f"About the matter: {info['description']}")
    if info["preferences"].strip():
        lines.append("Firm preferences (set by the firm; follow them unless they conflict with the "
                     f"rules above):\n{info['preferences'].strip()}")
    return "\n".join(lines)
