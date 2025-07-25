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
    # 1) normalize unicode → ascii
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    # 2) drop illegal filesystem chars
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    # 3) collapse whitespace to single spaces
    name = re.sub(r'\s+', ' ', name).strip()
    # 4) spaces → underscores
    name = name.replace(' ', '_')
    return name

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
            # strip trailing “Priority”
            raw_title = re.sub(r'[\s_-]*Priority\s*$', '', raw_title, flags=re.IGNORECASE)
            title   = clean_filename(raw_title)

            location = loc.group(1).strip() if loc else "UNKNOWN"
            equipment= eq.group(1).strip() if eq else "UNKNOWN"

            meta.append({
                "page": i,
                "title": title,
                "location": location,
                "equipment": clean_filename(equipment)
            })
    return meta

if uploaded_file:
    file_bytes  = uploaded_file.read()
    pdf_reader  = PdfReader(io.BytesIO(file_bytes))
    pages_text  = [p.extract_text() or "" for p in pdf_reader.pages]
    checklist_meta = extract_checklist_metadata(pages_text)

    if not checklist_meta:
        st.warning("Detected 0 checklists.")
    else:
        st.success(f"Detected {len(checklist_meta)} checklists.")

        starts = [d["page"] for d in checklist_meta]
        ends   = starts[1:] + [len(pages_text)]

        summary = []
        zbuf    = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w") as zf:
            for info, s, e in zip(checklist_meta, starts, ends):
                writer = PdfWriter()
                for p in range(s, e):
                    writer.add_page(pdf_reader.pages[p])

                out = io.BytesIO()
                writer.write(out)

                # nested folders by Location chain
                parts = [clean_filename(x.strip()) for x in info["location"].split(">")]
                folder = "/".join(parts) + "/"

                fname = f"{info['title']}.pdf"
                zf.writestr(folder + fname, out.getvalue())

                summary.append({
                    "Checklist Name": info["title"],
                    "Location":       info["location"],
                    "Equipment":      info["equipment"],
                    "Start Page":     s + 1,
                    "End Page":       e
                })

        df = pd.DataFrame(summary)
        st.dataframe(df)
        st.download_button(
            "Download ZIP",
            data=zbuf.getvalue(),
            file_name="Checklists_By_Location.zip"
        )