document.addEventListener('DOMContentLoaded', function() {
    const raw = document.getElementById('rawMarkdown').value;
    const contentDiv = document.getElementById('content');
    marked.setOptions({ breaks: true, gfm: true });
    const renderer = new marked.Renderer();
    const originalCode = renderer.code.bind(renderer);
    renderer.code = (code, language) => {
        if (language === 'mermaid') {
            return `<div class="mermaid">${code}</div>`;
        }
        return originalCode(code, language);
    };
    contentDiv.innerHTML = marked.parse(raw, { renderer: renderer });
    mermaid.initialize({
        startOnLoad: true,
        theme: 'dark',
        securityLevel: 'loose',
        themeVariables: {
            primaryColor: '#a855f7',
            primaryTextColor: '#fff',
            secondaryColor: '#ec4899',
            tertiaryColor: '#1e1e24',
            mainBkg: '#1e1e24',
            nodeBorder: '#a855f7',
            lineColor: '#e4e4e7'
        }
    });
    mermaid.run();
});
