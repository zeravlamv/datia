document.addEventListener('DOMContentLoaded', async () => {
  let appName = 'DATIA';
  
  // 1. Fetch App Name
  try {
    const res = await fetch('/api/config/global');
    const data = await res.json();
    const name = (data && data.implanter_settings && data.implanter_settings.app_name) 
                 || localStorage.getItem('datia-app-name');
    if (name) appName = name;
  } catch (_) {
    const stored = localStorage.getItem('datia-app-name');
    if (stored) appName = stored;
  }

  // 2. Update specific ID and Title
  try {
    const el = document.getElementById('whitepaper-app-name');
    if (el) el.textContent = appName;
    document.title = `${appName} - Investment Deck`;
  } catch (_) {}

  // 3. Global Text Replacement (Datia/DATIA -> appName)
  // Only if appName is different to avoid redundant work
  if (appName && appName.toUpperCase() !== 'DATIA') {
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
      null,
      false
    );
    let node;
    const regex = /\b(Datia|DATIA)\b/g;
    while (node = walker.nextNode()) {
       if (node.nodeValue && regex.test(node.nodeValue)) {
          // Avoid replacing inside scripts or styles just in case
          if (node.parentElement && ['SCRIPT', 'STYLE'].includes(node.parentElement.tagName)) continue;
          node.nodeValue = node.nodeValue.replace(regex, appName);
       }
    }
  }

  // 4. Gallery Render (Datia Pro Captures)
  try {
    const container = document.querySelector('.container');
    if (!container) return;

    // Check if Gallery already exists (to replace or append)
    // We append a new section at the end
    const section = document.createElement('section');
    section.className = 'section';

    const header = document.createElement('div');
    header.className = 'section-header';
    const num = document.createElement('div');
    num.className = 'section-number';
    num.textContent = 'GALERÍA';
    const title = document.createElement('div');
    title.className = 'section-title';
    title.textContent = 'Capturas de Producto';
    header.appendChild(num);
    header.appendChild(title);
    section.appendChild(header);

    const grid = document.createElement('div');
    grid.className = 'gallery-grid';

    // Generate Captura1.JPG to Captura12.JPG
    // Note: Served via STATICFILES_DIRS pointing to datia_pro
    // So URL is /static/CapturaX.JPG
    const images = [];
    for (let i = 1; i <= 12; i++) {
        images.push({
            src: `/static/Captura${i}.JPG`,
            alt: `Captura de Pantalla ${i}`
        });
    }

    images.forEach(img => {
      const item = document.createElement('figure');
      item.className = 'gallery-item';
      
      const image = document.createElement('img');
      image.className = 'gallery-img';
      image.src = img.src;
      image.alt = img.alt;
      image.loading = 'lazy';
      
      // Hide if fails (robustness)
      image.onerror = function() {
          item.style.display = 'none';
      };

      const cap = document.createElement('figcaption');
      cap.className = 'gallery-caption';
      cap.textContent = img.alt;
      
      item.appendChild(image);
      item.appendChild(cap);
      grid.appendChild(item);
    });

    section.appendChild(grid);
    container.appendChild(section);
  } catch (_) {}
});
