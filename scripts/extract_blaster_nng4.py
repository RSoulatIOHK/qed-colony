#!/usr/bin/env python3
"""Freeze and validate a deterministic, proof-free prefix of upstream NNG4.

This parser intentionally supports only the small command language in the
selected upstream prefix. It never imports the vendored placeholder proofs.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re


CORPUS_ID = "blaster-nng4-prefix-v1"
CASE_COUNT = 12
COMMIT = "b7cc5304bde87c269bb3ba57e560304ffd9f2189"
REPOSITORY = "https://github.com/input-output-hk/Blaster-benchmarking"
SOURCE_PATH = "BlasterBenchmarks/NNG4/NNG4.lean"
VENDOR = "benchmarks/upstream/blaster-b7cc5304"
MANIFEST_PATH = "benchmarks/blaster-nng4-v1.json"
LOCK_PATH = "benchmarks/blaster-nng4-v1.lock.json"
SOURCE_SHA256 = "93d6755ade248473aff71ae5832f30aaf2ff205a5e2619955c8f9585631328cf"
SOURCE_GIT_BLOB = "39330d6867b8e307015588aa1fc5ded7feae8b78"
LICENSE_SHA256 = "50e6751797c50dedd75ef1b8a0d9e42f5f8472e9fbce91f34718e9f97b0c780a"
LICENSE_GIT_BLOB = "b09cd7856d58590578ee1a4f3ad45d1310a97f87"
UPSTREAM_TOOLCHAIN = "leanprover/lean4:v4.24.0"
LOCAL_TOOLCHAIN = "leanprover/lean4:v4.35.0"


class CorpusError(ValueError):
    """An input differs from the reviewed frozen corpus or supported syntax."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def _statement_hash(context, header):
    return sha256(json.dumps({"context": context, "header": header}, ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8"))


def extract_cases(source, count=CASE_COUNT):
    """Retain exact headers and active commands; discard every upstream proof."""
    if type(count) is not int or count <= 0:
        raise CorpusError("Selection count must be a positive integer")
    lines = source.splitlines()
    scopes, cases = [], []
    index = 0
    while index < len(lines):
        raw = lines[index]
        line = raw.strip()
        index += 1
        if not line or line.startswith("--"):
            continue
        block = re.fullmatch(r"(namespace|section) ([\w.]+)", line)
        if block:
            scopes.append({"kind": block[1], "name": block[2], "commands": [raw]})
            continue
        ending = re.fullmatch(r"end(?: ([\w.]+))?", line)
        if ending:
            if not scopes or (ending[1] and ending[1] != scopes[-1]["name"]):
                raise CorpusError("Unmatched source scope at line %d" % index)
            scopes.pop()
            continue
        if line == "abbrev ℕ := Nat" or line == "open Nat":
            if not scopes:
                raise CorpusError("Context command outside the supported namespace")
            scopes[-1]["commands"].append(raw)
            continue
        declaration = re.match(r"theorem ([A-Za-z_][A-Za-z_0-9.]*)\b", line)
        if not declaration:
            raise CorpusError("Unsupported source command at line %d" % index)
        start = index
        header_lines = [raw]
        while ":=" not in header_lines[-1]:
            if index >= len(lines):
                raise CorpusError("Unterminated declaration at line %d" % start)
            header_lines.append(lines[index])
            index += 1
        header_text = "\n".join(header_lines)
        header, proof = header_text.split(":=", 1)
        if proof.strip() != "by sorry":
            raise CorpusError("Unexpected upstream proof at line %d" % start)
        header += ":="
        context = [command for scope in scopes for command in scope["commands"]]
        namespaces = [scope["name"] for scope in scopes if scope["kind"] == "namespace"]
        name = declaration[1]
        full_name = ".".join(namespaces + [name])
        cases.append({"id": "nng4." + name, "source_name": name, "full_name": full_name,
                      "source_line": start, "kind": "positive", "context": context,
                      "header": header, "context_closers": ["end " + scope["name"] for scope in reversed(scopes)],
                      "statement_sha256": _statement_hash(context, header)})
        if len(cases) == count:
            return cases
    raise CorpusError("Upstream source has fewer than the requested named theorems")


def _controls():
    context = ["namespace ColonyNNG4Controls"]
    records = []
    for name, kind, statement in (("witness", "nonvacuity", "(0 : Nat) + 1 ≠ 0"),
                                  ("impossible", "negative", "∀ n : Nat, n + 1 = n")):
        header = "theorem %s : %s :=" % (name, statement)
        records.append({"id": "control." + name, "source_name": name,
                        "full_name": "ColonyNNG4Controls." + name, "source_line": None,
                        "kind": kind, "context": context, "header": header,
                        "context_closers": ["end ColonyNNG4Controls"],
                        "statement_sha256": _statement_hash(context, header)})
    return records


def _safe_file(root, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise CorpusError("Corpus paths must remain repository relative")
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise CorpusError("Corpus inputs must not be symlinks")
    if not current.is_file():
        raise CorpusError("A required frozen corpus input is missing: " + relative)
    return current


def build_manifest(root):
    root = Path(root).resolve()
    source = _safe_file(root, VENDOR + "/NNG4.lean").read_bytes()
    license_text = _safe_file(root, VENDOR + "/LICENSE").read_bytes()
    upstream_pin = _safe_file(root, VENDOR + "/lean-toolchain").read_text(encoding="utf-8")
    if sha256(source) != SOURCE_SHA256 or git_blob(source) != SOURCE_GIT_BLOB:
        raise CorpusError("Vendored NNG4 bytes do not match the immutable upstream source")
    if sha256(license_text) != LICENSE_SHA256 or git_blob(license_text) != LICENSE_GIT_BLOB:
        raise CorpusError("Vendored license bytes do not match the immutable upstream source")
    if upstream_pin != UPSTREAM_TOOLCHAIN + "\n":
        raise CorpusError("Upstream toolchain pin changed")
    return {
        "schema": "colony.external_corpus.v1", "id": CORPUS_ID,
        "scope": "First 12 named NNG4 theorems in source order; exploratory rehost, not the full upstream benchmark.",
        "source": {"repository": REPOSITORY, "commit": COMMIT, "path": SOURCE_PATH,
                   "url": REPOSITORY + "/blob/" + COMMIT + "/" + SOURCE_PATH,
                   "vendored_path": VENDOR + "/NNG4.lean", "sha256": SOURCE_SHA256,
                   "git_blob": SOURCE_GIT_BLOB, "upstream_toolchain": UPSTREAM_TOOLCHAIN,
                   "named_theorem_count": len(re.findall(r"^\s*theorem\s+", source.decode("utf-8"), re.MULTILINE)),
                   "unnamed_example_count": len(re.findall(r"^\s*example\s+", source.decode("utf-8"), re.MULTILINE)),
                   "license": "Apache-2.0", "license_path": VENDOR + "/LICENSE",
                   "license_sha256": LICENSE_SHA256, "license_git_blob": LICENSE_GIT_BLOB},
        "selection": {"kind": "first_named_theorems", "count": CASE_COUNT,
                      "remaining_named_theorems": 108 - CASE_COUNT, "excluded_unnamed_examples": 9,
                      "policy": "Source order only; no theorem-name, proof-success or difficulty selection."},
        "imports": ["Colony.Tactic"], "local_toolchain": LOCAL_TOOLCHAIN,
        "resource_limits": {"timeout_seconds": 20, "max_heartbeats": 200000},
        "allowed_axioms": ["propext", "Quot.sound", "Classical.choice"],
        "proof_contract": {"candidate_body": "by colony", "isolated_declaration": True,
                           "extra_imports": False, "extra_helpers": False, "manual_proof_steps": False},
        "comparability": "Upstream uses Lean 4.24.0; this rehost uses 4.35.0. No official Blaster comparison or superiority claim.",
        "cases": extract_cases(source.decode("utf-8")), "controls": _controls(),
    }


def protected_paths():
    return [VENDOR + "/NNG4.lean", VENDOR + "/LICENSE", VENDOR + "/lean-toolchain",
            "scripts/extract_blaster_nng4.py"]


def freeze(root):
    root = Path(root).resolve()
    manifest = build_manifest(root)
    encoded = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (root / MANIFEST_PATH).write_bytes(encoded)
    lock = {"schema": "colony.external_corpus_lock.v1", "corpus_id": CORPUS_ID,
            "manifest": {"path": MANIFEST_PATH, "sha256": sha256(encoded)},
            "protected_files": {path: sha256(_safe_file(root, path).read_bytes()) for path in protected_paths()}}
    (root / LOCK_PATH).write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def load_corpus(manifest_path, lock_path=None, root=None):
    manifest_path = Path(manifest_path).resolve()
    root = Path(root).resolve() if root is not None else manifest_path.parent.parent
    lock_path = Path(lock_path) if lock_path is not None else manifest_path.with_name(manifest_path.stem + ".lock.json")
    if manifest_path != _safe_file(root, MANIFEST_PATH).resolve():
        raise CorpusError("Unexpected corpus manifest path")
    if lock_path.resolve() != _safe_file(root, LOCK_PATH).resolve():
        raise CorpusError("Unexpected corpus lock path")
    encoded = manifest_path.read_bytes()
    manifest, lock = json.loads(encoded), json.loads(lock_path.read_text(encoding="utf-8"))
    if (lock.get("schema") != "colony.external_corpus_lock.v1" or lock.get("corpus_id") != CORPUS_ID
            or lock.get("manifest") != {"path": MANIFEST_PATH, "sha256": sha256(encoded)}):
        raise CorpusError("Manifest differs from the frozen corpus lock")
    expected_files = {path: sha256(_safe_file(root, path).read_bytes()) for path in protected_paths()}
    if lock.get("protected_files") != expected_files:
        raise CorpusError("Protected corpus input differs from its frozen hash")
    if manifest != build_manifest(root):
        raise CorpusError("Manifest selection, statements, context or checking policy changed")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Regenerate reviewed manifest and lock from the pinned source")
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    manifest = freeze(root) if arguments.write else load_corpus(root / MANIFEST_PATH)
    print("Validated %s: %d frozen statements and %d controls" %
          (manifest["id"], len(manifest["cases"]), len(manifest["controls"])))


if __name__ == "__main__":
    main()
