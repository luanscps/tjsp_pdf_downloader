#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
PDF_MAGIC = b"%PDF-"
BASE_URL = "https://eproc-consulta.tjsp.jus.br/consulta_1g/"


def slugify(name: str) -> str:
    name = unquote(name)
    name = re.sub(r'[\\/:*?"<>|]+', '_', name)
    name = re.sub(r'[\s]+', ' ', name).strip()
    return name[:180].strip(' ._') or 'arquivo'


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    i = 2
    while True:
        cand = path.with_name(f'{path.stem}__{i}{path.suffix}')
        if not cand.exists():
            return cand
        i += 1


def complete_url(line: str) -> str:
    """Se a linha nao comecar com http, adiciona a URL base do EPROC."""
    line = line.strip()
    if line.startswith(('http://', 'https://')):
        return line
    return BASE_URL + line.lstrip('/')


def read_urls(file_path: Path) -> list[str]:
    text = file_path.read_text(encoding='utf-8', errors='ignore')
    urls = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # aceita links relativos (controlador.php?...) e absolutos (https://...)
        if line.startswith(('http://', 'https://')) or 'controlador.php' in line or 'acao=' in line:
            urls.append(complete_url(line))
    return urls


def build_session(args) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        'User-Agent': args.user_agent,
        'Accept': 'application/pdf,application/octet-stream,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
    })
    if args.referer:
        s.headers['Referer'] = args.referer
    if args.cookie_header:
        for part in args.cookie_header.split(';'):
            if '=' in part:
                k, v = part.strip().split('=', 1)
                s.cookies.set(k.strip(), v.strip())
    return s


def infer_name(resp, url, index):
    cd = resp.headers.get('Content-Disposition', '')
    m = re.search(r"filename\*?=(?:UTF-8''|\")?([^\"\s;]+)", cd, re.I)
    if m:
        name = slugify(m.group(1).strip().strip('"'))
    else:
        parsed = urlparse(resp.url or url)
        qs = parse_qs(parsed.query)
        base = None
        for key in ('nome', 'filename', 'file', 'doc', 'evento'):
            if key in qs and qs[key]:
                base = qs[key][0]
                break
        if not base:
            tail = Path(parsed.path).name
            base = tail if tail else f'documento_{index:03d}'
        name = slugify(str(base))
    if not name.lower().endswith('.pdf'):
        name += '.pdf'
    return name


def fetch_document(session: requests.Session, url: str, args):
    resp = session.get(url, timeout=(15, args.timeout), allow_redirects=True)
    resp.raise_for_status()
    content = resp.content
    ctype = (resp.headers.get('Content-Type') or '').lower()
    if 'html' in ctype or b'<html' in content[:6000].lower():
        html = content.decode('utf-8', errors='ignore')
        for pat in [
            r'<iframe[^>]+id="conteudoIframe"[^>]+src="([^"]+)"',
            r'<iframe[^>]+src="([^"]+)"',
            r'src="([^"]*acessar_documento_[^"]+)"',
            r'href="([^"]*acessar_documento_[^"]+)"',
        ]:
            m = re.search(pat, html, re.I)
            if not m:
                continue
            iframe_url = urljoin(resp.url, m.group(1).replace('&amp;', '&'))
            r2 = session.get(iframe_url, timeout=(15, args.timeout), allow_redirects=True)
            r2.raise_for_status()
            c2 = (r2.headers.get('Content-Type') or '').lower()
            c2content = r2.content
            if b'%PDF-' in c2content[:2048] or ('pdf' in c2 and not c2content.startswith(b'<!DOCTYPE')):
                return r2, c2content, c2
    return resp, content, ctype


def download_one(index, url, args):
    session = build_session(args)
    dest_dir = Path(args.output_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = dest_dir / '.tmp'
    temp_dir.mkdir(parents=True, exist_ok=True)
    debug_dir = dest_dir / 'debug_html'
    debug_dir.mkdir(parents=True, exist_ok=True)
    meta = {'index': index, 'url': url, 'status': 'error', 'file': None, 'detail': None}
    try:
        resp, content, ctype = fetch_document(session, url, args)
        if not (content.startswith(PDF_MAGIC) or b'%PDF-' in content[:4096] or 'pdf' in ctype):
            if args.save_html_debug:
                (debug_dir / f'{index:03d}.html').write_bytes(content)
            preview_text = ' '.join(content[:300].decode('utf-8', errors='ignore').splitlines())[:180]
            meta['detail'] = 'conteudo nao parece PDF (content-type=' + str(resp.headers.get('Content-Type')) + ') :: ' + preview_text
            return meta
        name = infer_name(resp, url, index)
        final_path = dest_dir / name
        if final_path.exists() and args.skip_existing:
            meta.update({'status': 'skipped', 'file': str(final_path), 'detail': 'arquivo ja existe'})
            return meta
        if final_path.exists():
            final_path = unique_path(final_path)
        tmp_path = temp_dir / (final_path.name + '.part')
        tmp_path.write_bytes(content)
        shutil.move(str(tmp_path), str(final_path))
        meta.update({'status': 'ok', 'file': str(final_path), 'detail': f'{final_path.stat().st_size} bytes'})
        return meta
    except Exception as e:
        meta['detail'] = f'{type(e).__name__}: {e}'
        return meta


def main():
    p = argparse.ArgumentParser(description='Baixa PDFs do TJSP/EPROC. Links relativos sao completados automaticamente com a URL base.')
    p.add_argument('--input', default='urls_extraidos.txt')
    p.add_argument('--output-dir', default='downloads')
    p.add_argument('--workers', type=int, default=1)
    p.add_argument('--timeout', type=int, default=90)
    p.add_argument('--skip-existing', action='store_true', default=True)
    p.add_argument('--cookie-header')
    p.add_argument('--user-agent', default=UA)
    p.add_argument('--referer')
    p.add_argument('--log-json', default='download_log.json')
    p.add_argument('--limit', type=int, default=1)
    p.add_argument('--save-html-debug', action='store_true')
    args = p.parse_args()

    urls = read_urls(Path(args.input))
    if args.limit > 0:
        urls = urls[:args.limit]
    if not urls:
        print('Nenhuma URL valida encontrada.', file=sys.stderr)
        sys.exit(1)

    print(f'[info] {len(urls)} URL(s) carregada(s). Base URL aplicada automaticamente para links relativos.')

    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futures = [ex.submit(download_one, i, url, args) for i, url in enumerate(urls, 1)]
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            print(f"[{res['status']}] {res['index']:03d} {res['file'] or '-'} :: {res['detail']}")

    results.sort(key=lambda x: x['index'])
    summary = {
        'total': len(results),
        'ok': sum(r['status'] == 'ok' for r in results),
        'skipped': sum(r['status'] == 'skipped' for r in results),
        'error': sum(r['status'] == 'error' for r in results),
        'results': results,
    }
    Path(args.log_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'results'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
