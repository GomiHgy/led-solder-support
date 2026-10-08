#!/usr/bin/env python3
"""Browser smoke tests. Requires playwright; no site dependencies are added.

By default, test the self-contained document without making a network request.
Use --url to test an actual hosted copy. Clipboard behavior is deterministically
mocked; downloads and generated text are checked in the real browser.
"""
from __future__ import annotations
import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
LOCALES = json.loads((ROOT / 'src/locales.json').read_text(encoding='utf-8'))
LANGUAGES = tuple(locale['code'] for locale in LOCALES)


def prompt_context(text: str) -> dict:
    return json.loads('{' + text.rsplit('\n{', 1)[1])


def brightness(color: str) -> float:
    values = [float(value) for value in color.removeprefix('rgb(').removeprefix('rgba(').rstrip(')').split(',')[:3]]
    return .2126 * values[0] + .7152 * values[1] + .0722 * values[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', help='Path to Chromium; default: system Chromium or Playwright Chromium')
    parser.add_argument('--url', help='Test an HTTP(S) deployment instead of direct document loading')
    parser.add_argument('--screenshots', type=Path, help='Write desktop/mobile screenshots to this directory')
    args = parser.parse_args()
    html = (ROOT / 'index.html').read_text(encoding='utf-8')
    prompts = {lang: (ROOT / f'prompts/led_solder_review_{lang}.txt').read_text(encoding='utf-8').strip() for lang in LANGUAGES}
    translations = {lang: json.loads((ROOT / f'src/translations/{lang}.json').read_text(encoding='utf-8')) for lang in LANGUAGES[1:]}

    def translated(key: str, language: str) -> str:
        return key if language == 'ja' else translations[language][key]
    reports: list[str] = []
    errors: list[str] = []
    requests: list[str] = []
    executable = args.browser or shutil.which('chromium') or shutil.which('chromium-browser')
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        launch_options = {'headless': True, 'args': ['--no-sandbox']}
        if executable:
            launch_options['executable_path'] = executable
        browser = pw.chromium.launch(**launch_options)
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1, color_scheme='light', reduced_motion='reduce', accept_downloads=True)
        context.on('request', lambda req: requests.append(req.url))

        def load_page(ctx=context):
            p = ctx.new_page()
            p.set_default_timeout(5000)
            p.on('pageerror', lambda e: errors.append(str(e)))
            if args.url:
                p.goto(args.url, wait_until='load')
            else:
                p.set_content(html, wait_until='load')
            return p

        page = load_page()
        assert page.title() == 'LEDテープ はんだ付けサポート | EdelWorks'
        assert page.locator('#language-select').input_value() == 'ja'
        assert page.locator('#theme-select').input_value() == 'auto'
        assert page.locator('html').get_attribute('data-theme') == 'auto'
        assert page.locator('.brand').inner_text() == 'フルカラーLEDテープ はんだ付けサポート'
        reports.append('Text site title displays, with Japanese and automatic theme defaults')
        initial = page.locator('#prompt-output').input_value()
        assert len(initial) > 7000
        assert '未記入。実際の作業状況は未確認' in initial
        assert 'このWebページでは確認していません' in initial
        assert '最優先：はんだ付けの確認が先' in initial
        assert not page.locator('#prompt-preview').evaluate('(e) => e.open')
        reports.append('Initial prompt, unverified defaults, and post-review reinforcement rules')

        if args.screenshots:
            page.evaluate("window.scrollTo({top:0, behavior:'instant'})")
            page.screenshot(path=str(args.screenshots / 'desktop-full.png'), full_page=True)
            page.screenshot(path=str(args.screenshots / 'desktop-preview.png'))

        original_description = page.locator('meta[name="description"]').get_attribute('content')
        original_placeholder = page.locator('#product').get_attribute('placeholder')
        for language in LANGUAGES:
            page.select_option('#language-select', language)
            assert page.locator('html').get_attribute('lang') == language
            assert page.title() == translated('LEDテープ はんだ付けサポート | EdelWorks', language)
            assert page.locator('meta[name="description"]').get_attribute('content') == translated(original_description, language)
            assert page.locator('#product').get_attribute('placeholder') == translated(original_placeholder, language)
            assert page.locator('label[for="led-type"]').inner_text() == translated('使うもの', language)
            assert page.locator('#prompt-output').input_value().startswith(prompts[language])
            scope = page.locator('.scope-note').inner_text()
            for voltage in (5, 12, 24):
                assert re.search(rf'(?<!\d){voltage}\s*V(?![A-Za-z0-9])', scope), f'Missing {voltage}V scope in {language}'
            for theme in ('auto', 'light', 'dark'):
                page.select_option('#theme-select', theme)
                assert page.locator('html').get_attribute('data-theme') == theme
                for width in (320, 375, 390, 650, 768, 1024, 1440):
                    page.set_viewport_size({'width': width, 'height': 900})
                    page.evaluate("window.scrollTo({top:0, behavior:'instant'})")
                    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), f'Overflow in {language}/{theme} at {width}px'
                if args.screenshots and theme == 'dark':
                    page.screenshot(path=str(args.screenshots / f'desktop-{language}-dark.png'))
                    page.set_viewport_size({'width': 390, 'height': 844})
                    page.screenshot(path=str(args.screenshots / f'mobile-{language}-dark.png'))
        reports.append(f'All {len(LANGUAGES)} locales translate title, metadata, labels, placeholders, and prompts; no overflow in all {len(LANGUAGES) * 3 * 7} locale/theme/width combinations')

        def body_color() -> str:
            return page.evaluate('getComputedStyle(document.body).backgroundColor')

        page.select_option('#theme-select', 'auto')
        page.emulate_media(color_scheme='light')
        light = body_color()
        page.emulate_media(color_scheme='dark')
        dark = body_color()
        assert brightness(light) > 180 and brightness(dark) < 90, (light, dark)
        page.select_option('#theme-select', 'light')
        assert body_color() == light
        page.emulate_media(color_scheme='light')
        page.select_option('#theme-select', 'dark')
        assert body_color() == dark
        page.emulate_media(media='print')
        assert brightness(body_color()) > 180, body_color()
        page.emulate_media(media='screen', color_scheme='light')
        page.select_option('#theme-select', 'auto')
        page.select_option('#language-select', 'ja')
        reports.append('Automatic theme follows OS preference; manual light/dark overrides it, and printing uses a light background')

        page.set_viewport_size({'width': 390, 'height': 844})
        page.evaluate("window.scrollTo({top:0, behavior:'instant'})")
        if args.screenshots:
            page.screenshot(path=str(args.screenshots / 'mobile-full.png'), full_page=True)
            page.screenshot(path=str(args.screenshots / 'mobile-top.png'))
        page.locator('#optional-fields > summary').click()
        for led_type in ('strip', 'ring', 'both', 'unknown'):
            page.select_option('#led-type', led_type)
            for stage in ('unspecified', 'uncovered', 'repaired', 'covered', 'before'):
                page.select_option('#work-stage', stage)
                text = page.locator('#prompt-output').input_value()
                assert text.startswith('# LEDテープ・LEDリング')
                assert 'このWebページでは確認していません' in text
                context_data = prompt_context(text)
                assert context_data['対象']
                assert page.locator('#stage-notice').is_visible() == (stage in ('covered', 'before'))
        reports.append('All 20 material/stage combinations and relevant notices')

        page.fill('#product', 'WS2812B、5V（製品表示）')
        malicious = '</textarea><script>window.__xss = true</script>\n中央の端子が気になります。'
        page.fill('#concern', malicious)
        text = page.locator('#prompt-output').input_value()
        assert 'WS2812B、5V（製品表示）' in text
        assert page.evaluate('window.__xss === undefined')
        data = prompt_context(text)
        assert data['気になる点・使用予定（利用者の自由記入）'] == malicious
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        reports.append('Optional form values are included as data, not executed HTML')

        page.locator('#preview-btn').click()
        page.wait_for_function("document.getElementById('preview-btn').getAttribute('aria-expanded') === 'true'")
        page.locator('#select-btn').click()
        assert page.locator('#prompt-output').evaluate('(e) => e.selectionStart === 0 && e.selectionEnd === e.value.length')
        reports.append('Preview state, accessible disclosure, and full-text selection')

        for language in LANGUAGES:
            page.select_option('#language-select', language)
            assert page.locator('#product').input_value() == 'WS2812B、5V（製品表示）'
            assert page.locator('#concern').input_value() == malicious
            assert page.locator('#led-type').input_value() == 'unknown'
            assert page.locator('#work-stage').input_value() == 'before'
            text = page.locator('#prompt-output').input_value()
            assert text.startswith(prompts[language])
            data = prompt_context(text)
            assert data[translated('気になる点・使用予定（利用者の自由記入）', language)] == malicious
            assert data[translated('電源切断・測定・動作確認の実施状況', language)] == translated('このWebページでは確認していません', language)
            for stage, key in (
                ('covered', '隠れた接合部は判断できません。覆う前の写真があれば使い、撮影のためだけに無理に剥がさないでください。'),
                ('before', '写真レビューは、はんだ付けして接合部が冷めてから。電源を外し、覆う前の状態で撮影してください。'),
            ):
                page.select_option('#work-stage', stage)
                assert page.locator('#stage-notice').inner_text() == translated(key, language)
            assert page.evaluate('window.__xss === undefined')
            with page.expect_download() as item:
                page.locator('#download-btn').click()
            download = item.value
            assert download.suggested_filename == f'led-solder-review-{language}.txt'
            with tempfile.TemporaryDirectory() as tmp:
                saved = Path(tmp) / download.suggested_filename
                download.save_as(saved)
                assert saved.read_bytes().startswith(b'\xef\xbb\xbf')
                assert saved.read_text(encoding='utf-8-sig') == page.locator('#prompt-output').input_value()
        page.select_option('#language-select', 'ja')
        reports.append('Language switching preserves all form values, translates context keys/values and notices, and downloads exact UTF-8 BOM content with each language filename')

        # Deterministic API-success path, not a claim about OS clipboard permissions.
        page.evaluate("""() => {
            Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true });
            Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
                writeText: async (text) => { window.__copiedText = text; }
            }});
        }""")
        page.locator('#copy-btn').click()
        page.wait_for_function("document.getElementById('status').dataset.type === 'success'")
        assert page.evaluate('window.__copiedText') == page.locator('#prompt-output').input_value()
        reports.append('Clipboard API success path (mocked API)')

        for language in LANGUAGES[1:]:
            page.select_option('#language-select', language)
            page.locator('#copy-btn').click()
            page.wait_for_function("document.getElementById('status').dataset.type === 'success'")
            assert page.locator('#status').inner_text() == translated('コピーしました。画像対応AIのチャットに貼り付けて送信し、続けて写真を送ってください。', language)
            assert page.locator('#copy-label').inner_text() == translated('コピーしました', language)
        page.select_option('#language-select', 'ja')
        reports.append('Copy success status and button label use the selected language')

        # A delayed clipboard completion must not claim the newly displayed text was copied.
        for change in ('language', 'input'):
            page.evaluate("""() => {
                navigator.clipboard.writeText = (text) => new Promise((resolve) => {
                    window.__completeCopy = () => { window.__copiedText = text; resolve(); };
                });
            }""")
            old_text = page.locator('#prompt-output').input_value()
            page.locator('#copy-btn').click()
            page.wait_for_function("typeof window.__completeCopy === 'function'")
            language = 'en' if change == 'language' else 'ja'
            if change == 'language':
                page.select_option('#language-select', language)
            else:
                page.fill('#concern', malicious + '\n追記')
            assert page.locator('#prompt-output').input_value() != old_text
            page.evaluate('window.__completeCopy()')
            page.wait_for_function("document.getElementById('status').dataset.type === 'warning'")
            assert page.evaluate('window.__copiedText') == old_text
            assert page.locator('#status').inner_text() == translated('変更前の内容がコピーされました。現在の内容をもう一度コピーしてください。', language)
            page.select_option('#language-select', 'ja')
            page.fill('#concern', malicious)
            page.evaluate('delete window.__completeCopy')
        reports.append('Changing language or input during delayed copying reports the older copied content and asks to copy again')

        page.evaluate("""() => {
            navigator.clipboard.writeText = async () => { throw new Error('Permission denied'); };
            document.execCommand = () => { window.__legacyText = document.activeElement.value; return true; };
        }""")
        page.locator('#copy-btn').click()
        page.wait_for_function("window.__legacyText !== undefined")
        assert page.evaluate('window.__legacyText') == page.locator('#prompt-output').input_value()
        reports.append('Clipboard permission refusal and successful compatibility path (mocked)')

        page.evaluate('document.execCommand = () => false')
        page.locator('#copy-btn').click()
        page.wait_for_function("document.getElementById('status').dataset.type === 'warning'")
        assert '自動コピーが使えませんでした' in page.locator('#status').inner_text()
        assert page.locator('#prompt-output').evaluate('(e) => e.selectionStart === 0 && e.selectionEnd === e.value.length')
        reports.append('Total clipboard refusal opens/selects full text and explains manual copying')

        # The file's own fragment links must open closed source disclosures.
        page.evaluate("location.hash = 'source-6'")
        page.wait_for_function("document.getElementById('sources').open")
        assert page.locator('#source-6').is_visible()
        reports.append('Reference fragment opens the source accordion')

        nojs_context = browser.new_context(java_script_enabled=False, viewport={'width': 390, 'height': 844}, color_scheme='dark')
        nojs = load_page(nojs_context)
        assert '最優先：はんだ付けの確認が先' in nojs.locator('#prompt-output').input_value()
        assert nojs.locator('noscript').is_visible()
        assert brightness(nojs.evaluate('getComputedStyle(document.body).backgroundColor')) < 90
        assert not nojs.evaluate('document.documentElement.scrollWidth > innerWidth')
        nojs_context.close()
        reports.append('JavaScript-disabled fallback preserves the full Japanese prompt and follows the OS dark theme without overflow')

        if not args.url:
            assert not [u for u in requests if u.startswith(('http:', 'https:'))], requests
        assert not errors, errors
        reports.append('No uncaught JavaScript errors or app-originated network requests')
        print(json.dumps({'status': 'PASS', 'browser': browser.version, 'load_mode': 'URL' if args.url else 'direct document', 'checks': reports, 'limitations': ['Clipboard APIs mocked; OS clipboard not tested', 'Physical mobile devices not tested', 'AI photo-assessment quality not tested']}, ensure_ascii=False, indent=2))
        browser.close()


if __name__ == '__main__':
    main()
