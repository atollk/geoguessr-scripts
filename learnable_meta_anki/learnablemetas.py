import dataclasses
import json
import os
import tempfile

from learnable_meta_anki import anki, scrape
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

BASE_URL = "https://geometa-web.pages.dev/"


@dataclasses.dataclass
class Config:
    custom_image: dict[str, str]
    select_image: dict[str, int]


def main():
    config = Config(**json.load(open(os.path.join(os.path.dirname(__file__), "config.json"))))

    logger.info("Loading map list")
    map_list = scrape.load_map_list(os.path.join(BASE_URL, "maps"))

    # uncomment for debugging
    # map_list = [next(m for m in map_list if "ALM -  Unique & Shared European & Slavic Letters" in m.name)]

    with tempfile.TemporaryDirectory() as tempdir:
        logger.info("Creating Anki package")
        package = anki.create_anki_package(
            workdir=tempdir,
            map_list=map_list,
            config=config,
        )
        logger.info("Writing package file")
        package.write_to_file("learnable_meta.apkg")


if __name__ == "__main__":
    main()
