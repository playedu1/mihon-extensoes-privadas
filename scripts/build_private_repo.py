#!/usr/bin/env python3
"""Gera um repositório Mihon v2 privado sem publicar nada (somente stdlib)."""
import argparse
import gzip
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlparse
from zipfile import ZipFile

def variable(number, value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)

def varfield(number, value):
    return variable(number, (number << 3)) + variable(number, int(value))

def bytesfield(number, value):
    data = value.encode("utf-8") if isinstance(value, str) else bytes(value)
    return variable(number, (number << 3) | 2) + variable(number, len(data)) + data

def base_url(value):
    value = value.rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Use a URL HTTPS real da sua rede privada (sem usuário ou senha)")
    return value

def signer_fingerprint(apk):
    sdk = Path(os.getenv("ANDROID_HOME") or os.getenv("ANDROID_SDK_ROOT") or "")
    tools = sorted((sdk / "build-tools").glob("*/apksigner"), reverse=True)
    if not tools:
        raise RuntimeError("apksigner não encontrado em ANDROID_HOME/build-tools")
    result = subprocess.check_output(
        [str(tools[0]), "verify", "--print-certs", str(apk)], text=True
    )
    match = re.search(r"Signer #1 certificate SHA-256 digest:\s*([0-9a-f:]{64,95})", result, re.I)
    if match:
        return match.group(1).lower().replace(":", "")
    return extract_v2_cert_sha256(apk)


def extract_v2_cert_sha256(apk):
    """Lê o certificado X.509 da assinatura APK Signature Scheme v2 validada por apksigner."""
    import struct

    data = Path(apk).read_bytes()
    eocd = data.rfind(b"PK\\x05\\x06")
    if eocd < 0 or eocd + 20 > len(data):
        raise ValueError("APK inválido: diretório ZIP ausente")
    cd_start = struct.unpack_from("<I", data, eocd + 16)[0]
    if data[cd_start - 16:cd_start] != b"APK Sig Block 42":
        raise ValueError("APK sem bloco de assinatura v2/v3")
    footer_size = struct.unpack_from("<Q", data, cd_start - 24)[0]
    start = cd_start - footer_size - 8
    if start < 0 or struct.unpack_from("<Q", data, start)[0] != footer_size:
        raise ValueError("Bloco de assinatura APK inválido")

    def read_prefixed(blob, offset):
        if offset + 4 > len(blob):
            raise ValueError("Assinatura APK truncada")
        size = struct.unpack_from("<I", blob, offset)[0]
        end = offset + 4 + size
        if end > len(blob):
            raise ValueError("Comprimento inválido na assinatura APK")
        return blob[offset + 4:end], end

    pos = start + 8
    while pos < cd_start - 24:
        size = struct.unpack_from("<Q", data, pos)[0]
        identifier = struct.unpack_from("<I", data, pos + 8)[0]
        if identifier == 0x7109871A:
            block = data[pos + 12:pos + 8 + size]
            signers, _ = read_prefixed(block, 0)
            signer, _ = read_prefixed(signers, 0)
            signed_data, _ = read_prefixed(signer, 0)
            _, next_pos = read_prefixed(signed_data, 0)
            certificates, _ = read_prefixed(signed_data, next_pos)
            certificate, _ = read_prefixed(certificates, 0)
            return hashlib.sha256(certificate).hexdigest()
        pos += 8 + size
    raise ValueError("Certificado APK v2 não encontrado")


def scan_builds(root, output):
    entries = []
    for meta in sorted(root.glob("*/*/build/keiyoushi-source-info.json")):
        info = json.loads(meta.read_text(encoding="utf-8"))
        apks = list((meta.parent / "outputs/apk/debug").glob("*.apk"))
        if len(apks) != 1:
            raise ValueError(f"{meta}: esperado exatamente um APK debug, encontrados {len(apks)}")
        apk = apks[0]
        fingerprint = signer_fingerprint(apk)
        package = info["packageName"]
        apk_name = package + ".apk"
        (output / "apk").mkdir(exist_ok=True, parents=True)
        (output / "icon").mkdir(exist_ok=True, parents=True)
        shutil.copy2(apk, output / "apk" / apk_name)
        with ZipFile(apk) as archive:
            icons = [x for x in archive.namelist() if x.endswith("/ic_launcher.png")]
            if icons:
                icon = next((x for x in icons if "xxxhdpi" in x), icons[-1])
                (output / "icon" / (package + ".png")).write_bytes(archive.read(icon))
        entries.append({"info": info, "apk": apk_name, "fingerprint": fingerprint,
                        "sha256": hashlib.sha256(apk.read_bytes()).hexdigest()})
    if not entries:
        raise RuntimeError("Nenhum keiyoushi-source-info.json encontrado: inclua generateSourceInfo no build")
    (output / "catalog-metadata.json").write_text(
        json.dumps(entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return entries

def render(entries, output, url):
    url = base_url(url)
    keys = {e["fingerprint"] for e in entries}
    if len(keys) != 1:
        raise RuntimeError("Extensões assinadas por certificados diferentes; configure uma assinatura única.")
    fingerprint = keys.pop()
    extension_messages = []
    legacy = []
    json_entries = []
    for e in entries:
        info = e["info"]
        package, filename = info["packageName"], e["apk"]
        if not (output / "apk" / filename).is_file():
            raise RuntimeError("APK ausente: " + filename)
        icon_name = package + ".png"
        apkurl = url + "/apk/" + filename
        iconurl = url + "/icon/" + icon_name if (output / "icon" / icon_name).exists() else ""
        resources = bytesfield(1, apkurl) + (bytesfield(2, iconurl) if iconurl else b"")
        sources = []
        source_msgs = []
        for source in info.get("sources", []):
            sid = int(source["id"])
            source_msgs.append(
                varfield(1, sid) + bytesfield(2, source["name"])
                + bytesfield(3, source["lang"]) + bytesfield(4, source["baseUrl"])
            )
            sources.append({"id": str(sid), "name": source["name"], "lang": source["lang"],
                            "baseUrl": source["baseUrl"]})
        msg = (
            bytesfield(1, info["name"])
            + bytesfield(2, package)
            + bytesfield(3, resources)
            + bytesfield(4, info["extensionLib"])
            + varfield(5, int(info["versionCode"]))
            + bytesfield(6, info["versionName"])
            + varfield(7, int(info["contentWarning"]))
            + b"".join(bytesfield(8, source_msg) for source_msg in source_msgs)
        )
        extension_messages.append(bytesfield(1, msg))
        legacy.append({"name": "Tachiyomi: " + info["name"], "pkg": package,
                       "apk": filename, "lang": sources[0]["lang"] if len(sources) == 1 else "all",
                       "code": int(info["versionCode"]), "version": info["versionName"],
                       "nsfw": int(int(info["contentWarning"]) == 3), "sources": sources})
        json_entries.append({
            "name": info["name"], "packageName": package,
            "resources": {"apkUrl": apkurl, "iconUrl": iconurl},
            "extensionLib": info["extensionLib"], "versionCode": str(info["versionCode"]),
            "versionName": info["versionName"], "contentWarning": int(info["contentWarning"]),
            "sources": [{"id": s["id"], "name": s["name"], "language": s["lang"],
                         "homeUrl": s["baseUrl"]} for s in sources],
        })
    site = "Mihon Privado"
    payload = (
        bytesfield(1, site) + bytesfield(2, "PRV") + bytesfield(3, fingerprint)
        + bytesfield(4, bytesfield(1, url))
        + bytesfield(101, b"".join(extension_messages))
    )
    (output / "index.pb").write_bytes(gzip.compress(payload, mtime=0))
    index_data = {"name": site, "badgeLabel": "PRV", "signingKey": fingerprint,
                  "contact": {"website": url}, "extensionList": {"extensions": json_entries}}
    (output / "index.json").write_text(
        json.dumps(index_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "index.min.json").write_text(
        json.dumps(legacy, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    (output / "repo.json").write_text(
        json.dumps({"index_v2": url + "/index.pb",
                    "meta": {"name": site, "website": url,
                             "signingKeyFingerprint": fingerprint}}, indent=2) + "\n",
        encoding="utf-8")
    links = "\n".join(
        '<li><a href="' + html.escape(e["info"]["packageName"] + ".apk") + '">' +
        html.escape(e["info"]["name"]) + "</a></li>" for e in entries
    )
    (output / "index.html").write_text(
        '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Mihon Privado</title>'
        '<h1>Mihon Privado</h1><p>Catálogo de extensões pessoais</p>'
        '<p>URL Mihon: <code>' + html.escape(url + "/index.pb") + '</code></p>'
        '<ul>' + links + '</ul></html>\n', encoding="utf-8")
    print("Índice gerado: " + url + "/index.pb")
    print("Assinatura SHA-256: " + fingerprint)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-root", type=Path, help="upstream/src após o assembleDebug e generateSourceInfo")
    parser.add_argument("--store", type=Path, required=True, help="Diretório do catálogo")
    parser.add_argument("--base-url", required=True, help="URL HTTPS acessível no Tailscale, sem barra final")
    opts = parser.parse_args()
    opts.store.mkdir(parents=True, exist_ok=True)
    entries = scan_builds(opts.build_root, opts.store) if opts.build_root else json.loads(
        (opts.store / "catalog-metadata.json").read_text(encoding="utf-8")
    )
    render(entries, opts.store, opts.base_url)

if __name__ == "__main__":
    main()
