import dataclasses
import json
import os
import sys
import tempfile
import argparse
import fnmatch

from learnable_meta_anki import anki, scrape
import logging

from learnable_meta_anki.shared import Config, BASE_URL


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

@dataclasses.dataclass
class CliArgs:
    config: str
    include_maps: str

def _parse_cli_args(args: list[str]) -> CliArgs:
    parser = argparse.ArgumentParser(description="Generate an Anki package from a list of learnable metas.")
    parser.add_argument("--config", type=str, default=os.path.join(os.path.dirname(__file__), "config.json"), help="Path to the config file")
    parser.add_argument("--include_maps", type=str, default="*", help="Filter by map name (supports wildcards)")
    parsed = parser.parse_args(args)
    return CliArgs(parsed.config, parsed.include_maps)


def main(raw_args: list[str]) -> None:
    args = _parse_cli_args(raw_args)

    config = Config(**json.load(open(args.config, "r")))

    logger.info("Loading map list")
    map_list = scrape.load_map_list(os.path.join(BASE_URL, "maps"))
    map_list = [
        map_item for map_item in map_list
        if fnmatch.fnmatch(map_item.name, args.include_maps)
    ]

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
