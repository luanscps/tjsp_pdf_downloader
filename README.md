# tjsp_pdf_downloader

Downloader automático de PDFs do portal **EPROC/TJSP** — testado no sistema de **Consulta Unificada de Processos**, **Consulta Avançada com Número e Chave de Acesso**.

Suporta dois modos de operação:

| Modo | Arquivo | Quando usar |
|---|---|---|
| `requests` direto | `tjsp_pdf_downloader_v5.py` | PDFs simples, sem renderização |
| `Playwright` (impressão) | `tjsp_print_to_pdf_playwright.py` | PDFs com texto corrompido ou assinados digitalmente |

---

## Fluxo completo — do processo ao download

Este é o passo a passo completo de como utilizar o downloader, desde acessar o processo no EPROC até ter os PDFs salvos na sua máquina.

### Passo 1 — Acessar o processo no EPROC

1. Acesse o portal: [https://eproc-consulta.tjsp.jus.br/consulta_1g/externo/controlador.php?acao=tjspconsultaunificadapublicaconsultar](https://eproc-consulta.tjsp.jus.br/consulta_1g/externo/controlador.php?acao=tjspconsultaunificadapublicaconsultar)
2. Selecione a opção **Consulta Avançada**.
3. Informe o **número do processo** e a **chave de acesso** (fornecida pelo tribunal ou pela parte).
4. Clique em **Consultar**.
5. A página de **Detalhes do Processo** será aberta, exibindo todos os eventos com seus respectivos documentos.

### Passo 2 — Extrair o código-fonte da página

Com a página de detalhes do processo aberta no Chrome:

1. Pressione `Ctrl + U` (Windows/Linux) ou `Cmd + U` (Mac) para abrir o **código-fonte** da página.
2. Pressione `Ctrl + A` para selecionar todo o HTML.
3. Pressione `Ctrl + C` para copiar.
4. Cole em um arquivo de texto (`.html` ou `.txt`) ou diretamente em uma IA.

> **Dica:** Você também pode salvar diretamente com `Ctrl + S` no Chrome e escolher "Página Web, somente HTML".

### Passo 3 — Identificar os links dos documentos no HTML

Dentro do HTML da página, cada documento de cada evento aparece como uma tag `<a>` com a classe `infraLinkDocumento`. O atributo `href` contém o link relativo do arquivo.

Exemplo real extraído do HTML:

```html
<a class="infraLinkDocumento"
   href="controlador.php?acao=acessar_documento_publico&doc=611780923064886376183340167286&evento=611780923064886376183355344561&key=9a2990525948846865d1e45f2252b711c72df347bfbbc7a9223e7a6ca0dec7d0&hash=64a2a74226e2a8a3233524f9e260c768"
   target="_blank"
   aria-label="Visualizar documento AR1 do tipo pdf">
  <img src="infracss/imagens/consultar.gif" title="Visualizar Documento" />
</a>
```

Os parâmetros importantes do link são:

| Parâmetro | Descrição |
|---|---|
| `acao` | Sempre `acessar_documento_publico` |
| `doc` | ID único do documento |
| `evento` | ID do evento ao qual o documento pertence |
| `key` | Chave de autenticação do documento |
| `hash` | Hash de verificação de integridade |

### Passo 4 — Limpar o HTML com uma IA

Copie o HTML completo da página e envie para uma IA (ChatGPT, Perplexity, Gemini etc.) com o seguinte prompt:

```
Do HTML abaixo, extraia apenas os valores do atributo href das tags <a class="infraLinkDocumento"> e <a class="infraLinkDocumentoSigiloso">.
Retorne somente os links, um por linha, sem nenhum texto adicional, sem numeração, sem aspas.
Não inclua links que não sejam de acessar_documento_publico.

[COLE O HTML AQUI]
```

O resultado esperado é uma lista limpa assim:

```
controlador.php?acao=acessar_documento_publico&doc=611780923064886376183340167286&evento=611780923064886376183355344561&key=9a2990525948846865d1e45f2252b711c72df347bfbbc7a9223e7a6ca0dec7d0&hash=64a2a74226e2a8a3233524f9e260c768
controlador.php?acao=acessar_documento_publico&doc=611781870567893535682811167482&evento=611781870567893535682811365477&key=21c3d35e5c16e457b6035d034a7907444fcc3494152c9cd9e1b2cb343ee05417&hash=d2a1226c5055e8267eecb2ac99159ec8
```

### Passo 5 — Salvar os links no arquivo de entrada

Salve os links extraídos em um arquivo de texto chamado `1.txt` (ou qualquer nome, configurável com `--input`), um link por linha.

> ✅ **Não é necessário adicionar a URL base manualmente.** Os scripts completam automaticamente para:
> `https://eproc-consulta.tjsp.jus.br/consulta_1g/`

Se o link já estiver completo (começando com `https://`), ele será usado como está.

Exemplo de `1.txt` com links relativos (funciona diretamente):

```
controlador.php?acao=acessar_documento_publico&doc=611780923064886376183340167286&evento=611780923064886376183355344561&key=9a2990525948846865d1e45f2252b711c72df347bfbbc7a9223e7a6ca0dec7d0&hash=64a2a74226e2a8a3233524f9e260c768
controlador.php?acao=acessar_documento_publico&doc=611781870567893535682811167482&evento=611781870567893535682811365477&key=21c3d35e5c16e457b6035d034a7907444fcc3494152c9cd9e1b2cb343ee05417&hash=d2a1226c5055e8267eecb2ac99159ec8
```

### Passo 6 — Obter o cookie de sessão

1. Abra o portal EPROC no Chrome com o processo já consultado.
2. Pressione `F12` → aba **Network**.
3. Clique em qualquer requisição ao domínio `eproc-consulta.tjsp.jus.br`.
4. Na aba **Headers**, localize o campo **Cookie:** e copie seu valor completo.
5. Use esse valor no argumento `--cookie-header`.

> **Atenção:** O cookie expira com o tempo ou ao fechar a sessão. Se o download falhar ou redirecionar para a tela de login, obtenha um novo cookie.

### Passo 7 — Executar o download

Com o arquivo `1.txt` criado e o cookie em mãos, execute:

```bash
# Modo requests (mais rápido)
python tjsp_pdf_downloader_v5.py --input 1.txt --limit 0 --cookie-header "PHPSESSID=SEU_COOKIE" --output-dir downloads

# Modo Playwright (PDFs com texto corrompido)
python tjsp_print_to_pdf_playwright.py --input 1.txt --limit 0 --cookie-header "PHPSESSID=SEU_COOKIE" --output-dir downloads_print
```

`--limit 0` significa baixar **todos** os links do arquivo.

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
python tjsp_pdf_downloader_v5.py --input 1.txt --limit 5 --cookie-header "PHPSESSID=SEU_COOKIE" --output-dir downloads --save-html-debug
```

### Argumentos

| Argumento | Padrão | Descrição |
|---|---|---|
| `--input` | `urls_extraidos.txt` | Arquivo `.txt` com uma URL por linha (relativa ou absoluta) |
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
  AR1.pdf
  EMAIL1.pdf
  .tmp/
  debug_html/
    001.html
download_log.json
```

---

## Modo 2 — Impressão via Playwright (recomendado para PDFs com texto corrompido)

### Uso

```bash
python tjsp_print_to_pdf_playwright.py --input 1.txt --limit 1 --cookie-header "PHPSESSID=SEU_COOKIE" --referer "https://eproc-consulta.tjsp.jus.br/consulta_1g/" --output-dir downloads_print --debug-html
```

### Argumentos

| Argumento | Padrão | Descrição |
|---|---|---|
| `--input` | `1.txt` | Arquivo `.txt` com uma URL por linha (relativa ou absoluta) |
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

## Problema resolvido

Documentos baixados diretamente do portal EPROC muitas vezes apresentam:

- Texto corrompido ao copiar (fontes incorporadas ou assinatura digital).
- Conteúdo ilegível fora do visualizador do navegador.

A abordagem via **Playwright** abre o documento no Chromium, renderiza a página completa e salva usando o mecanismo de **impressão para PDF** do próprio navegador — equivalente ao "Imprimir → Salvar como PDF" feito manualmente.

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
