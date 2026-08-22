#!/usr/bin/env python3
"""Prepare the SQLite assets consumed by the Android application.

The repository keeps the source databases in Git LFS, which is not available
to the Android release checkout.  The compressed prebuilt database is small
enough to keep in the repository, so the release build derives the two mobile
databases from it and validates their schemas before Flutter bundles them.
"""

from __future__ import annotations

import csv
import gzip
import shutil
import sqlite3
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PREBUILT = ROOT / "assets/database/prebuilt_tags.db.gz"
TAGS_CSV = ROOT / "assets/translations/hf_danbooru_tags.csv"
ZH_CSV = ROOT / "assets/translations/danbooru_zh.csv"
DATABASE_DIR = ROOT / "assets/databases"
TRANSLATION_DB = DATABASE_DIR / "translation.db"
COOCCURRENCE_DB = DATABASE_DIR / "cooccurrence.db"


def _load_translation_map(path: Path) -> dict[str, str]:
    translations: dict[str, str] = {}
    if not path.exists():
        return translations

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.reader(handle):
            if len(row) < 2:
                continue
            tag = row[0].strip().lower()
            translation = row[1].strip()
            if tag and translation and translation.lower() != "none":
                translations.setdefault(tag, translation)
    return translations


def _extract_prebuilt(destination: Path) -> None:
    with gzip.open(PREBUILT, "rb") as source, destination.open("wb") as target:
        shutil.copyfileobj(source, target)


def _prepare_translation_db(source: sqlite3.Connection) -> None:
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    if TRANSLATION_DB.exists():
        TRANSLATION_DB.unlink()

    zh_translations = _load_translation_map(ZH_CSV)
    source_translations = {
        tag.lower(): translation
        for tag, translation in source.execute(
            "SELECT tag, zh_translation FROM translations"
        )
        if translation and translation not in {"0", "None"}
    }

    destination = sqlite3.connect(TRANSLATION_DB)
    try:
        destination.executescript(
            """
            PRAGMA journal_mode = OFF;
            PRAGMA synchronous = OFF;
            CREATE TABLE tags (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                type INTEGER NOT NULL DEFAULT 0,
                count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE translations (
                id INTEGER PRIMARY KEY,
                tag_id INTEGER NOT NULL,
                language TEXT NOT NULL,
                translation TEXT NOT NULL,
                UNIQUE (tag_id, language),
                FOREIGN KEY (tag_id) REFERENCES tags(id)
            );
            CREATE INDEX idx_tags_name ON tags(name);
            CREATE INDEX idx_tags_type ON tags(type);
            CREATE INDEX idx_translations_lang ON translations(language);
            """
        )

        with TAGS_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            tag_rows = []
            translation_rows = []
            translation_id = 1
            for tag_id, row in enumerate(reader, start=1):
                name = (row.get("tag") or "").strip().lower()
                if not name:
                    continue
                tag_rows.append(
                    (
                        tag_id,
                        name,
                        int(row.get("category") or 0),
                        int(row.get("count") or 0),
                    )
                )
                translation = zh_translations.get(name) or source_translations.get(name)
                if translation:
                    translation_rows.append((translation_id, tag_id, "zh", translation))
                    translation_id += 1

        destination.executemany(
            "INSERT INTO tags(id, name, type, count) VALUES (?, ?, ?, ?)",
            tag_rows,
        )
        destination.executemany(
            "INSERT INTO translations(id, tag_id, language, translation) VALUES (?, ?, ?, ?)",
            translation_rows,
        )
        destination.commit()
    finally:
        destination.close()


def _prepare_cooccurrence_db(source: sqlite3.Connection) -> None:
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    if COOCCURRENCE_DB.exists():
        COOCCURRENCE_DB.unlink()

    destination = sqlite3.connect(COOCCURRENCE_DB)
    try:
        destination.executescript(
            """
            PRAGMA journal_mode = OFF;
            PRAGMA synchronous = OFF;
            CREATE TABLE cooccurrences (
                tag1 TEXT NOT NULL,
                tag2 TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                cooccurrence_score REAL NOT NULL DEFAULT 0.0,
                PRIMARY KEY (tag1, tag2)
            );
            CREATE INDEX idx_cooccurrences_tag1_count
                ON cooccurrences(tag1, count DESC, tag2);
            """
        )
        rows = source.execute(
            "SELECT tag1, tag2, count, cooccurrence_score FROM cooccurrences"
        )
        while True:
            batch = rows.fetchmany(5000)
            if not batch:
                break
            destination.executemany(
                "INSERT INTO cooccurrences(tag1, tag2, count, cooccurrence_score) "
                "VALUES (?, ?, ?, ?)",
                batch,
            )
        destination.commit()
    finally:
        destination.close()


def _validate_database(path: Path, required_tables: set[str]) -> None:
    with path.open("rb") as handle:
        header = handle.read(16)
    if header != b"SQLite format 3\x00":
        raise RuntimeError(f"{path} is not a SQLite database")

    connection = sqlite3.connect(path)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"{path} integrity check failed: {integrity}")
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        missing = required_tables - tables
        if missing:
            raise RuntimeError(f"{path} is missing tables: {sorted(missing)}")
        count = connection.execute(
            f"SELECT COUNT(*) FROM {sorted(required_tables)[0]}"
        ).fetchone()[0]
        if count <= 0:
            raise RuntimeError(f"{path} contains no records")
    finally:
        connection.close()


def main() -> None:
    for required in (PREBUILT, TAGS_CSV):
        if not required.exists():
            raise FileNotFoundError(required)

    with tempfile.TemporaryDirectory(prefix="nai-mobile-db-") as directory:
        source_path = Path(directory) / "prebuilt_tags.db"
        _extract_prebuilt(source_path)
        source = sqlite3.connect(source_path)
        try:
            _prepare_translation_db(source)
            _prepare_cooccurrence_db(source)
        finally:
            source.close()

    _validate_database(TRANSLATION_DB, {"tags", "translations"})
    _validate_database(COOCCURRENCE_DB, {"cooccurrences"})
    translation_size = TRANSLATION_DB.stat().st_size
    cooccurrence_size = COOCCURRENCE_DB.stat().st_size
    print(
        "Prepared mobile databases: "
        f"translation.db={translation_size} bytes, "
        f"cooccurrence.db={cooccurrence_size} bytes"
    )


if __name__ == "__main__":
    main()
