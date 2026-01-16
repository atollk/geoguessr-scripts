import argparse
import dataclasses
import json
import os
import sys
import tempfile
import argparse
import fnmatch

from . import anki, scrape
import logging

from .shared import Config, BASE_URL


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "learnable_meta_anki",
        help="Generate an Anki package from learnable metas.",
    )
    parser.add_argument(
        "--config_path",
        type=str,
        default="learnable_meta_anki/config.json",
        help="Path to the config file",
    )
    parser.add_argument(
        "--include_maps",
        type=str,
        default="*",
        help="Filter by map name (supports wildcards)",
    )

    def entry(args: argparse.Namespace):
        main(config_path=args.config_path, include_maps=args.include_maps)

    parser.set_defaults(func=entry)


class CustomFormatter(logging.Formatter):
    def format(self, record):
        if record.levelno >= logging.WARNING:
            return f"{record.levelname}: {record.getMessage()}"
        return record.getMessage()


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(CustomFormatter())
logging.basicConfig(
    handlers=[handler],
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def main(config_path: str, include_maps: str) -> None:
    config = Config(**json.load(open(config_path, "r")))

    logger.info("Loading map list")
    map_list = scrape.load_map_list(os.path.join(BASE_URL, "maps"))
    map_list = [map_item for map_item in map_list if fnmatch.fnmatch(map_item.name, include_maps)]

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
    # TODO: add option to include online links rather than packed media files
    # TODO: add option to create a separate APK for each deck
    main(sys.argv[1:])
