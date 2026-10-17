
import os
from pypdf import PdfReader

pdf_path = "Tratado Integral de Análisis de Estados Financieros.pdf"
keywords = ["Liquidez", "Solvencia", "Endeudamiento", "Ratio", "Rentabilidad"]
content = {}

try:
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    
    # Simple extraction of context around keywords
    for kw in keywords:
        start_idx = text.find(kw)
        if start_idx != -1:
            # Grab a chunk of text around the keyword
            end_idx = min(len(text), start_idx + 1500)
            content[kw] = text[start_idx:end_idx].replace('\n', ' ')
            
    print("Extraction Success")
    for k, v in content.items():
        print(f"--- {k} ---")
        print(v[:500] + "...")
        print("\n")

except Exception as e:
    print(f"Error reading PDF: {e}")
