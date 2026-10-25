"""Build templates/WellCare Consent Form.pdf from a filled WellCare consent form.

    python tools/make_consent_template.py "Consent Form - SOME CLIENT.pdf"

The WellCare form has no fields: the client's name and the date are printed on the page.
This removes those printed values (the text itself, so no client's name stays in the file),
draws three more name / signature / date rows, and adds fillable fields that
fill_consent.py fills and flattens.
"""
import re
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (ArrayObject, BooleanObject, ContentStream, DecodedStreamObject, DictionaryObject,
                           FloatObject, NameObject, NumberObject, TextStringObject)

OUT = Path(__file__).resolve().parent.parent / "templates" / "WellCare Consent Form.pdf"
H = 792                      # page height; positions below are measured from the top (as pdfplumber gives them)
ROW_LINES = [542.6, 568.6, 594.6, 620.6]           # underline of each name / signature / date row
COLUMNS = [(44.0, 233.1), (243.1, 453.2), (463.2, 558.0)]
FIELDS = {                                          # name: (x0, x1, underline top)
    "Client(s) Name": (75.0, 330.0, 143.6),
    "Date1_af_date": (73.0, 239.0, 456.9),
    **{f"Name {i}": (46.0, 231.0, y) for i, y in enumerate(ROW_LINES, 1)},
}


def text_of(operands):
    """The characters drawn by a Tj / TJ operation (this form uses 1-byte codes = ASCII)."""
    parts = operands[0] if isinstance(operands[0], list) else [operands[0]]
    return "".join(p.decode("latin-1") if isinstance(p, bytes) else str(p) if not isinstance(p, (int, float)) else ""
                   for p in parts)


def main(sample):
    reader = PdfReader(sample)
    writer = PdfWriter(clone_from=reader)
    page = writer.pages[0]
    name = re.search(r"AND:\s*(.+?)\s*\(the", page.extract_text()).group(1).strip()
    date = re.search(r"Date:\s*(\w+ \d{1,2}, \d{4})", page.extract_text()).group(1)

    content = ContentStream(page.get_contents(), writer)
    removed = []
    for op in content.operations:
        operands, operator = op
        if operator in (b"Tj", b"TJ"):
            shown = re.sub(r"\s+", " ", text_of(operands)).strip()
            if shown and (shown in (name, date) or shown in name.split() or shown in date.split()):
                op[0][0] = ArrayObject() if operator == b"TJ" else TextStringObject("")
                removed.append(shown)
    page[NameObject("/Contents")] = content
    left = page.extract_text()
    if name in left or date in left:
        sys.exit(f"Could not remove the printed values (removed {removed}) - not writing a template.")

    # three more rows: underlines under name / signature / date (row 1 is already on the form)
    lines = "q 0 0 0 RG 0.6 w\n" + "".join(f"{x0} {H - y} m {x1} {H - y} l S\n"
                                         for y in ROW_LINES[1:] for x0, x1 in COLUMNS) + "Q\n"
    extra = DecodedStreamObject()
    extra.set_data(lines.encode())
    page[NameObject("/Contents")] = ArrayObject([
        writer._add_object(_stream(b"q\n")), writer._add_object(page["/Contents"]) if not hasattr(
            page["/Contents"], "indirect_reference") or page["/Contents"].indirect_reference is None
        else page["/Contents"].indirect_reference,
        writer._add_object(_stream(b"Q\n")), writer._add_object(extra)])

    font = writer._add_object(DictionaryObject({
        NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Times-Roman"), NameObject("/Encoding"): NameObject("/WinAnsiEncoding")}))
    fields = ArrayObject()
    for field, (x0, x1, line) in FIELDS.items():
        widget = writer._add_object(DictionaryObject({
            NameObject("/Type"): NameObject("/Annot"), NameObject("/Subtype"): NameObject("/Widget"),
            NameObject("/FT"): NameObject("/Tx"), NameObject("/T"): TextStringObject(field),
            NameObject("/Rect"): ArrayObject([FloatObject(x0), FloatObject(H - line + 1),
                                              FloatObject(x1), FloatObject(H - line + 13)]),
            NameObject("/F"): NumberObject(4), NameObject("/DA"): TextStringObject("/TiRo 9 Tf 0 g"),
            NameObject("/P"): page.indirect_reference}))
        fields.append(widget)
    page[NameObject("/Annots")] = ArrayObject(list(page.get("/Annots", [])) + list(fields))
    writer._root_object[NameObject("/AcroForm")] = DictionaryObject({
        NameObject("/Fields"): fields, NameObject("/NeedAppearances"): BooleanObject(True),
        NameObject("/DA"): TextStringObject("/TiRo 9 Tf 0 g"),
        NameObject("/DR"): DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/TiRo"): font})})})
    # plain metadata (the sample's entries point at objects that don't survive copying)
    writer._info = writer._add_object(DictionaryObject({
        NameObject("/Title"): TextStringObject("WellCare Personal Information Client Consent Form"),
        NameObject("/Producer"): TextStringObject("Client Intake")}))
    with open(OUT, "wb") as f:
        writer.write(f)
    print(f"{OUT}  (removed: {removed})")


def _stream(data):
    s = DecodedStreamObject()
    s.set_data(data)
    return s


if __name__ == "__main__":
    main(sys.argv[1])
