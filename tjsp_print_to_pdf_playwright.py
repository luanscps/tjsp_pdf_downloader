#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse, urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
BASE_URL = "https://eproc-consulta.tjsp.jus.br/consulta_1g/"


def complete_url(line: str) -> str:
    """Se a linha nao comecar com http, adiciona a URL base do EPROC."""
    line = line.strip()
    if line.startswith(('http://', 'https://')):
        return line
    return BASE_URL + line.lstrip('/')


def read_urls(path: Path) -> list[str]:
    txt = path.read_text(encoding='utf-8', errors='ignore')
    urls = []
    for line in txt.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(('http://', 'https://')) or 'controlador.php' in line or 'acao=' in line:
            urls.append(complete_url(line))
    return urls


def safe_name(url: str, index: int) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name or f'documento_{index:03d}'
    name = re.sub(r'[\\/:*?"<>|]+', '_', name)
    if not name.lower().endswith('.pdf'):
        name += '.pdf'
    return name


def main():
    ap = argparse.ArgumentParser(description='Abre o documento no Chromium e salva como PDF impresso. Links relativos sao completados automaticamente.')
    ap.add_argument('--input', default='1.txt')
    ap.add_argument('--output-dir', default='downloads_print')
    ap.add_argument('--limit', type=int, default=1)
    ap.add_argument('--cookie-header', help='Cookie do Chrome no formato nome=valor; nome2=valor2')
    ap.add_argument('--referer', help='Referer inicial')
    ap.add_argument('--user-agent', default=UA)
    ap.add_argument('--show-browser', action='store_true')
    ap.add_argument('--wait-ms', type=int, default=2500)
    ap.add_argument('--timeout-ms', type=int, default=45000)
    ap.add_argument('--debug-html', action='store_true')
    args = ap.parse_args()

    urls = read_urls(Path(args.input))
    if args.limit > 0:
        urls = urls[:args.limit]
    if not urls:
        raise SystemExit('Nenhuma URL valida encontrada.')

    print(f'[info] {len(urls)} URL(s) carregada(s). Base URL aplicada automaticamente para links relativos.')

    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    debugdir = outdir / 'debug'
    debugdir.mkdir(parents=True, exist_ok=True)
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.show_browser, args=['--disable-blink-features=AutomationControlled'])
        context = browser.new_context(
            user_agent=args.user_agent,
            accept_downloads=True,
            viewport={'width': 1600, 'height': 1200},
        )
        if args.cookie_header:
            cookie_url = args.referer or urls[0]
            pu = urlparse(cookie_url)
            domain = pu.hostname or 'eproc-consulta.tjsp.jus.br'
            cookies = []
            for part in args.cookie_header.split(';'):
                if '=' in part:
                    k, v = part.strip().split('=', 1)
                    cookies.append({'name': k.strip(), 'value': v.strip(), 'domain': domain, 'path': '/'})
            if cookies:
                context.add_cookies(cookies)

        for idx, url in enumerate(urls, 1):
            page = context.new_page()
            page.set_default_timeout(args.timeout_ms)
            try:
                if args.referer:
                    page.goto(args.referer, wait_until='domcontentloaded')
                page.goto(url, wait_until='domcontentloaded')
                page.wait_for_load_state('networkidle', timeout=args.timeout_ms)
                page.wait_for_timeout(args.wait_ms)

                try:
                    iframe = page.locator('iframe#conteudoIframe')
                    if iframe.count() > 0:
                        src = iframe.first.get_attribute('src')
                        if src:
                            iframe_url = urljoin(page.url, src)
                            page.goto(iframe_url, wait_until='domcontentloaded')
                            page.wait_for_load_state('networkidle', timeout=args.timeout_ms)
                            page.wait_for_timeout(args.wait_ms)
                except Exception:
                    pass

                if args.debug_html:
                    (debugdir / f'{idx:03d}.html').write_text(page.content(), encoding='utf-8', errors='ignore')

                pdf_name = safe_name(url, idx)
                pdf_path = outdir / pdf_name
                page.emulate_media(media='print')
                page.pdf(path=str(pdf_path), print_background=True, prefer_css_page_size=True)
                results.append({'index': idx, 'url': url, 'status': 'ok', 'file': str(pdf_path)})
                print(f'[ok] {idx:03d} {pdf_path.name}')
            except PlaywrightTimeoutError as e:
                results.append({'index': idx, 'url': url, 'status': 'error', 'detail': f'TimeoutError: {e}'})
                print(f'[error] {idx:03d} TimeoutError: {e}')
            except Exception as e:
                results.append({'index': idx, 'url': url, 'status': 'error', 'detail': f'{type(e).__name__}: {e}'})
                print(f'[error] {idx:03d} {type(e).__name__}: {e}')
            finally:
                page.close()

        browser.close()

    (outdir / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
