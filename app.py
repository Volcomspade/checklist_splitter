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

# Clean filenames: normalize, remove illegal chars, replace spaces with underscores
def clean_filename(name):
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name.replace(' ', '_')

# Clean folder names: normalize, remove illegal chars, preserve spaces
def clean_foldername(name):
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    return re.sub(r'\s+', ' ', name).strip()

# Extract metadata based on header fields
def extract_checklist_metadata(pages_text):
    meta = []
    for i, text in enumerate(pages_text):
        if all(k in text for k in ("ID", "Name", "Description", "Company", "Checklist Status")):
            m = re.search(
                r"Name\s*[:\-]?\s*(.*?)\n(?=(?:ID|Description|Author|Created On|Tags|Custom Properties|Company|Status|Location|Equipment Name|Equipment Barcode))",
                text, re.IGNORECASE | re.DOTALL
            )
            loc = re.search(r"Location\s*[:\-]?\s*(.*?)\n", text, re.IGNORECASE)
            eq  = re.search(r"Equipment Name\s*[:\-]?\s*(.*?)\n", text, re.IGNORECASE)
            if not m:
                continue

            raw_title = m.group(1).strip()
            raw_title = re.sub(r'[\s_-]*Priority\s*$', '', raw_title, flags=re.IGNORECASE)
            title = clean_filename(raw_title)

            location = loc.group(1).strip() if loc else "UNKNOWN"
            equipment = eq.group(1).strip() if eq else "UNKNOWN"

            meta.append({
                "page": i,
                "title": title,
                "location": location,
                "equipment": clean_filename(equipment)
            })
    return meta

if uploaded_file:
    file_bytes = uploaded_file.read()
    pdf_reader = PdfReader(io.BytesIO(file_bytes))
    pages_text = [p.extract_text() or "" for p in pdf_reader.pages]
    checklist_meta = extract_checklist_metadata(pages_text)

    if not checklist_meta:
        st.warning("Detected 0 checklists.")
    else:
        st.success(f"Detected {len(checklist_meta)} checklists.")

        starts = [d["page"] for d in checklist_meta]
        ends = starts[1:] + [len(pages_text)]

        summary = []
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zf:
            for info, s, e in zip(checklist_meta, starts, ends):
                writer = PdfWriter()
                for p in range(s, e):
                    writer.add_page(pdf_reader.pages[p])

                output_bytes = io.BytesIO()
                writer.write(output_bytes)

                # Build folder path with spaces preserved
                parts = [clean_foldername(x.strip()) for x in info["location"].split(">")]
                folder = "/".join(parts) + "/"

                filename = f"{info['title']}.pdf"
                zf.writestr(folder + filename, output_bytes.getvalue())

                summary.append({
                    "Checklist Name": info["title"],
                    "Location": info["location"],
                    "Equipment": info["equipment"],
                    "Start Page": s + 1,
                    "End Page": e
                })

        df = pd.DataFrame(summary)
        st.dataframe(df)
        st.download_button(
            "Download ZIP",
            data=zip_buffer.getvalue(),
            file_name="Checklists_By_Location.zip"
        )