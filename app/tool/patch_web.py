"""Names the web version "Chintan" so it installs nicely on an iPhone home screen.

Run from app/ after `flutter create --platforms web .` and the icon step.
"""
import json
import pathlib
import re

WEB = pathlib.Path(__file__).resolve().parent.parent / "web"

manifest_path = WEB / "manifest.json"
m = json.loads(manifest_path.read_text())
m.update({
    "name": "Chintan AI Call Assistant",
    "short_name": "Chintan",
    "description": "AI call assistant for a CA practice",
    "background_color": "#1B2430",
    "theme_color": "#1B2430",
    "display": "standalone",
})
manifest_path.write_text(json.dumps(m, indent=2))

index_path = WEB / "index.html"
h = index_path.read_text()
h = re.sub(r"<title>.*?</title>", "<title>Chintan</title>", h, flags=re.S)
h = re.sub(r'(<meta name="apple-mobile-web-app-title" content=")[^"]*(")', r"\1Chintan\2", h)
h = re.sub(r'(<meta name="description" content=")[^"]*(")', r"\1Chintan AI Call Assistant\2", h)
if 'name="apple-mobile-web-app-capable"' not in h:
    h = h.replace("</head>", '  <meta name="apple-mobile-web-app-capable" content="yes">\n</head>', 1)
if 'name="theme-color"' not in h:
    h = h.replace("</head>", '  <meta name="theme-color" content="#1B2430">\n</head>', 1)
index_path.write_text(h)
print("Web app named Chintan.")
