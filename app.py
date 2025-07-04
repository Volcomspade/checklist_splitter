import streamlit as st
import zipfile
from PyPDF2 import PdfReader, PdfWriter
import io
import re
import unicodedata
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

st.set_page_config(page_title="Checklist PDF Splitter", layout="wide")
st.title("\U0001F4C4 Checklist PDF Splitter")

uploaded_file = st.file_uploader("Upload Checklist Report PDF", type=["pdf"])

def clean_filename(name):
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    name = re.sub(r'[^\w\-\s\.]', '', name)
    name = name.replace(' ', '_')
    return name[:100]

def extract_checklist_titles(pages_text):
    titles = []
    for i, text in enumerate(pages_text):
        if all(field in text for field in ["ID", "Name", "Description", "Company", "Checklist Status"]):
            match = re.search(
                r"Name\s*[:\-]?\s*(.*?)\n(?=(ID|Description|Author|Created On|Tags|Custom Properties|Company|Priority|Status|Location|Equipment Name|Equipment Barcode))",
                text,
                re.IGNORECASE | re.DOTALL
            )
            if match:
                raw_title = match.group(1).strip()
                raw_title = re.sub(
                    r"\s*(ID|Description|Author|Created On|Tags|Custom Properties|Company|Priority|Status|Location|Equipment Name|Equipment Barcode)\s*:?.*",
                    "", raw_title, flags=re.IGNORECASE)
                titles.append((i, raw_title))
    return titles

def overlay_white_footer(page):
    packet = io.BytesIO()
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    can = canvas.Canvas(packet, pagesize=(width, height))
    can.setFillColorRGB(1, 1, 1)
    can.rect(0, 0, width, 90, fill=True, stroke=False)  # Footer
    can.save()
    packet.seek(0)
    overlay_pdf = PdfReader(packet)
    overlay_page = overlay_pdf.pages[0]
    page.merge_page(overlay_page)
    return page

def clean_all_pages(pdf_reader):
    cleaned_pages = []
    for i in range(len(pdf_reader.pages)):
        cleaned_page = overlay_white_footer(pdf_reader.pages[i])
        cleaned_pages.append(cleaned_page)
    return cleaned_pages

if uploaded_file:
    uploaded_file.seek(0)
    file_bytes = uploaded_file.read()
    pdf_reader = PdfReader(io.BytesIO(file_bytes))

    pages_text = [page.extract_text() or "" for page in pdf_reader.pages]

    checklist_titles = extract_checklist_titles(pages_text)

    if checklist_titles:
        st.success(f"Detected {len(checklist_titles)} checklists.")

        start_indices = [idx for idx, _ in checklist_titles]
        end_indices = start_indices[1:] + [len(pages_text)]
        checklist_groups = [
            {"title": clean_filename(title), "start": start, "end": end}
            for (start, title), end in zip(checklist_titles, end_indices)
        ]

        summary_data = []
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            for group in checklist_groups:
                writer = PdfWriter()
                for p in range(group["start"], group["end"]):
                    cleaned_page = overlay_white_footer(pdf_reader.pages[p])
                    writer.add_page(cleaned_page)
                pdf_output = io.BytesIO()
                writer.write(pdf_output)
                filename = f"{group['title']}.pdf"
                zipf.writestr(filename, pdf_output.getvalue())
                summary_data.append({"Checklist Name": group['title'], "Start Page": group['start'] + 1, "End Page": group['end']})

        summary_df = pd.DataFrame(summary_data)
        st.dataframe(summary_df)
        st.download_button("Download ZIP", data=zip_buffer.getvalue(), file_name="Checklist_Split.zip")
    else:
        st.warning("Detected 0 checklists.")
