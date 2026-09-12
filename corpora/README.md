# Corpora

Seeded, committed generator scripts for the three evaluation corpora — see
spec §16.1. All data is synthetic or public (e.g. Garfinkel's digital
corpora); nothing here is real casework (§19).

| Corpus | What it contains | Purpose |
| --- | --- | --- |
| **C1** | Files of each supported type at known offsets | Easy, contiguous case — reported as such |
| **C2** | A FAT32 volume (mtools), populated then files deleted | The realistic carving scenario; also makes the Autopsy comparison valid (§16.4) |
| **C3** | Adversarial: truncated files, EXIF thumbnails, nested ZIP, seeded random headers, misaligned headers, wrong BMP sizes, stale SQLite page counts | Stresses parsers; also produces the P-09 density corpus |

Benchmark results are written to `results/` as JSON and committed (§16.7).

Scripts land at M1-7 (C1, C2) and M1-8 (C3 + mutation fuzzer).