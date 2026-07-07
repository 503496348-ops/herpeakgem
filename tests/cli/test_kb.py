from __future__ import annotations

from pathlib import Path

import pytest
import typer

from herpeakgem_cli import kb as kb_module


def test_collect_documents_with_file_and_glob(tmp_path: Path) -> None:
    doc1 = tmp_path / "a.txt"
    doc2 = tmp_path / "a.pdf"
    doc3 = tmp_path / "ignore.bin"
    doc1.write_text("hello", encoding="utf-8")
    doc2.write_text("pdf", encoding="utf-8")
    doc3.write_bytes(b"binary")

    out = kb_module._collect_documents(
        [str(doc1), str(doc2), str((tmp_path / "*.txt").as_posix())], docs_dir=None
    )

    assert out == [str(doc1), str(doc2)]

    # glob entries should resolve deterministically with no duplicate entries
    duplicate = kb_module._collect_documents([str((tmp_path / "**/*.txt").as_posix())], docs_dir=None)
    assert duplicate == [str(doc1)]


def test_collect_documents_from_directory_and_invalid_path(tmp_path: Path) -> None:
    nested = tmp_path / "docs"
    nested.mkdir()
    keep = nested / "keep.md"
    drop = nested / "drop.bin"
    keep.write_text("keep", encoding="utf-8")
    drop.write_text("drop", encoding="utf-8")

    out = kb_module._collect_documents([str(nested)], docs_dir=None)
    assert out == [str(keep)]

    with pytest.raises(typer.BadParameter):
        kb_module._collect_documents([str(drop)], docs_dir=None)

    with pytest.raises(typer.BadParameter):
        kb_module._collect_documents([str(tmp_path / "missing.txt")], docs_dir=None)

