#!/usr/bin/env python3
"""Prepara fontes privadas no monorepo de build Keiyoushi."""
import argparse
from pathlib import Path
import re
import shutil

def discover(src):
    return [
        (lang.name, ext.name, ext)
        for lang in sorted(src.iterdir()) if lang.is_dir()
        for ext in sorted(lang.iterdir())
        if ext.is_dir() and (ext / "build.gradle.kts").is_file()
    ]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("src", type=Path)
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--list-only", action="store_true")
    opts = parser.parse_args()
    modules = discover(opts.src)
    if not modules:
        parser.error("Nenhum módulo em src/<idioma>/<fonte>")
    if opts.list_only:
        for lang, name, _ in modules:
            print(f":src:{lang}:{name}")
        return

    settings_file = opts.upstream / "settings.gradle.kts"
    config = settings_file.read_text(encoding="utf-8")
    config, n = re.subn(
        r"(?m)^([ \t]*)loadAllIndividualExtensions\(\)[ \t]*$",
        r"\1// loadAllIndividualExtensions() // private build",
        config,
    )
    if n != 1:
        parser.error(f"Upstream mudou a inicialização do Gradle: {n} ocorrências")
    for lang, name, module in modules:
        dest = opts.upstream / "src" / lang / name
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(module, dest)
        config += f'\nloadIndividualExtension("{lang}", "{name}")\n'
    settings_file.write_text(config, encoding="utf-8")
    print(f"Módulos preparados: {len(modules)}")

if __name__ == "__main__":
    main()
