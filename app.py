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
st.title("📄 Checklist PDF Splitter")

uploaded_file = st.file_uploader("Upload Checklist Report PDF", type=["pdf"])

def clean_filename(name):
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    name = re.sub(r'[<>:"/\\|?*]', '', name)  # Remove illegal characters
    return name.strip()

def extract_checklist_metadata(pages_text):
    titles = []
    for i, text in enumerate(pages_text):
        if all(field in text for field in ["ID", "Name", "Description", "Company", "Checklist Status"]):
            name_match = re.search(
                r"Name\s*[:\-]?\s*(.*?)\n(?=(ID|Description|Author|Created On|Tags|Custom Properties|Company|Priority|Status|Location|Equipment Name|Equipment Barcode))",
                text,
                re.IGNORECASE | re.DOTALL
            )
            location_match = re.search(r"Location\s*[:\-]?\s*(.*?)\n", text)
            equipment_match = re.search(r"Equipment Name\s*[:\-]?\s*(.*?)\n", text)

            if name_match:
                raw_title = name_match.group(1).strip()
                location = location_match.group(1).strip() if location_match else "UNKNOWN LOCATION"
                equipment = equipment_match.group(1).strip() if equipment_match else "UNKNOWN EQUIPMENT"

                titles.append({
                    "page": i,
                    "title": clean_filename(raw_title),
                    "location": clean_filename(location),
                    "equipment": clean_filename(equipment)
                })
    return titles

if uploaded_file:
    uploaded_file.seek(0)
    file_bytes = uploaded_file.read()
    pdf_reader = PdfReader(io.BytesIO(file_bytes))

    pages_text = [page.extract_text() or "" for page in pdf_reader.pages]
    checklist_meta = extract_checklist_metadata(pages_text)

    if checklist_meta:
        st.success(f"Detected {len(checklist_meta)} checklists.")

        start_indices = [item['page'] for item in checklist_meta]
        end_indices = start_indices[1:] + [len(pages_text)]

        checklist_groups = [
            {
                "title": item['title'],
                "location": item['location'],
                "equipment": item['equipment'],
                "start": start,
                "end": end
            }
            for item, start, end in zip(checklist_meta, start_indices, end_indices)
        ]

        summary_data = []
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            for group in checklist_groups:
                writer = PdfWriter()
                for p in range(group["start"], group["end"]):
                    writer.add_page(pdf_reader.pages[p])
                pdf_output = io.BytesIO()
                writer.write(pdf_output)
                folder_path = group["location"] + "/"
                filename = f"{group['title']}.pdf"
                zipf.writestr(folder_path + filename, pdf_output.getvalue())

                summary_data.append({
                    "Checklist Name": group['title'],
                    "Location": group['location'],
                    "Equipment Name": group['equipment'],
                    "Start Page": group['start'] + 1,
                    "End Page": group['end']
                })

        summary_df = pd.DataFrame(summary_data)
        st.dataframe(summary_df)
        st.download_button("Download ZIP", data=zip_buffer.getvalue(), file_name="Checklist_Split_By_Location.zip")
    else:
        st.warning("Detected 0 checklists.")
