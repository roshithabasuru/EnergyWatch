import urllib.request
import os

font_dir = 'app/static/css/fonts'
os.makedirs(font_dir, exist_ok=True)

fonts = {
    '300': 'https://fonts.gstatic.com/s/outfit/v15/QGYyz_MVcBeNP4NjuGObqx1XmO1I4W61C4E.ttf',
    '400': 'https://fonts.gstatic.com/s/outfit/v15/QGYyz_MVcBeNP4NjuGObqx1XmO1I4TC1C4E.ttf',
    '600': 'https://fonts.gstatic.com/s/outfit/v15/QGYyz_MVcBeNP4NjuGObqx1XmO1I4e6yC4E.ttf',
    '700': 'https://fonts.gstatic.com/s/outfit/v15/QGYyz_MVcBeNP4NjuGObqx1XmO1I4deyC4E.ttf'
}

css_content = ''

for weight, url in fonts.items():
    filename = f'outfit-{weight}.ttf'
    filepath = os.path.join(font_dir, filename)
    print(f"Downloading {filename}...")
    urllib.request.urlretrieve(url, filepath)
    css_content += f'''@font-face {{
  font-family: "Outfit";
  font-style: normal;
  font-weight: {weight};
  font-display: swap;
  src: url("./fonts/{filename}") format("truetype");
}}\n'''

with open('app/static/css/outfit.css', 'w') as f:
    f.write(css_content)

print('Fonts downloaded and CSS created successfully.')
