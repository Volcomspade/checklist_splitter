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
    # normalize to ASCII and strip illegal filename chars
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = name.strip()
    # collapse spaces
    return re.sub(r'\s+', ' ', name)


def extract_checklist_metadata(pages_text):
    entries = []
    name_re = re.compile(r"Name\s*[:\-]?\s*([\s\S]*?)(?=\nDescription)", re.IGNORECASE)
    loc_re = re.compile(r"Location\s*[:\-]?\s*(.*?)\s*\n", re.IGNORECASE)
    equip_re = re.compile(r"Equipment Name\s*[:\-]?\s*(.*?)\s*\n", re.IGNORECASE)

    for idx, text in enumerate(pages_text):
        if 'ID' in text and 'Name' in text and 'Description' in text and 'Location' in text:
            # extract name spanning possible multiple lines, until Description header
            m = name_re.search(text)
            if not m:
                continue
            raw_name = m.group(1).strip().replace('\n', ' ')
            # extract location
            loc_m = loc_re.search(text)
            raw_loc = loc_m.group(1).strip() if loc_m else 'UNKNOWN LOCATION'
            # extract equipment
            eq_m = equip_re.search(text)
            raw_eq = eq_m.group(1).strip() if eq_m else 'UNKNOWN EQUIPMENT'

            entries.append({
                'page': idx,
                'title': clean_filename(raw_name),
                'location': clean_filename(raw_loc),
                'equipment': clean_filename(raw_eq)
            })
    return entries

if uploaded_file:
    uploaded_file.seek(0)
    data = uploaded_file.read()
    reader = PdfReader(io.BytesIO(data))
    pages = [p.extract_text() or '' for p in reader.pages]
    meta = extract_checklist_metadata(pages)

    if not meta:
        st.warning("Detected 0 checklists.")
    else:
        st.success(f"Detected {len(meta)} checklists.")
        starts = [e['page'] for e in meta]
        ends = starts[1:] + [len(pages)]

        records = []
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            for e, s, t in zip(meta, starts, ends):
                writer = PdfWriter()
                for page_idx in range(s, t):
                    writer.add_page(reader.pages[page_idx])
                out = io.BytesIO()
                writer.write(out)

                folder = e['location'] + '/'
                fname = f"{e['title']}.pdf"
                zf.writestr(folder + fname, out.getvalue())
                records.append({
                    'Checklist Name': e['title'],
                    'Location': e['location'],
                    'Equipment Name': e['equipment'],
                    'Start Page': s+1,
                    'End Page': t
                })

        df = pd.DataFrame(records)
        st.dataframe(df)
        st.download_button("Download ZIP", data=buf.getvalue(), file_name="Checklist_Split_By_Location.zip")
