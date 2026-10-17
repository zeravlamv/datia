
from pdfminer.high_level import extract_text
import sys
import os

def extract_pdf_content(pdf_path):
    try:
        text = extract_text(pdf_path)
        # Save to a text file for review
        output_path = pdf_path.replace('.pdf', '_content.txt')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Successfully extracted text to {output_path}")
        
        # Print the first 2000 characters to get an idea of the content
        print("First 2000 characters:")
        print(text[:2000])
        
    except Exception as e:
        print(f"Error extracting text: {e}")

if __name__ == "__main__":
    pdf_path = "c:/Users/miguel vergara/Desktop/datia/Tratado Integral de Análisis de Estados Financieros.pdf"
    extract_pdf_content(pdf_path)
