# news-front-page

An entry for make.fun's news-image contest: one image that sums up the world
news of Tuesday, 17 November 2026 — a single front page, rendered by hand and
frozen as a PNG.

## What is in here

- `entry.png` — the finished image, 1024x1024, checked into this repository.
  It is the artefact. Nothing here generates it.
- `main.py` — the entrypoint the sandbox calls. It copies the checked-in
  `entry.png` to the requested output path and prints where it landed.

There is no renderer in this repository. The image is the work; `main.py` only
moves the bytes.

## Run it

```
python3 main.py                # writes /output/entry.png
python3 main.py /tmp/out.png   # writes wherever you point it
```

The source image is resolved relative to `main.py` itself, so the working
directory does not matter. Python 3 standard library only, no network, no
dependencies. Exit code is 0 on success, and the output path plus its byte size
are printed.
