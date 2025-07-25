import streamlit as st
import zipfile
from PyPDF2 import PdfReader, PdfWriter
import io
import re
import unicodedata
import pandas as pd

st.set_page_config(page_title="Checklist PDF Splitter", layout="wide")
st.title("📄 Checklist PDF Splitter")

uploaded_file = st.file_uploader("Upload Checklist Report PDF", type=["pdf"])

def clean_filename(name):
    # Normalize unicode and strip illegal filename characters
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    return re.sub(r'[<>:"/\\|?*]', '', name).strip()


def extract_checklist_metadata(pages_text):
    metadata = []
    for i, text in enumerate(pages_text):
        # Identify the header section by presence of key fields
        if all(field in text for field in ["ID", "Name", "Description", "Company", "Checklist Status"]):
            # Capture the Name field (handles multiline)
            name_match = re.search(
                r"Name\s*[:\-]?\s*([\s\S]+?)\n(?:ID|Description|Author|Created On|Tags|Custom Properties|Company)",
                text,
                re.IGNORECASE
            )
            location_match = re.search(r"Location\s*[:\-]?\s*(.*?)\n", text)
            equipment_match = re.search(r"Equipment Name\s*[:\-]?\s*(.*?)\n", text)

            if name_match:
                raw_title = ' '.join(name_match.group(1).split())
                location = location_match.group(1).strip() if location_match else "UNKNOWN_LOCATION"
                equipment = equipment_match.group(1).strip() if equipment_match else "UNKNOWN_EQUIPMENT"

                metadata.append({
                    "page": i,
                    "title": clean_filename(raw_title),
                    "location": clean_filename(location),
                    "equipment": clean_filename(equipment)
                })
    return metadata


if uploaded_file:
    file_bytes = uploaded_file.read()
    pdf_reader = PdfReader(io.BytesIO(file_bytes))

    # Extract text from each page
    pages_text = [p.extract_text() or "" for p in pdf_reader.pages]
    checklist_meta = extract_checklist_metadata(pages_text)

    if checklist_meta:
        st.success(f"Detected {len(checklist_meta)} checklists.")

        # Determine page ranges for each checklist
        starts = [item['page'] for item in checklist_meta]
        ends = starts[1:] + [len(pages_text)]

        groups = []
        for meta, start, end in zip(checklist_meta, starts, ends):
            groups.append({
                "title": meta['title'],
                "start": start,
                "end": end
            })

        # Build the ZIP
        zip_buffer = io.BytesIO()
        summary = []
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            for g in groups:
                writer = PdfWriter()
                for pg in range(g['start'], g['end']):
                    writer.add_page(pdf_reader.pages[pg])

                pdf_out = io.BytesIO()
                writer.write(pdf_out)
                filename = f"{g['title']}.pdf"
                zipf.writestr(filename, pdf_out.getvalue())

                summary.append({
                    "Checklist Name": g['title'],
                    "Start Page": g['start'] + 1,
                    "End Page": g['end']
                })

        df = pd.DataFrame(summary)
        st.dataframe(df)
        st.download_button(
            "Download ZIP of Checklists",
            data=zip_buffer.getvalue(),
            file_name="Checklist_Split.zip"
        )
    else:
        st.warning("Detected 0 checklists.")