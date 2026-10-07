#!/usr/bin/env python3
"""Build a self-contained HTML page. Python 3.9+, standard library only."""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build() -> Path:
    template_path = ROOT / 'src' / 'index.template.html'
    prompt_path = ROOT / 'prompts' / 'led_solder_review_ja.txt'
    template = template_path.read_text(encoding='utf-8')
    prompt = prompt_path.read_text(encoding='utf-8').strip() + '\n'
    if not prompt.startswith('# LEDテープ'):
        raise ValueError('Unexpected or empty prompt content')
    for token in ('@@PROMPT_HTML@@', '@@PROMPT_JSON@@'):
        if template.count(token) != 1:
            raise ValueError(f'Expected exactly one {token} placeholder')
    # Escape embedded script data, including </script>, without changing runtime text.
    prompt_json = (json.dumps(prompt, ensure_ascii=False)
                   .replace('<', '\\u003c').replace('>', '\\u003e')
                   .replace('&', '\\u0026').replace('\u2028', '\\u2028')
                   .replace('\u2029', '\\u2029'))
    page = template.replace('@@PROMPT_HTML@@', html.escape(prompt, quote=False))
    page = page.replace('@@PROMPT_JSON@@', prompt_json)
    target = ROOT / 'index.html'
    target.write_text(page, encoding='utf-8')
    (ROOT / '.nojekyll').touch()
    return target


if __name__ == '__main__':
    try:
        output = build()
    except (OSError, ValueError) as error:
        raise SystemExit(f'Build failed: {error}') from error
    print(f'Built {output.name} ({output.stat().st_size:,} bytes)')
