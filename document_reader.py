
from io import BytesIO
from pypdf import PdfReader


def read_pdf(uploaded_file):
    """
    Extract readable text from an uploaded PDF.
    Returns a dictionary containing the filename, page count,
    extracted text, and file size.
    """

    if uploaded_file is None:
        raise ValueError("Please upload a PDF document.")

    filename = uploaded_file.name

    if not filename.lower().endswith(".pdf"):
        raise ValueError(f"{filename} is not a PDF file.")

    pdf_bytes = uploaded_file.getvalue()

    if not pdf_bytes:
        raise ValueError(f"{filename} is empty.")

    try:
        reader = PdfReader(BytesIO(pdf_bytes))

        if reader.is_encrypted:
            try:
                if reader.decrypt("") == 0:
                    raise ValueError(
                        f"{filename} is password-protected. "
                        "Please upload an unlocked PDF."
                    )
            except Exception as exc:
                if isinstance(exc, ValueError):
                    raise
                raise ValueError(
                    f"{filename} is password-protected. "
                    "Please upload an unlocked PDF."
                ) from exc

        page_texts = []

        for page_number, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""

            text = text.strip()

            if text:
                page_texts.append(
                    f"[Page {page_number}]\n{text}"
                )

        full_text = "\n\n".join(page_texts).strip()

        if not full_text:
            raise ValueError(
                f"No readable text was found in {filename}. "
                "The PDF may contain scanned images. "
                "Please try a text-based PDF."
            )

        return {
            "filename": filename,
            "page_count": len(reader.pages),
            "text": full_text,
            "file_size": len(pdf_bytes),
            "character_count": len(full_text),
        }

    except ValueError:
        raise

    except Exception as exc:
        raise ValueError(
            f"Could not read {filename}. "
            "Please check that the PDF is valid and not damaged."
        ) from exc
