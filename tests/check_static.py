#!/usr/bin/env python3
"""Static checks for the generated page. Standard library only."""
from __future__ import annotations
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
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
            self.external_assets.append(a['src'])
        if tag == 'link' and a.get('rel') == 'stylesheet':
            self.external_assets.append(href)


def main() -> None:
    page = (ROOT / 'index.html').read_text(encoding='utf-8')
    build()
    assert page == (ROOT / 'index.html').read_text(encoding='utf-8'), 'index.html was not in sync; regenerated it'
    prompt = (ROOT / 'prompts/led_solder_review_ja.txt').read_text(encoding='utf-8').strip() + '\n'
    match = re.search(r'const BASE_PROMPT = (.+);\n', page)
    assert match and json.loads(match.group(1)) == prompt, 'JS prompt is out of sync'
    field = re.search(r'<textarea id="prompt-output"[^>]*>(.*?)</textarea>', page, re.S)
    assert field and html.unescape(field.group(1)) == prompt, 'No-JS prompt is out of sync'
    assert '@@PROMPT_' not in page
    for phrase in ['最優先：はんだ付けの確認が先', '補強がないことだけで接合不良と判定せず', '写真確認の前提条件にしない', 'この時点では接合部を覆わず', '覆う前の写真があれば', '電流端子や電流モードを使わせない']:
        assert phrase in prompt, f'Missing safety rule: {phrase}'
    parser = PageParser()
    parser.feed(page)
    assert len(parser.ids) == len(set(parser.ids)), 'Duplicate HTML id'
    assert all(anchor in parser.ids for anchor in parser.anchors), 'Broken fragment link'
    assert all(field_id in parser.labels for field_id in parser.inputs), 'Unlabelled field'
    assert parser.h1_count == 1, 'Expected one H1'
    assert not parser.external_assets, f'Unexpected external asset: {parser.external_assets}'
    assert '<html lang="ja">' in page
    assert 'localStorage.' not in page and 'fetch(' not in page and 'XMLHttpRequest' not in page
    print('PASS: build sync, prompt sync, safety rules, fragment links, form labels, and no external assets.')


if __name__ == '__main__':
    main()
