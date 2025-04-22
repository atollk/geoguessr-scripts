import dataclasses
import json
import os
import tempfile

from learnable_meta_anki import anki, scrape

BASE_URL = "https://geometa-web.pages.dev/"


@dataclasses.dataclass
class Config:
    custom_image: dict[str, str]
    select_image: dict[str, int]


def main():
    config = Config(**json.load(open(os.path.join(os.path.dirname(__file__), "config.json"))))

    print("Loading map list")
    map_list = scrape.load_map_list(os.path.join(BASE_URL, "maps"))

    with tempfile.TemporaryDirectory() as tempdir:
        print("Creating Anki package")
        package = anki.create_anki_package(
            workdir=tempdir,
            map_list=map_list[19:20],  # TODO
            config=config,
        )
        package.write_to_file("learnable_meta.apkg")


# Example usage
if __name__ == "__main__":
    main()
