"""Ask: answers underwriting questions from the knowledge notes (Claude API).

The notes (a folder of .md files) become the system prompt, cached so follow-up
questions only pay for the new text. The selected client's record can be added to
a question; it goes in the user message so the cached notes stay unchanged.
"""
from pathlib import Path

import anthropic

import eligibility
import records

MODEL = "claude-opus-5-5"
DEFAULT_NOTES = Path.home() / "Documents" / "Docs" / "Insurance" / "Underwriting Knowledge"

INSTRUCTIONS = """You help a RIBO Level 1 insurance broker at WellCare Insurance in Ontario. They quote in \
Applied Rating Service, bind in PowerBroker, and pull DASH and MVR reports. They ask about carrier eligibility, \
underwriting rules, endorsements, discounts, payments and processing for the carriers in the notes below \
(Intact, Jevco, Pafco, Pembridge, Echelon and others), and about WellCare's own refer rules.

Answer from the notes. Name the note and section you used, so the broker can check the source manual. \
WellCare's in-house refer rules apply on top of every carrier's rules: mention them when they change the answer. \
When the notes do not cover something, or a rule needs judgment (borderline records, anything outside binding \
authority), say so plainly and tell them to confirm with the underwriter or the principal broker; you can add \
general Ontario insurance knowledge, but label it as not from the notes.

When a client record is attached, apply the rules to that client and say which facts you relied on and which \
are missing. Keep answers short and practical: the verdict or answer first, then the reasons. The answer is \
guidance for a licensed broker, not advice to send to a client as-is.

The answer is shown as plain text, so don't use Markdown: no asterisks, # headings or tables. Use short \
paragraphs and lines starting with "- " for lists.

The notes:"""


def notes_dir(cfg):
    return Path(cfg.get("knowledge_dir") or DEFAULT_NOTES)


def load_notes(folder):
    """[(file name, text)] for every .md note, in name order (stable, so the cache keeps hitting)."""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return [(p.name, p.read_text(encoding="utf-8-sig")) for p in sorted(folder.glob("*.md"))]


def system_prompt(notes):
    parts = [INSTRUCTIONS]
    for name, text in notes:
        parts.append(f'<note file="{name}">\n{text.strip()}\n</note>')
    return [{"type": "text", "text": "\n\n".join(parts), "cache_control": {"type": "ephemeral"}}]


def client_context(folder, client_type=""):
    """Plain-text summary of one client: records, DASH facts and documents on file."""
    folder = Path(folder)
    lines = [f"Client: {folder.name}" + (f" ({client_type} folder)" if client_type else "")]
    data = records.load(folder)
    for kind, spec in records.KINDS.items():
        if not data[kind]:
            continue
        labels = {key: label for key, label, *_ in spec["fields"]}
        lines.append(f"\n{spec['title']}:")
        for item in data[kind]:
            vals = [f"{labels[k]}: {item[k]}" for k in labels if item.get(k) not in (None, "", False)]
            lines.append("- " + "; ".join(vals))
    dash = sorted(folder.glob("DASH Report*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    if dash:
        try:
            facts, _, notes = eligibility.read_dash_facts(dash[0])
            lines.append(f"\nFrom the DASH report ({dash[0].name}):")
            lines += [f"- {eligibility.FACTS[k]}: {v}" for k, v in facts.items()
                      if v is not None and k in eligibility.FACTS]
            lines += [f"- Note: {n}" for n in notes]
        except Exception as e:
            lines.append(f"\nDASH report could not be read: {e}")
    docs = sorted(p.name for p in folder.glob("*.pdf"))
    if docs:
        lines.append("\nDocuments in the folder: " + ", ".join(docs))
    if len(lines) == 1:
        lines.append("No records, DASH report or documents on file yet.")
    return "\n".join(lines)


class Chat:
    """One conversation. Not thread-safe: run ask() on one background thread at a time."""

    def __init__(self, api_key, notes):
        self.client = anthropic.Anthropic(api_key=api_key or None)  # None: use ANTHROPIC_API_KEY
        self.system = system_prompt(notes)
        self.messages = []

    def ask(self, question, on_text, context=None):
        """Stream the answer, calling on_text(chunk). Returns the final message.

        The question and answer are added to the history only when the answer is complete,
        so a failed or declined request can simply be asked again.
        """
        content = f"<client_record>\n{context}\n</client_record>\n\n{question}" if context else question
        turn = {"role": "user", "content": content}
        with self.client.beta.messages.stream(
            model=MODEL,
            max_tokens=16000,
            system=self.system,
            messages=self.messages + [turn],
            output_config={"effort": "medium"},
            cache_control={"type": "ephemeral"},   # also cache the conversation so far
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",                   # retry a safety decline on another model
        ) as stream:
            for text in stream.text_stream:
                on_text(text)
            final = stream.get_final_message()
        if final.stop_reason != "refusal":
            # keep the whole content (thinking and fallback blocks too): the API expects it back unchanged
            self.messages += [turn, {"role": "assistant", "content": final.content}]
        return final
