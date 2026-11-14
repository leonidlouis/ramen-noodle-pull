# Tonkotsu ramen — make.fun food-picture-01 entry

An entry for make.fun's **food-picture-01** contest ("make the best-looking food picture").
The picture is `assets/ramen.jpg`: a 1024×1024 photo of a bowl of tonkotsu ramen with a noodle pull.

`main.py` (Python 3.13, standard library only) checks the image and then writes it, byte for byte,
to `<output>/entry.png`. The contest identifies the format from the first bytes, so JPEG content
under the name `entry.png` is allowed. Before writing, the program checks that the file:

- starts with a JPEG or PNG signature,
- is at most 1 MiB,
- is at most 1024×1024 pixels, and not 0 in either dimension (read from the JPEG SOF segment or the PNG IHDR chunk),
- is a whole image: for a JPEG, every segment and the scan data run through to the end-of-image
  marker with nothing after it; for a PNG, every chunk has a valid CRC, from IHDR through IEND.

The output is written to a temporary file and then renamed, so there is never a partial
`entry.png`. If any check fails, it exits non-zero with a message and writes nothing. The output is
deterministic: every run writes the same bytes.

## Run

```sh
python3 main.py                                   # writes /output/entry.png
MAKEFUN_OUTPUT_DIR=out python3 main.py            # writes out/entry.png (dir created if missing)
python3 main.py path/to/other.jpg                 # validate/write a different image
```

Paths are resolved relative to `main.py`, so it can be run from any directory.

## Test

```sh
python3 -m unittest discover -s tests -v
```

## License

MIT, see [LICENSE](LICENSE).
