"""
Sentence-boundary-aware chunking for legal documents.

Strategy:
  1. Clean raw text (strip HTML, normalize whitespace)
  2. Split into paragraphs on double-newlines
  3. Split paragraphs into sentences via regex
  4. Greedily pack sentences into chunks up to CHUNK_SIZE tokens
  5. Overlap = repeat last N sentences from previous chunk (not raw tokens)
  6. Every chunk starts and ends on a complete sentence
"""

import json
import re
import tiktoken
from pathlib import Path

from data_collection.config import RAW_DATA_DIR, BASE_DIR

CHUNKS_DIR = BASE_DIR / "chunks"
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE = 512
OVERLAP_SENTENCES = 2
MIN_CHUNK_TOKENS = 60

ENCODING = tiktoken.encoding_for_model("text-embedding-3-small")

SENTENCE_SPLIT = re.compile(
    r'(?<=[.!?])'            # sentence-ending punctuation (fixed-width lookbehind)
    r'\s+'                   # whitespace after the punctuation
    r'(?=[A-Z0-9"\'\[(§])'  # next sentence starts with uppercase, digit, quote, section sign
)

LEGAL_ABBREVS = {
    "U.S.", "v.", "Id.", "No.", "Nos.", "Cir.", "App.", "Dist.", "Ct.",
    "Rev.", "Stat.", "Supp.", "Ed.", "Vol.", "Sec.", "§.", "Inc.", "Corp.",
    "Ltd.", "Co.", "Jr.", "Sr.", "Dr.", "Mr.", "Mrs.", "Ms.", "Gen.",
    "Gov.", "Rep.", "Sen.", "Prof.", "Dept.", "Div.", "Ch.", "Art.",
    "Amend.", "Fed.", "Reg.", "Cal.", "Tex.", "Ill.", "Fla.", "Pa.",
    "Va.", "Ga.", "Ala.", "Ariz.", "Ark.", "Colo.", "Conn.", "Del.",
    "Haw.", "Ind.", "Kan.", "Ky.", "Md.", "Mich.", "Minn.", "Miss.",
    "Mo.", "Mont.", "Neb.", "Nev.", "Okla.", "Ore.", "Tenn.", "Vt.",
    "Wash.", "Wis.", "Wyo.", "Mass.", "N.Y.", "N.J.", "N.C.", "N.D.",
    "N.H.", "N.M.", "R.I.", "S.C.", "S.D.", "W.Va.", "D.C.",
    "Jan.", "Feb.", "Mar.", "Apr.", "Jun.", "Jul.", "Aug.", "Sep.",
    "Sept.", "Oct.", "Nov.", "Dec.", "cf.", "e.g.", "i.e.", "et al.",
}


def count_tokens(text):
    return len(ENCODING.encode(text, disallowed_special=()))


def split_into_sentences(text):
    """Split text into sentences, respecting legal abbreviations."""
    text = re.sub(r"\n{2,}", " [PARA] ", text)
    text = re.sub(r"\n", " ", text)
    text = re.sub(r"\s{2,}", " ", text)

    raw_sentences = SENTENCE_SPLIT.split(text)

    sentences = []
    buffer = ""

    for raw in raw_sentences:
        raw = raw.strip()
        if not raw:
            continue

        if buffer:
            candidate = buffer + " " + raw
        else:
            candidate = raw

        ends_with_abbrev = False
        words = candidate.rstrip().split()
        if words:
            last_word = words[-1]
            if last_word in LEGAL_ABBREVS or (
                len(last_word) <= 4 and last_word.endswith(".") and last_word[0].isupper()
            ):
                ends_with_abbrev = True

        if ends_with_abbrev:
            buffer = candidate
        else:
            paragraph_parts = candidate.split(" [PARA] ")
            for i, part in enumerate(paragraph_parts):
                part = part.strip()
                if part:
                    sentences.append(part)
            buffer = ""

    if buffer.strip():
        for part in buffer.split(" [PARA] "):
            part = part.strip()
            if part:
                sentences.append(part)

    return sentences


def pack_sentences_into_chunks(sentences, max_tokens=CHUNK_SIZE, overlap_n=OVERLAP_SENTENCES):
    """
    Greedily pack sentences into chunks. Each chunk is a complete set of sentences.
    Overlap by prepending the last N sentences from the previous chunk to the next.
    """
    if not sentences:
        return []

    raw_groups = []
    current_sents = []
    current_tokens = 0

    for sent in sentences:
        sent_tokens = count_tokens(sent)

        if sent_tokens > max_tokens:
            if current_sents:
                raw_groups.append(current_sents)
                current_sents = []
                current_tokens = 0
            raw_groups.append([sent[:max_tokens * 4]])
            continue

        if current_tokens + sent_tokens + 1 > max_tokens:
            raw_groups.append(current_sents)
            current_sents = []
            current_tokens = 0

        current_sents.append(sent)
        current_tokens += sent_tokens + 1

    if current_sents:
        raw_groups.append(current_sents)

    if not raw_groups:
        return []

    chunks = [" ".join(raw_groups[0])]

    for i in range(1, len(raw_groups)):
        overlap_sents = raw_groups[i - 1][-overlap_n:]
        overlap_text = " ".join(overlap_sents)

        body_text = " ".join(raw_groups[i])

        if count_tokens(overlap_text) + count_tokens(body_text) + 1 <= max_tokens + 80:
            chunks.append(overlap_text + " " + body_text)
        else:
            chunks.append(body_text)

    return chunks


def clean_legal_text(text):
    """Normalize legal document text."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"\t", " ", text)
    text = re.sub(r" {3,}", "  ", text)
    text = re.sub(r"\n{4,}", "\n\n", text)
    return text.strip()


def chunk_all_documents():
    """Chunk every JSON doc in raw_data/ and write chunks to chunks/."""
    for old in CHUNKS_DIR.glob("*.json"):
        old.unlink()

    total_chunks = 0
    sources = ["caselaw", "courtlistener", "edgar"]

    for source in sources:
        source_dir = RAW_DATA_DIR / source
        json_files = list(source_dir.glob("*.json"))
        print("[chunker] Processing %d docs from %s..." % (len(json_files), source))

        for fpath in json_files:
            try:
                doc = json.loads(fpath.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            text = doc.get("text", "")
            if not text or len(text) < 100:
                continue

            text = clean_legal_text(text)
            sentences = split_into_sentences(text)
            doc_chunks = pack_sentences_into_chunks(sentences)

            doc_chunks = [c for c in doc_chunks if count_tokens(c) >= MIN_CHUNK_TOKENS]

            for idx, chunk_text in enumerate(doc_chunks):
                chunk_doc = {
                    "id": "%s_chunk_%d" % (doc["id"], idx),
                    "doc_id": doc["id"],
                    "source": doc.get("source", source),
                    "title": doc.get("title", ""),
                    "court": doc.get("court", ""),
                    "date": doc.get("date", doc.get("filing_date", "")),
                    "chunk_index": idx,
                    "total_chunks": len(doc_chunks),
                    "token_count": count_tokens(chunk_text),
                    "text": chunk_text,
                }

                out_path = CHUNKS_DIR / ("%s_chunk_%d.json" % (doc["id"], idx))
                out_path.write_text(
                    json.dumps(chunk_doc, ensure_ascii=False), encoding="utf-8"
                )
                total_chunks += 1

    print("[chunker] Created %d chunks total." % total_chunks)
    return total_chunks


if __name__ == "__main__":
    chunk_all_documents()
