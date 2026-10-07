#!/usr/bin/env python3
"""Static checks for the generated page. Standard library only."""
from __future__ import annotations
import html
import base64
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ('ja', 'en', 'zh-CN')
JAPANESE = re.compile(r'[ぁ-んァ-ヶ一-龯]')
sys.path.insert(0, str(ROOT))
from build import build


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.anchors: list[str] = []
        self.external_assets: list[str] = []
        self.h1_count = 0
        self.labels: set[str] = set()
        self.inputs: list[str] = []
        self.stack: list[tuple[str, dict[str, str | None]]] = []
        self.translation_keys: set[str] = set()
        self.logo_sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag not in ('area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'):
            self.stack.append((tag, a))
        for name in ('aria-label', 'placeholder', 'content', 'title'):
            value = a.get(name, '') or ''
            if JAPANESE.search(value):
                self.translation_keys.add(value)
        if a.get('id'):
            self.ids.append(a['id'])
        if tag == 'h1':
            self.h1_count += 1
        if tag == 'label' and a.get('for'):
            self.labels.add(a['for'])
        if tag in ('input', 'select', 'textarea') and a.get('id'):
            self.inputs.append(a['id'])
        href = a.get('href', '') or ''
        if href.startswith('#'):
            self.anchors.append(href[1:])
        if tag in ('script', 'img', 'iframe') and a.get('src'):
            if not (tag == 'img' and a['src'].startswith('data:image/png;base64,')):
                self.external_assets.append(a['src'])
        if tag == 'img' and 'brand-logo' in (a.get('class', '') or '').split():
            self.logo_sources.append(a.get('src', '') or '')
        if tag == 'link' and a.get('rel') == 'stylesheet':
            self.external_assets.append(href)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if any(tag in ('script', 'style', 'textarea', 'noscript') or attrs.get('id') == 'language-select' for tag, attrs in self.stack):
            return
        key = data.strip()
        if JAPANESE.search(key):
            self.translation_keys.add(key)


def embedded_json(page: str, name: str):
    match = re.search(r'const ' + re.escape(name) + r' = (.+);\n', page)
    assert match, f'Missing embedded {name}'
    return json.loads(match.group(1))


def main() -> None:
    page = (ROOT / 'index.html').read_text(encoding='utf-8')
    build()
    assert page == (ROOT / 'index.html').read_text(encoding='utf-8'), 'index.html was not in sync; regenerated it'
    prompts = {lang: (ROOT / f'prompts/led_solder_review_{lang}.txt').read_text(encoding='utf-8').strip() + '\n' for lang in LANGUAGES}
    prompt = prompts['ja']
    assert embedded_json(page, 'BASE_PROMPT') == prompt, 'JS Japanese prompt is out of sync'
    assert embedded_json(page, 'PROMPTS') == prompts, 'Multilingual JS prompts are out of sync'
    translations = json.loads((ROOT / 'src/translations.json').read_text(encoding='utf-8'))
    assert embedded_json(page, 'TRANSLATIONS') == translations, 'JS translations are out of sync'
    field = re.search(r'<textarea id="prompt-output"[^>]*>(.*?)</textarea>', page, re.S)
    assert field and html.unescape(field.group(1)) == prompt, 'No-JS prompt is out of sync'
    assert not re.search(r'@@[A-Z_]+@@', page), 'Unreplaced build placeholder'
    for phrase in ['最優先：はんだ付けの確認が先', '補強がないことだけで接合不良と判定せず', '写真確認の前提条件にしない', 'この時点では接合部を覆わず', '覆う前の写真があれば', '電流端子や電流モードを使わせない']:
        assert phrase in prompt, f'Missing safety rule: {phrase}'
    parser = PageParser()
    parser.feed(page)
    assert len(parser.ids) == len(set(parser.ids)), 'Duplicate HTML id'
    assert all(anchor in parser.ids for anchor in parser.anchors), 'Broken fragment link'
    assert all(field_id in parser.labels for field_id in parser.inputs), 'Unlabelled field'
    assert parser.h1_count == 1, 'Expected one H1'
    assert not parser.external_assets, f'Unexpected external asset: {parser.external_assets}'
    for language in ('en', 'zh-CN'):
        assert language in translations, f'Missing language: {language}'
        missing = sorted(parser.translation_keys - translations[language].keys())
        assert not missing, f'Missing {language} translations: {missing}'
        assert all(isinstance(value, str) and value.strip() for value in translations[language].values()), f'Empty {language} translation'
    assert len(parser.logo_sources) == 1, 'Expected one embedded EdelWorks logo'
    prefix = 'data:image/png;base64,'
    assert parser.logo_sources[0].startswith(prefix)
    assert base64.b64decode(parser.logo_sources[0][len(prefix):], validate=True) == (ROOT / 'assets/edelworks_logo_origin.png').read_bytes(), 'Logo does not match the supplied original'
    assert re.search(r'<html\b[^>]*\blang="ja"', page), 'Expected Japanese fallback language'
    assert 'theme-select' in parser.ids and 'language-select' in parser.ids
    assert 'localStorage.' not in page and 'fetch(' not in page and 'XMLHttpRequest' not in page
    print('PASS: build sync, all three prompt/translation sources, Japanese translation coverage, original logo bytes, safety rules, fragment links, form labels, and no external assets.')


if __name__ == '__main__':
    main()
