#!/usr/bin/env python3
"""Build a self-contained HTML page. Python 3.9+, standard library only."""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOCALES = json.loads((ROOT / 'src' / 'locales.json').read_text(encoding='utf-8'))
LANGUAGES = tuple(locale['code'] for locale in LOCALES)


def build() -> Path:
    if len(set(LANGUAGES)) != len(LANGUAGES) or not LANGUAGES or LANGUAGES[0] != 'ja':
        raise ValueError('Expected unique locales with Japanese as the fallback')
    template_path = ROOT / 'src' / 'index.template.html'
    template = template_path.read_text(encoding='utf-8')
    prompts = {}
    for language in LANGUAGES:
        prompt_path = ROOT / 'prompts' / f'led_solder_review_{language}.txt'
        prompt_text = prompt_path.read_text(encoding='utf-8').strip() + '\n'
        if not prompt_text.startswith('# ') or len(prompt_text) < 1000:
            raise ValueError(f'Unexpected or empty prompt content: {language}')
        prompts[language] = prompt_text
    prompt = prompts['ja']
    translations = {}
    for language in LANGUAGES[1:]:
        translation_path = ROOT / 'src' / 'translations' / f'{language}.json'
        translations[language] = json.loads(translation_path.read_text(encoding='utf-8'))
        if not isinstance(translations[language], dict) or not translations[language]:
            raise ValueError(f'Missing UI translations: {language}')
    for token in ('@@PROMPT_HTML@@', '@@PROMPT_JSON@@', '@@PROMPTS_JSON@@', '@@TRANSLATIONS_JSON@@', '@@LOCALES_JSON@@', '@@LANGUAGE_OPTIONS@@'):
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
    page = page.replace('@@LOCALES_JSON@@', script_json(LOCALES))
    language_options = ''.join(
        f'<option value="{html.escape(locale["code"], quote=True)}" '
        f'lang="{html.escape(locale["code"], quote=True)}">{html.escape(locale["name"])}</option>'
        for locale in LOCALES)
    page = page.replace('@@LANGUAGE_OPTIONS@@', language_options)
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
