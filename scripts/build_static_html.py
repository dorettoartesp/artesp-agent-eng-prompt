#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
import unicodedata
from typing import Iterable

# Nota: importamos `markdown` de forma tardia dentro das funções para permitir `--dry-run`


def slugify(text: str) -> str:
    """
    Gera um slug ASCII amigável para URLs/nomes de arquivo.
    - Normaliza acentos (NFKD) -> ASCII
    - Converte espaços e separadores em '-'
    - Remove qualquer caractere não [a-z0-9-]
    - Condensa hífens contínuos
    """
    # Normaliza acentos e converte para ASCII
    text = (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    text = text.lower().strip()
    # Substitui separadores por '-'
    text = re.sub(r"[\s_/:+]+", "-", text)
    # Mantém apenas [a-z0-9-]
    text = re.sub(r"[^a-z0-9-]", "", text)
    # Condensa múltiplos '-'
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "page"


def find_title(md_text: str, fallback: str) -> str:
    """Extrai o primeiro título de nível 1 (# ...) do Markdown; se não houver, usa fallback."""
    for line in md_text.splitlines():
        if line.lstrip().startswith("# "):
            return line.lstrip()[2:].strip()
    return fallback


def discover_markdown_files(indir: Path) -> Iterable[Path]:
    for p in sorted(indir.glob("**/*.md")):
        if p.is_file():
            yield p


def ensure_unique(path: Path) -> Path:
    """Evita sobrescrever: se já existir, adiciona sufixo -2, -3, ..."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    n = 2
    while True:
        candidate = path.with_name(f"{stem}-{n}{suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def render_html_document(title: str, body_html: str, lang: str = "pt-BR") -> str:
    """Envolve o HTML do corpo em um documento HTML5 simples e estático."""
    # Estilos leves para legibilidade e sem dependência externa
    styles = """
    :root { --maxw: 920px; --pad: 16px; --font: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, 'Helvetica Neue', Arial, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol'; }
    * { box-sizing: border-box; }
    html { font-size: 16px; }
    body { margin: 0; font-family: var(--font); line-height: 1.6; color: #111; background: #fff; }
    main { max-width: var(--maxw); margin: 0 auto; padding: calc(var(--pad) * 1.5) var(--pad); }
    h1, h2, h3, h4 { line-height: 1.25; }
    pre { background: #f6f8fa; padding: 12px; overflow: auto; border-radius: 6px; }
    code { background: #f6f8fa; padding: 2px 4px; border-radius: 4px; }
    a { color: #0969da; text-decoration: none; }
    a:hover { text-decoration: underline; }
    hr { border: 0; border-top: 1px solid #eaecef; margin: 24px 0; }
    blockquote { margin: 0; padding-left: 1rem; border-left: 4px solid #eaecef; color: #57606a; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #d0d7de; padding: 6px 8px; }
    th { background: #f6f8fa; }
    """
    return f"""<!doctype html>
<html lang="{lang}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="robots" content="index,follow" />
  <title>{title}</title>
  <meta name="description" content="{title} - versão HTML estática" />
  <style>{styles}</style>
</head>
<body>
  <main>
    <h1>{title}</h1>
    {body_html}
  </main>
</body>
</html>"""


def convert_markdown_to_html(md_text: str) -> str:
    """Converte Markdown para HTML usando a lib `markdown` (python-markdown)."""
    try:
        import markdown  # type: ignore
    except ImportError as e:
        print(
            "Erro: biblioteca 'markdown' não encontrada.\n"
            "Instale com um dos comandos:\n"
            "  - uv add markdown\n"
            "  - pip install markdown\n",
            file=sys.stderr,
        )
        raise

    # Extensões úteis e leves
    extensions = [
        "extra",            # inclui tabelas, abreviações, etc.
        "toc",              # gera âncoras para títulos
        "admonition",
        "sane_lists",
        "smarty",
        "fenced_code",
    ]
    return markdown.markdown(md_text, extensions=extensions, output_format="html5")


def build(
    input_dir: Path,
    output_dir: Path,
    overwrite: bool = False,
    dry_run: bool = False,
    naming: str = "title",
) -> int:
    md_files = list(discover_markdown_files(input_dir))
    if not md_files:
        print(f"Nenhum arquivo .md encontrado em: {input_dir}")
        return 0

    print(f"Encontrados {len(md_files)} arquivo(s) Markdown em {input_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    exit_code = 0

    for md_path in md_files:
        md_text = md_path.read_text(encoding="utf-8")
        title = find_title(md_text, fallback=md_path.stem)

        # Nome do arquivo de saída
        if naming == "filename":
            base_slug = slugify(md_path.stem)
        else:
            base_slug = slugify(title) or slugify(md_path.stem)
        out_name = f"{base_slug}.html"
        out_path = output_dir / out_name

        if not overwrite:
            out_path = ensure_unique(out_path)

        rel_in = md_path.relative_to(input_dir)
        rel_out = out_path.relative_to(output_dir)

        if dry_run:
            print(f"[dry-run] {rel_in} -> {rel_out}")
            continue

        try:
            body_html = convert_markdown_to_html(md_text)
        except ImportError:
            return 1
        html = render_html_document(title=title, body_html=body_html)
        out_path.write_text(html, encoding="utf-8")
        print(f"Gerado: {rel_in} -> {rel_out}")

    return exit_code


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="build_static_html",
        description=(
            "Converte arquivos Markdown (.md) em HTML estático simples, sem JS. "
            "Ideal para indexação e leitura por agentes de IA."
        ),
    )
    p.add_argument(
        "--input",
        "-i",
        type=Path,
        default=Path("docs"),
        help="Diretório de entrada com arquivos .md (padrão: ./docs)",
    )
    p.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("."),
        help="Diretório de saída para os .html gerados (padrão: .)",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Sobrescreve arquivos .html existentes com o mesmo nome (padrão: cria sufixos -2, -3, ...)"
        ),
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o que seria gerado sem escrever arquivos",
    )
    p.add_argument(
        "--naming",
        choices=["title", "filename"],
        default="title",
        help=(
            "Estratégia para nomear os arquivos HTML: 'title' usa o primeiro H1; 'filename' usa o nome do arquivo .md"
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    ns = parse_args(sys.argv[1:] if argv is None else argv)
    return build(
        input_dir=ns.input,
        output_dir=ns.output,
        overwrite=ns.overwrite,
        dry_run=ns.dry_run,
        naming=ns.naming,
    )


if __name__ == "__main__":
    raise SystemExit(main())

