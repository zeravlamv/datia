import os
import sys
import django
from xhtml2pdf import pisa

# Calculate the project root (assuming script is in datia/scripts/)
# We need to add 'datia/' (the project root containing manage.py) to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
from django.conf import settings
django.setup()

from django.template.loader import render_to_string

def generate_pdf():
    print("Rendering HTML template...")
    # Render the updated whitepaper_pdf.html
    # We pass an empty context as the template is static, or add variables if needed
    try:
        html_content = render_to_string('datia/whitepaper_pdf.html', {})
    except Exception as e:
        print(f"Error rendering template: {e}")
        return

    def link_callback(uri, rel):
        """
        Convert HTML URIs to absolute system paths so xhtml2pdf can access those resources
        """
        sUrl = settings.STATIC_URL        # Typically /static/
        sRoot = settings.STATIC_ROOT      # Typically /home/userX/project_static/
        mUrl = settings.MEDIA_URL         # Typically /media/
        mRoot = settings.MEDIA_ROOT       # Typically /home/userX/project_static/media/

        if uri.startswith(mUrl):
            path = os.path.join(mRoot, uri.replace(mUrl, ""))
        elif uri.startswith(sUrl):
            path = os.path.join(sRoot, uri.replace(sUrl, ""))
        else:
            return uri  # handle absolute uri (ie: http://some.tld/foo.png)

        # make sure that file exists
        if not os.path.isfile(path):
            # Try finding in STATICFILES_DIRS if DEBUG is True or STATIC_ROOT empty
            if hasattr(settings, 'STATICFILES_DIRS'):
                for directory in settings.STATICFILES_DIRS:
                    potential_path = os.path.join(directory, uri.replace(sUrl, ""))
                    if os.path.isfile(potential_path):
                         return potential_path
            
            # FALLBACK: Explicitly check datia/static
            # project_root is calculated at the top as c:/.../datia
            # content is in datia/static
            kw = uri.replace(sUrl, "")
            fallback_path = os.path.join(project_root, 'datia', 'static', kw)
            if os.path.isfile(fallback_path):
                return fallback_path
            
            print(f"Media URI not found: {path} (URI: {uri}) -> Checked fallback: {fallback_path}")
            return uri
            
        return path

    output_filename = os.path.join(project_root, "Whitepaper_Datia_Exec.pdf")
    print(f"Generating PDF to {output_filename}...")
    
    try:
        with open(output_filename, "wb") as result_file:
            pisa_status = pisa.CreatePDF(
                html_content,
                dest=result_file,
                encoding='utf-8',
                link_callback=link_callback
            )

        if pisa_status.err:
            print(f"Error generating PDF: {pisa_status.err}")
        else:
            print(f"SUCCESS: PDF successfully generated at {output_filename}")
            
    except Exception as e:
        print(f"Error writing PDF file: {e}")

if __name__ == "__main__":
    generate_pdf()
