import fitz


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract all text from a PDF file.
    """

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    text = ""

    for page in doc:
        text += page.get_text()

    doc.close()

    return text.strip()