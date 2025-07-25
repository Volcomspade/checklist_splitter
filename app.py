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
    # normalize accents, drop non‐ascii, strip illegal path chars
    name = unicodedata.normalize('NFKD', name)
    name = name.encode('ascii', 'ignore').decode()
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    return name.strip()

def extract_checklist_metadata(pages_text):
    """
    Scan each page's text for the "Details" block, then pull:
     - Name
     - Location
     - Equipment Name
    """
    metadata = []
    for i, text in enumerate(pages_text):
        if all(k in text for k in ("ID", "Name", "Description", "Company", "Checklist Status")):
            # capture the full “Name” value up until the next left‐column header
            m = re.search(
                r"Name\s*[:\-]?\s*(.*?)\n(?=(?:ID|Description|Author|Created On|Tags|Custom Properties|Company|Status|Location|Equipment Name|Equipment Barcode))",
                text,
                re.IGNORECASE | re.DOTALL
            )
            loc = re.search(r"Location\s*[:\-]?\s*(.*?)\n", text, re.IGNORECASE)
            eq  = re.search(r"Equipment Name\s*[:\-]?\s*(.*?)\n", text, re.IGNORECASE)

            if m:
                raw_title = m.group(1).strip()
                # strip trailing “Priority” if present
                raw_title = re.sub(r'[\s_-]*Priority\s*$', '', raw_title, flags=re.IGNORECASE)
                title = clean_filename(raw_title)

                location = loc.group(1).strip() if loc else "UNKNOWN"
                equipment = eq.group(1).strip() if eq else "UNKNOWN"

                metadata.append({
                    "page": i,
                    "title": title,
                    "location": location,
                    "equipment": clean_filename(equipment)
                })
    return metadata

if uploaded_file:
    # read and OCR‐extract
    file_bytes = uploaded_file.read()
    pdf_reader = PdfReader(io.BytesIO(file_bytes))
    pages_text = [p.extract_text() or "" for p in pdf_reader.pages]

    # pull out each checklist’s start‐page, name, etc.
    meta = extract_checklist_metadata(pages_text)

    if not meta:
        st.warning("Detected 0 checklists.")
    else:
        st.success(f"Detected {len(meta)} checklists.")

        # determine page ranges
        starts = [d["page"] for d in meta]
        ends   = starts[1:] + [len(pages_text)]

        # collect for table + ZIP
        summary = []
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as z:
            for info, s, e in zip(meta, starts, ends):
                writer = PdfWriter()
                for p in range(s, e):
                    writer.add_page(pdf_reader.pages[p])

                out_pdf = io.BytesIO()
                writer.write(out_pdf)

                # build nested folder path from “>”‐separated location
                parts = [clean_filename(x.strip()) for x in info["location"].split(">")]
                folder = "/".join(parts) + "/"

                fname = f"{info['title']}.pdf"
                z.writestr(folder + fname, out_pdf.getvalue())

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
            data=zip_buf.getvalue(),
            file_name="Checklists_By_Location.zip"
        )