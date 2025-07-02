import streamlit as st
import zipfile
from PyPDF2 import PdfReader, PdfWriter
import io
import re
import unicodedata

st.set_page_config(page_title="Checklist PDF Splitter", layout="wide")
st.title("📄 Checklist PDF Splitter")

uploaded_file = st.file_uploader("Upload Checklist Report PDF", type=["pdf"])

if uploaded_file:
    pdf_reader = PdfReader(uploaded_file)
    pages_text = [page.extract_text() for page in pdf_reader.pages]

    # Detect checklist pages by finding "Name" and "Checklist" pattern
    checklist_names = []
    checklist_starts = []
    for i, text in enumerate(pages_text):
        if text:
            match = re.search(r"Name\s+(.+?Checklist)", text)
            if match:
                name = match.group(1).strip()
                if not checklist_names or name != checklist_names[-1]:
                    checklist_names.append(name)
                    checklist_starts.append(i)

    checklist_starts.append(len(pages_text))
    checklist_ranges = [
        {"Name": checklist_names[i], "start": checklist_starts[i], "end": checklist_starts[i+1]}
        for i in range(len(checklist_names))
    ]

    if checklist_ranges:
        st.success(f"Detected {len(checklist_ranges)} checklists.")

        if st.button("Download ZIP of Checklists"):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zipf:
                uploaded_file.seek(0)
                pdf = PdfReader(uploaded_file)

                for chk in checklist_ranges:
                    writer = PdfWriter()
                    for p in range(chk["start"], chk["end"]):
                        writer.add_page(pdf.pages[p])

                    # Clean filename
                    raw_name = chk["Name"].replace("Name", "").strip()
                    cleaned_name = re.sub(r'[^\w\-]', '', unicodedata.normalize('NFKD', raw_name).encode('ascii', 'ignore').decode())
                    filename = f"{cleaned_name}.pdf"

                    pdf_output = io.BytesIO()
                    writer.write(pdf_output)
                    pdf_output.seek(0)
                    zipf.writestr(filename, pdf_output.getvalue())

            st.download_button("Download ZIP", data=zip_buffer.getvalue(), file_name="CHECKLIST_SPLITS.ZIP")
    else:
        st.success("Detected 0 checklists.")
