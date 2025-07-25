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
    # Normalize, strip accents, and remove illegal filename chars
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    return re.sub(r'[<>:"/\\|?*]', '', name).strip()


def extract_checklist_metadata(pages_text):
    meta = []
    for i, text in enumerate(pages_text):
        # look for the common header fields
        if all(field in text for field in ["ID", "Name", "Description", "Company", "Checklist Status"]):
            # multi-line name until next header keyword
            name_match = re.search(
                r"Name\s*[:\-]?\s*(.+?)(?=\n(?:ID|Description|Author|Created On|Tags|Custom Properties|Company|Priority|Status|Location|Equipment Name|Equipment Barcode))",
                text,
                re.IGNORECASE | re.DOTALL
            )
            loc_match = re.search(r"Location\s*[:\-]?\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
            equip_match = re.search(r"Equipment Name\s*[:\-]?\s*(.+?)(?:\n|$)", text, re.IGNORECASE)

            if name_match:
                raw = name_match.group(1).strip().replace('\n', ' ')  # flatten line breaks
                location = loc_match.group(1).strip() if loc_match else "UNKNOWN_LOCATION"
                equipment = equip_match.group(1).strip() if equip_match else "UNKNOWN_EQUIPMENT"

                meta.append({
                    "page": i,
                    "title": clean_filename(raw),
                    "location": clean_filename(location),
                    "equipment": clean_filename(equipment)
                })
    return meta


if uploaded_file:
    file_bytes = uploaded_file.read()
    reader = PdfReader(io.BytesIO(file_bytes))
    pages_text = [p.extract_text() or "" for p in reader.pages]
    items = extract_checklist_metadata(pages_text)

    if not items:
        st.warning("Detected 0 checklists.")
    else:
        st.success(f"Detected {len(items)} checklists.")
        starts = [it['page'] for it in items]
        ends = starts[1:] + [len(reader.pages)]

        rows = []
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            for it, st_idx, en_idx in zip(items, starts, ends):
                writer = PdfWriter()
                for pg in range(st_idx, en_idx):
                    writer.add_page(reader.pages[pg])
                out = io.BytesIO()
                writer.write(out)
                folder = it['location'] + '/'
                filename = f"{it['title']}.pdf"
                zf.writestr(folder + filename, out.getvalue())

                rows.append({
                    "Checklist Name": it['title'],
                    "Location": it['location'],
                    "Equipment Name": it['equipment'],
                    "Start Page": st_idx+1,
                    "End Page": en_idx
                })

        df = pd.DataFrame(rows)
        st.dataframe(df)
        st.download_button("Download ZIP", data=buf.getvalue(), file_name="checklists.zip")
