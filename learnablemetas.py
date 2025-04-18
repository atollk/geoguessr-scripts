import dataclasses
import json
import tempfile
from collections.abc import Iterator

import genanki
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import requests
from bs4 import BeautifulSoup

from tqdm import tqdm

from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import re
import logging


@dataclasses.dataclass
class MetaMap:
    name: str
    author: str
    description: str
    map_id: str
    difficulty: str


def load_map_list(base_url: str) -> list[MetaMap]:
    options = webdriver.FirefoxOptions()
    options.add_argument("--headless")
    driver = webdriver.Firefox(options=options)

    def extract_map_id(href: str) -> str | None:
        if not href:
            return None

        # Extract the map ID from URLs like "https://www.geoguessr.com/maps/66fda352ee1c8ee4735e1aa8"
        match = re.search(r"maps/([a-zA-Z0-9]+)", href)
        if match:
            return match.group(1)
        return None

    try:
        driver.get(base_url)

        # Find all map containers
        map_containers = driver.find_elements(
            By.CSS_SELECTOR,
            "div.bg-card.text-card-foreground.rounded-xl.border.shadow.flex.flex-col",
        )

        maps_data = []
        for container in tqdm(map_containers):
            # Extract name
            name_element = container.find_element(
                By.CSS_SELECTOR, "h3.font-semibold.leading-none.tracking-tight"
            )
            name = name_element.text

            # Extract author
            author_element = container.find_element(
                By.CSS_SELECTOR, "p.text-muted-foreground.text-sm strong"
            )
            author = author_element.text

            # Extract description
            description_element = container.find_element(
                By.CSS_SELECTOR, "p.mt-6.text-base.text-gray-600.dark\\:text-gray-300"
            )
            description = description_element.text

            # Extract difficulty
            # difficulty_element = container.find_element(By.XPATH,
            #                                            ".//svg[contains(@class, 'iconify--carbon')]/parent::div")
            # difficulty = difficulty_element.text.strip()
            difficulty = "?"

            # Extract map_id from play link
            play_link = container.find_element(By.CSS_SELECTOR, "a[href*='maps/']")
            href = play_link.get_attribute("href")
            map_id = extract_map_id(href)

            maps_data.append(
                {
                    "name": name,
                    "author": author,
                    "description": description,
                    "map_id": map_id,
                    "difficulty": difficulty,
                }
            )
        return [MetaMap(**x) for x in maps_data]

    finally:
        driver.quit()


def scrape_table_data(url: str, wait_time: int = 10) -> dict[str, str]:
    """
    Scrape data from a web page by clicking on each td element in a table.

    Args:
        url (str): The URL of the webpage to scrape.
        wait_time (int): Maximum time to wait for elements to load, in seconds.

    Returns:
        List of tuples containing (td_text, div_content) for each td element.
    """
    result = {}

    # Set up the webdriver
    options = webdriver.FirefoxOptions()
    options.add_argument("--headless")  # Run in headless mode (optional)
    driver = webdriver.Firefox(options=options)
    driver.implicitly_wait(time_to_wait=1)

    try:
        # Navigate to the URL
        driver.get(url)

        # Wait for the table to load
        WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )

        # Find all td elements
        td_elements = driver.find_elements(By.TAG_NAME, "td")

        page_title = driver.title

        # Click on each td element and process the results
        for td in tqdm(td_elements):
            # Store the td text
            td_text = td.text

            # Click the td element
            td.click()

            # Find the div with main contents
            xpath_condition = f"[node()[contains(., '{page_title}')] and node()[contains(., '{td_text.replace("'", "\\'")}')]]"
            xpath = f"//*{xpath_condition}[not(./descendant::*{xpath_condition})]/div[not(./descendant::h1)]"
            target_div = driver.find_element(By.XPATH, xpath)

            if target_div is None:
                print(f"Error: Could not find a div containing the text '{page_title}'")
                continue

            # Store the data in our results list
            result[td_text] = target_div.get_attribute("outerHTML")

        return result
    finally:
        # Clean up
        driver.quit()


def remove_class_attributes(html_string: str) -> str:
    soup = BeautifulSoup(html_string, "html.parser")

    # Find all elements with class attribute
    for element in soup.find_all(attrs={"class": True}):
        del element["class"]

    return str(soup)


def download_images(html_string: str, temp_folder: str) -> list[str]:
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

        # img_url = urljoin(base_url, src)
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
                print(
                    f"Failed to download {img_url}: Status code {response.status_code}"
                )
        except Exception as e:
            print(f"Error downloading {img_url}: {e}")

    return download_results


def create_anki_deck(
    *,
    meta_map: MetaMap,
    package: genanki.Package,
    model: genanki.Model,
    crawl_results: dict[str, str],
    question_image_replacements: dict[str, str],
    download_directory: str,
) -> None:
    deck = genanki.Deck(
        hash(meta_map.name), meta_map.name, description=meta_map.description
    )
    for note_title, html_string in tqdm(crawl_results.items()):
        # TODO: render images in answer offline
        content_images = download_images(html_string, download_directory)
        package.media_files += content_images
        if note_title in question_image_replacements:
            question_images = [question_image_replacements[note_title]]
        else:
            question_images = content_images
        for image in question_images:
            note = genanki.Note(
                model=model,
                fields=[
                    note_title,
                    f"<img src={os.path.basename(image)}>",
                    remove_class_attributes(html_string),
                ],
            )
            deck.add_note(note)
    package.decks.append(deck)


def main():
    print("Loading map list")
    map_list = load_map_list("https://geometa-web.pages.dev/maps")

    replacements: dict[str, str] = json.load(
        open("learnablemeta_images/overrides.json")
    )["image_overrides"]

    model = genanki.Model(
        1425153742,
        "Meta",
        fields=[
            {"name": "Rule Name"},
            {"name": "Image"},
            {"name": "Answer"},
        ],
        templates=[
            {
                "name": "Card 1",
                "qfmt": '<div style="display: flex; justify-content: center;">{{Image}}</div>',
                "afmt": '<div style="display: flex; justify-content: center;">{{Answer}}</div>',
            },
        ],
    )
    package = genanki.Package([])
    package.media_files = list(
        {
            os.path.join("learnablemeta_images", v)
            for v in replacements.values()
        }
    )

    # temporary
    map_list = map_list[:4]

    with tempfile.TemporaryDirectory() as tempdir:
        for i, meta_map in enumerate(map_list):
            url = f"https://geometa-web.pages.dev/maps/{meta_map.map_id}"
            print(f"Crawling {meta_map.name}...")
            crawl_results = scrape_table_data(url)
            print(f"Creating deck {meta_map.name} ({i+1} / {len(map_list)}) ...")
            create_anki_deck(
                meta_map=meta_map,
                package=package,
                model=model,
                crawl_results=crawl_results,
                question_image_replacements=replacements,
                download_directory=tempdir,
            )
            # TODO: handle name conflicts in downloaded files

        package.write_to_file("learnable_meta.apkg")


# Example usage
if __name__ == "__main__":
    main()
