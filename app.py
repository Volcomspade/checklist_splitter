
import streamlit as st
import fitz  # PyMuPDF
import io
import zipfile
import re

st.set_page_config(page_title="Checklist PDF Splitter", layout="wide")
st.title("📄 Checklist PDF Splitter")

uploaded_file = st.file_uploader("Upload Checklist Report PDF", type=["pdf"])

def clean_text(text):
    return text.replace("Checklist Details", "").strip()

def remove_footer_and_header(page):
    blocks = page.get_text("blocks")
    for b in blocks:
        text = b[4]
        if "Checklist Details" in text:
            page.add_redact_annot(fitz.Rect(b[:4]), fill=(1, 1, 1))
        elif "Report run on" in text and "@rosendin.com" in text:
            page.add_redact_annot(fitz.Rect(b[:4]), fill=(1, 1, 1))
    page.apply_redactions()

if uploaded_file:
    pdf_bytes = uploaded_file.read()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    checklist_files = []
    checklist_name = None
    checklist_pages = []

    for i, page in enumerate(doc):
        text = page.get_text()
        name_match = re.search(r"Name:\s+(.+?)\n", text)

        if name_match:
            if checklist_name and checklist_pages:
                buffer = io.BytesIO()
                writer = fitz.open()
                for p in checklist_pages:
                    writer.insert_pdf(doc, from_page=p, to_page=p)
                writer.save(buffer)
                writer.close()
                checklist_files.append((checklist_name, buffer.getvalue()))

            checklist_name = name_match.group(1).strip()
            checklist_pages = [i]
        else:
            checklist_pages.append(i)

    # Save the last checklist
    if checklist_name and checklist_pages:
        buffer = io.BytesIO()
        writer = fitz.open()
        for p in checklist_pages:
            remove_footer_and_header(doc[p])
            writer.insert_pdf(doc, from_page=p, to_page=p)
        writer.save(buffer)
        writer.close()
        checklist_files.append((checklist_name, buffer.getvalue()))

    st.success(f"Detected {len(checklist_files)} checklists.")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zipf:
        for name, content in checklist_files:
            safe_name = re.sub(r'[\\/*?\"<>|]', "_", name)
            zipf.writestr(f"{safe_name}.pdf", content)

    st.download_button("Download ZIP of Checklists", data=zip_buffer.getvalue(), file_name="CHECKLISTS.ZIP")
