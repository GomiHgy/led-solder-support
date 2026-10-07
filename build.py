#!/usr/bin/env python3
"""Build a self-contained HTML page. Python 3.9+, standard library only."""
from __future__ import annotations

import base64
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build() -> Path:
    template_path = ROOT / 'src' / 'index.template.html'
    template = template_path.read_text(encoding='utf-8')
    prompts = {}
    for language in ('ja', 'en', 'zh-CN'):
        prompt_path = ROOT / 'prompts' / f'led_solder_review_{language}.txt'
        prompt_text = prompt_path.read_text(encoding='utf-8').strip() + '\n'
        if not prompt_text.startswith('# ') or len(prompt_text) < 1000:
            raise ValueError(f'Unexpected or empty prompt content: {language}')
        prompts[language] = prompt_text
    prompt = prompts['ja']
    translations = json.loads((ROOT / 'src' / 'translations.json').read_text(encoding='utf-8'))
    for language in ('en', 'zh-CN'):
        if not isinstance(translations.get(language), dict) or not translations[language]:
            raise ValueError(f'Missing UI translations: {language}')
    logo = base64.b64encode((ROOT / 'assets' / 'edelworks_logo_origin.png').read_bytes()).decode('ascii')
    for token in ('@@PROMPT_HTML@@', '@@PROMPT_JSON@@', '@@PROMPTS_JSON@@', '@@TRANSLATIONS_JSON@@', '@@LOGO_DATA@@'):
        if template.count(token) != 1:
            raise ValueError(f'Expected exactly one {token} placeholder')
    # Escape embedded script data, including </script>, without changing runtime text.
    def script_json(value: object) -> str:
        return (json.dumps(value, ensure_ascii=False)
                .replace('<', '\\u003c').replace('>', '\\u003e')
                .replace('&', '\\u0026').replace('\u2028', '\\u2028')
                .replace('\u2029', '\\u2029'))

    page = template.replace('@@PROMPT_HTML@@', html.escape(prompt, quote=False))
    page = page.replace('@@PROMPT_JSON@@', script_json(prompt))
    page = page.replace('@@PROMPTS_JSON@@', script_json(prompts))
    page = page.replace('@@TRANSLATIONS_JSON@@', script_json(translations))
    page = page.replace('@@LOGO_DATA@@', f'data:image/png;base64,{logo}')
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
