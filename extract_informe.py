from pdfminer.high_level import extract_text
try:
    text = extract_text("c:/Users/miguel vergara/Desktop/datia/Informe de Estabilidad.pdf")
    with open("c:/Users/miguel vergara/Desktop/datia/Informe_content.txt", "w", encoding="utf-8") as f:
        f.write(text)
    print("Extracted.")
except Exception as e:
    print(f"Error: {e}")
