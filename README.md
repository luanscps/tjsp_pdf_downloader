# tjsp_pdf_downloader

Downloader automático de PDFs do portal **EPROC/TJSP** — testado no sistema de **Consulta Unificada de Processos**, **Consulta Avançada com Número e Chave de Acesso**.

Suporta dois modos de operação:

| Modo | Arquivo | Quando usar |
|---|---|---|
| `requests` direto | `tjsp_pdf_downloader_v5.py` | PDFs simples, sem renderização |
| `Playwright` (impressão) | `tjsp_print_to_pdf_playwright.py` | PDFs com texto corrompido ou assinados digitalmente |

---

## Problema resolvido

Documentos baixados diretamente do portal EPROC muitas vezes apresentam:

- Texto corrompido ao copiar (fontes incorporadas ou assinatura digital).
- Conteúdo ilegível fora do visualizador do navegador.

A abordagem via **Playwright** abre o documento no Chromium, renderiza a página completa e salva usando o mecanismo de **impressão para PDF** do próprio navegador — equivalente ao "Imprimir → Salvar como PDF" feito manualmente.

---

## Requisitos

```bash
pip install requests playwright
python -m playwright install chromium
```

Python 3.10 ou superior recomendado.

---

## Modo 1 — Download direto via `requests`

### Uso

```bash
python tjsp_pdf_downloader_v5.py --input urls.txt --limit 5 --cookie-header "PHPSESSID=SEU_COOKIE" --output-dir downloads --save-html-debug
```

### Argumentos

| Argumento | Padrão | Descrição |
|---|---|---|
| `--input` | `urls_extraidos.txt` | Arquivo `.txt` com uma URL por linha |
| `--output-dir` | `downloads` | Pasta de saída dos PDFs |
| `--workers` | `1` | Downloads paralelos |
| `--timeout` | `90` | Timeout de leitura em segundos |
| `--skip-existing` | `True` | Pula arquivos já baixados |
| `--cookie-header` | — | Cookies da sessão: `PHPSESSID=valor` |
| `--user-agent` | Chrome 143 | User-Agent do navegador |
| `--referer` | — | Referer da requisição |
| `--log-json` | `download_log.json` | Log de resultados em JSON |
| `--limit` | `1` | Processa apenas N URLs (0 = todas) |
| `--save-html-debug` | — | Salva HTML intermediário em `debug_html/` |

### Estrutura de saída

```
downloads/
  nome_do_arquivo.pdf
  .tmp/
  debug_html/
    001.html
download_log.json
```

---

## Modo 2 — Impressão via Playwright (recomendado para PDFs com texto corrompido)

### Uso

```bash
python tjsp_print_to_pdf_playwright.py --input urls.txt --limit 1 --cookie-header "PHPSESSID=SEU_COOKIE" --referer "https://eproc-consulta.tjsp.jus.br/consulta_1g/controlador.php?acao=acessar_documento_publico" --output-dir downloads_print --debug-html
```

### Argumentos

| Argumento | Padrão | Descrição |
|---|---|---|
| `--input` | `1.txt` | Arquivo `.txt` com uma URL por linha |
| `--output-dir` | `downloads_print` | Pasta de saída dos PDFs |
| `--limit` | `1` | Processa apenas N URLs (0 = todas) |
| `--cookie-header` | — | Cookies da sessão: `PHPSESSID=valor` |
| `--referer` | — | URL de entrada da consulta (recomendado) |
| `--user-agent` | Chrome 143 | User-Agent do navegador |
| `--show-browser` | — | Exibe o navegador visualmente durante execução |
| `--wait-ms` | `2500` | Espera extra após carregamento em ms |
| `--timeout-ms` | `45000` | Timeout total por página em ms |
| `--debug-html` | — | Salva HTML da página carregada em `debug/` |

### Estrutura de saída

```
downloads_print/
  controlador.php.pdf
  debug/
    001.html
results.json
```

---

## Como obter o cookie de sessão

1. Abra o portal EPROC no Chrome.
2. Acesse a **Consulta Avançada** com número e chave de acesso.
3. Pressione `F12` → aba **Network** → clique em qualquer requisição ao portal.
4. Na aba **Headers**, copie o valor do campo `Cookie:`.
5. Use esse valor no argumento `--cookie-header`.

> **Atenção:** O cookie de sessão expira com o tempo. Se o download falhar com redirecionamento para login, obtenha um novo cookie.

---

## Formato do arquivo de entrada (`urls.txt`)

Uma URL por linha, sem cabeçalhos:

```
https://eproc-consulta.tjsp.jus.br/consulta_1g/controlador.php?acao=acessar_documento_publico&doc=XXX&evento=YYY&key=ZZZ&hash=WWW
https://eproc-consulta.tjsp.jus.br/consulta_1g/controlador.php?acao=acessar_documento_publico&doc=AAA&evento=BBB&key=CCC&hash=DDD
```

Linhas em branco e que não iniciam com `http://` ou `https://` são ignoradas automaticamente.

---

## Fluxo interno (Modo 1)

```
main()
  read_urls()           → carrega URLs do arquivo de entrada
  download_one()        → processa cada URL
    build_session()     → cria sessão HTTP com cookie/User-Agent/Referer
    fetch_document()    → GET na URL
                          se retornar HTML → segue iframe#conteudoIframe
                          retorna conteúdo final (binário)
    valida PDF          → verifica assinatura %PDF-
    infer_name()        → extrai nome do Content-Disposition ou query string
    salva arquivo       → move de .tmp para destino final
  gera log JSON         → download_log.json
```

---

## Sistema testado

| Campo | Valor |
|---|---|
| Sistema | EPROC — Consulta Unificada de Processos |
| Modalidade | Consulta Avançada com Número e Chave de Acesso |
| Portal | `eproc-consulta.tjsp.jus.br` |
| Ação | `acessar_documento_publico` |
| Sistema operacional | Windows 10 |
| Python | 3.10+ |

---

## Licença

MIT
