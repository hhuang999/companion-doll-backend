# Self-hosted fonts

- `manrope.woff2`: Manrope variable font, Latin and navigation symbols. [Official source](https://github.com/google/fonts/tree/main/ofl/manrope); license `manrope-OFL.txt`.
- `companion-sans.woff2`: Noto Sans SC variable font, non-ASCII characters used in `docs/showcase.html`, `docs/assets/project.js` and `docs/assets/project-data.json`. [Official source](https://github.com/google/fonts/tree/main/ofl/notosanssc); license `notosanssc-OFL.txt`.

No font request leaves the site at runtime. System fonts only provide a fallback for loading or newly added characters. The prior Serif subset is no longer used.

To refresh, download the upstream variable TTFs from the official repositories, retain their OFL files, then use Python with `fonttools` and `brotli`. The fonts are asset-build dependencies, not backend runtime dependencies. Use this recipe from the repository root, with the downloaded TTF paths filled in:

```python
from pathlib import Path
from fontTools import subset
from fontTools.ttLib import TTFont

text = ''.join(Path(p).read_text(encoding='utf-8') for p in [
    'docs/showcase.html', 'docs/assets/project.js', 'docs/assets/project-data.json',
])
jobs = [
    ('NotoSansSC[wght].ttf', 'companion-sans.woff2', {c for c in text if ord(c) > 127}),
    ('Manrope[wght].ttf', 'manrope.woff2', {chr(c) for c in range(32, 127)} | set('→↗↓−·')),
]
for source, name, chars in jobs:
    font = TTFont(source)
    worker = subset.Subsetter(options=subset.Options())
    worker.populate(text=''.join(sorted(chars)))
    worker.subset(font)
    font.flavor = 'woff2'
    font.save(Path('docs/assets/fonts') / name)
```

Check the loaded fonts and inspect Chinese headings in the browser after refreshing. Do not commit the full upstream TTFs or font build environments.
