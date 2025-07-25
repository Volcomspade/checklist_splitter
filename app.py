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

def clean_folder_name(name):
    """
    Clean location for folder names: preserve spaces, remove illegal filesystem characters.
    """
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    # Remove illegal characters but keep > and spaces
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    return name.strip()

def clean_filename(name):
    """
    Clean title for filenames: replace spaces with underscores, remove illegal chars.
    """
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = name.replace(' ', '_')
    return name.strip()

def extract_checklist_metadata(pages_text):
    """
    Extract metadata: page index, raw title, location, equipment.
    """
    metadata = []
    for i, text in enumerate(pages_text):
        if all(field in text for field in ["ID", "Name", "Description", "Company", "Checklist Status"]):
            # Capture Name line
            name_match = re.search(
                r"Name\s*[:\-]?\s*(.*?)\n", text, re.IGNORECASE | re.DOTALL
            )
            location_match = re.search(r"Location\s*[:\-]?\s*(.*?)\n", text)
            equipment_match = re.search(r"Equipment Name\s*[:\-]?\s*(.*?)\n", text)
            if name_match:
                raw_title = name_match.group(1).strip()
                # Remove trailing 'Priority' and any appended text
                raw_title = re.sub(r"\bPriority\b.*$", "", raw_title, flags=re.IGNORECASE).strip()
                location = location_match.group(1).strip() if location_match else "UNKNOWN LOCATION"
                equipment = equipment_match.group(1).strip() if equipment_match else "UNKNOWN EQUIPMENT"
                metadata.append({
                    "page": i,
                    "title_raw": raw_title,
                    "location": location,
                    "equipment": equipment
                })
    return metadata

if uploaded_file:
    file_bytes = uploaded_file.read()
    pdf_reader = PdfReader(io.BytesIO(file_bytes))
    pages_text = [page.extract_text() or "" for page in pdf_reader.pages]

    checklist_meta = extract_checklist_metadata(pages_text)

    if checklist_meta:
        st.success(f"Detected {len(checklist_meta)} checklists.")
        # Determine start/end pages
        starts = [item['page'] for item in checklist_meta]
        ends = starts[1:] + [len(pages_text)]

        summary = []
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            for item, start, end in zip(checklist_meta, starts, ends):
                # Create PDF for this checklist
                writer = PdfWriter()
                for p in range(start, end):
                    writer.add_page(pdf_reader.pages[p])
                pdf_out = io.BytesIO()
                writer.write(pdf_out)

                # Build nested folder path from location (split on >)
                parts = [clean_folder_name(part.strip()) for part in item['location'].split('>')]
                folder_path = "/".join(parts) + "/"
                filename = clean_filename(item['title_raw']) + ".pdf"
                zipf.writestr(folder_path + filename, pdf_out.getvalue())

                summary.append({
                    "Checklist Name": item['title_raw'],
                    "Location": item['location'],
                    "Equipment Name": item['equipment'],
                    "Filename": filename,
                    "Start Page": start + 1,
                    "End Page": end
                })
        # Display summary
        df = pd.DataFrame(summary)
        st.dataframe(df)
        st.download_button("Download ZIP", data=zip_buffer.getvalue(), file_name="Checklist_By_Location.zip")
    else:
        st.warning("Detected 0 checklists.")