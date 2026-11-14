# ABOUTME: TER-3: downloads the LOLA DEMs of decision D28 from PDS Geosciences into data/raw/lola/
# ABOUTME: Owner: Federico. Idempotent: files already present with the expected size are skipped

"""Download the LOLA digital elevation models used by the terrain module (requirement TER-3).

Run once on every machine (about 1.1 GB in total)::

    uv run python scripts/terrain_download_dem.py            # all products
    uv run python scripts/terrain_download_dem.py ldem_64    # one product

Products (decision D28; NASA LRO LOLA Gridded Data Records, PDS Geosciences Node,
data set LRO-L-LOLA-4-GDR-V1.0):

- ``ldem_64``: global, simple cylindrical, 64 px/deg (~474 m/px at the equator), 531 MB.
- ``ldem_80s_80m``: south pole to 80 deg S, polar stereographic, 80 m/px, 116 MB.
- ``ldem_85s_20m``: south pole to 85 deg S, polar stereographic, 20 m/px, 460 MB (TER-4).

Each product is an ``.img`` grid of little-endian int16 heights (0.5 m per unit above the
1737.4 km sphere) plus its ``.lbl`` PDS label, which documents size, scaling and projection.
Downloads go to a ``.part`` file first and are renamed only when complete and of the right size,
so an interrupted run never leaves a truncated DEM behind.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger("terrain_download_dem")

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "lola"
PDS_GDR_URL = "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr"
CHUNK_BYTES = 1 << 20


@dataclass(frozen=True)
class DemProduct:
    """One LOLA DEM product on PDS.

    Attributes:
        name: Product id, also the file stem (e.g. ``ldem_64``).
        folder: Sub-folder on PDS (``cylindrical/img`` or ``polar/img``).
        img_bytes: Expected size of the ``.img`` file, bytes (from the PDS directory listing).
        description: Coverage, projection and resolution, for humans.
    """

    name: str
    folder: str
    img_bytes: int
    description: str

    def url(self, suffix: str) -> str:
        """Return the PDS URL of the file with ``suffix`` (``.img`` or ``.lbl``)."""
        return f"{PDS_GDR_URL}/{self.folder}/{self.name}{suffix}"


PRODUCTS = {
    p.name: p
    for p in (
        DemProduct(
            "ldem_64",
            "cylindrical/img",
            530_841_600,  # 23040 x 11520 int16 samples
            "global, simple cylindrical, 64 px/deg (~474 m/px)",
        ),
        DemProduct(
            "ldem_80s_80m",
            "polar/img",
            115_520_000,  # 7600 x 7600 int16 samples
            "south pole to 80 S, polar stereographic, 80 m/px",
        ),
        DemProduct(
            "ldem_85s_20m",
            "polar/img",
            460_136_448,  # 15168 x 15168 int16 samples
            "south pole to 85 S, polar stereographic, 20 m/px (near-site detail, TER-4)",
        ),
    )
}


def download(url: str, target: Path, expected_bytes: int | None = None) -> None:
    """Download ``url`` to ``target`` through a ``.part`` file.

    Args:
        url: Source URL.
        target: Final file path.
        expected_bytes: Required size of the downloaded file, bytes; None skips the check.

    Raises:
        OSError: On network or disk errors, or when the size does not match.
    """
    part = target.with_name(target.name + ".part")
    LOGGER.info("downloading %s", url)
    with urllib.request.urlopen(url, timeout=60) as response, part.open("wb") as out:
        total = int(response.headers.get("Content-Length", 0)) or expected_bytes or 0
        done = 0
        next_report = 0.0
        while chunk := response.read(CHUNK_BYTES):
            out.write(chunk)
            done += len(chunk)
            if total > CHUNK_BYTES and done / total >= next_report:  # no progress for labels
                LOGGER.info(
                    "  %s: %3.0f%% of %.0f MB", target.name, 100 * done / total, total / 1e6
                )
                next_report += 0.1
    size = part.stat().st_size
    if expected_bytes is not None and size != expected_bytes:
        part.unlink()
        raise OSError(f"{url}: got {size} bytes, expected {expected_bytes}")
    shutil.move(part, target)


def fetch_product(product: DemProduct, raw_dir: Path = RAW_DIR) -> None:
    """Download one product's label and image unless they are already complete.

    Args:
        product: The DEM product.
        raw_dir: Destination folder.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    label = raw_dir / f"{product.name}.lbl"
    image = raw_dir / f"{product.name}.img"
    if not label.exists():
        download(product.url(".lbl"), label)
    if image.exists() and image.stat().st_size == product.img_bytes:
        LOGGER.info("%s already present (%s), skipped", image.name, product.description)
        return
    download(product.url(".img"), image, product.img_bytes)
    LOGGER.info("%s ready (%s)", image.name, product.description)


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and download the requested products; return the exit code."""
    parser = argparse.ArgumentParser(description="Download the LOLA DEMs into data/raw/lola/.")
    parser.add_argument(
        "products", nargs="*", help=f"products to fetch, any of {list(PRODUCTS)} (default: all)"
    )
    args = parser.parse_args(argv)
    unknown = set(args.products) - set(PRODUCTS)
    if unknown:
        parser.error(f"unknown products {sorted(unknown)}; choose from {list(PRODUCTS)}")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for name in args.products or PRODUCTS:
        try:
            fetch_product(PRODUCTS[name])
        except OSError as exc:
            LOGGER.error("failed to download %s: %s", name, exc)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
