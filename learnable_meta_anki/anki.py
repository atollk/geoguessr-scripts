import os

import genanki
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from learnable_meta_anki.learnablemetas import Config, BASE_URL
from learnable_meta_anki.scrape import MetaMap, scrape_map
import logging

logger = logging.getLogger(__name__)

CARD_MODEL = genanki.Model(
    1425153742,
    "Meta",
    fields=[
        {"name": "Rule Name"},
        {"name": "Image"},
        {"name": "Answer"},
    ],
    templates=[
        {
            "name": "Single Image Card",
            "qfmt": '<div style="display: flex; justify-content: center;">{{Image}}</div>',
            "afmt": '<div style="display: flex; justify-content: center;">{{Answer}}</div>',
        },
    ],
)


def _remove_class_attributes(html_string: str) -> str:
    """Cleans up all 'class' attributes from an HTML string."""
    soup = BeautifulSoup(html_string, "html.parser")

    for element in soup.find_all(attrs={"class": True}):
        del element["class"]

    return str(soup)


def _download_images(html_string: str, temp_folder: str) -> list[str]:
    """
    Download all images found in 'img' tags of a given HTML string and stores them in the specified directory.
    Returns a list of the new file paths on disk.
    """
    # Create temp folder if it doesn't exist
    os.makedirs(temp_folder, exist_ok=True)

    soup = BeautifulSoup(html_string, "html.parser")
    images = soup.find_all("img")

    download_results = []

    for i, img in enumerate(images):
        # Get image URL and make it absolute if it's relative
        src = img.get("src")
        if not src:
            continue

        img_url = src

        # Determine filename
        filename = f"image_{i}_{os.path.basename(img_url)}"
        if "?" in filename:
            filename = filename.split("?")[0]

        file_path = os.path.join(temp_folder, filename)

        # Download the image
        try:
            response = requests.get(img_url, stream=True)
            if response.status_code == 200:
                with open(file_path, "wb") as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                download_results.append(file_path)
            else:
                logger.error(f"Failed to download {img_url}: Status code {response.status_code}")
        except Exception as e:
            logger.error(f"Error downloading {img_url}: {e}")

    return download_results


def create_anki_cards_from_meta(
    *,
    config: Config,
    workdir: str,
    meta_html_content: str,
    meta_name: str,
) -> tuple[list[genanki.Card], list[str]]:
    # TODO: render images in answer offline
    cards = []
    content_images = _download_images(meta_html_content, workdir)
    media_files = content_images
    if meta_name in config.custom_image:
        custom_image = config.custom_image[meta_name]
        if isinstance(custom_image, str):
            custom_image = [custom_image]
        question_images = custom_image
    elif meta_name in config.select_image:
        question_images = [content_images[config.select_image[meta_name] - 1]]
    else:
        question_images = content_images
    for image in question_images:
        note = genanki.Note(
            model=CARD_MODEL,
            fields=[
                meta_name,
                f"<img src={os.path.basename(image)}>",
                _remove_class_attributes(meta_html_content),
            ],
        )
        cards.append(note)
    return cards, media_files


def create_anki_deck(
    *,
    meta_map: MetaMap,
    metas: dict[str, str],
    config: Config,
    workdir: str,
) -> tuple[genanki.Deck, list[str]]:
    """
    Creates a deck for a given meta map.
    """
    deck_description = f"{meta_map.description}\n\nCreated from {BASE_URL} using github.com/atollk/geoguessr-scripts."
    deck = genanki.Deck(hash(meta_map.name), meta_map.name, description=deck_description)
    new_media_files = []
    for meta_name, html_string in tqdm(metas.items()):
        cards, media_files = create_anki_cards_from_meta(
            config=config,
            workdir=workdir,
            meta_html_content=html_string,
            meta_name=meta_name,
        )
        for card in cards:
            deck.add_note(card)
        new_media_files += media_files
    return deck, new_media_files


def create_anki_package(
    *,
    workdir: str,
    config: Config,
    map_list: list[MetaMap],
) -> genanki.Package:
    package = genanki.Package([])
    package.media_files = list({os.path.join("images", v) for v in config.custom_image.values()})

    for i, meta_map in enumerate(map_list):
        logger.info(f"Crawling {meta_map.name}...")
        metas = scrape_map(meta_map)
        logger.info(f"Creating deck {meta_map.name} ({i + 1} / {len(map_list)}) ...")
        deck, media_files = create_anki_deck(
            meta_map=meta_map,
            metas=metas,
            config=config,
            workdir=workdir,
        )
        package.media_files += media_files
        package.decks.append(deck)
        # TODO: handle name conflicts in downloaded files

    return package
