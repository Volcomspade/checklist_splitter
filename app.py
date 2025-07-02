import streamlit as st
import zipfile
from PyPDF2 import PdfReader, PdfWriter
import io
import re
import unicodedata
import pandas as pd

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
        match = re.search(r"ID:\s*MQ\d+.*?Name:\s*(.*?)\s+Description:", text, re.IGNORECASE | re.DOTALL)
        if match:
            titles.append((i, match.group(1).strip()))
    return titles

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
                    writer.add_page(pdf_reader.pages[p])
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
