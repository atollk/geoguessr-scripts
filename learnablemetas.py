import itertools
import json
from collections.abc import Iterator

import genanki
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Tuple

from tqdm import tqdm


def scrape_table_data(url: str, wait_time: int = 10) -> Iterator[tuple[str, str]]:
    """
    Scrape data from a web page by clicking on each td element in a table.

    Args:
        url (str): The URL of the webpage to scrape.
        wait_time (int): Maximum time to wait for elements to load, in seconds.

    Returns:
        List of tuples containing (td_text, div_content) for each td element.
    """
    results = []

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
        print("Crawling...")
        for td in tqdm(td_elements):
            # Store the td text
            td_text = td.text

            # Click the td element
            td.click()

            # Find the div with main contents
            xpath_condition = f"[node()[contains(., '{page_title}')] and node()[contains(., '{td_text}')]]"
            xpath = f"//*{xpath_condition}[not(./descendant::*{xpath_condition})]/div[not(./descendant::h1)]"
            target_div = driver.find_element(By.XPATH, xpath)

            if target_div is None:
                print(f"Error: Could not find a div containing the text '{page_title}'")
                continue

            # Store the data in our results list
            yield td_text, target_div.get_attribute("outerHTML")

    finally:
        # Clean up
        driver.quit()


def remove_class_attributes(html_string: str) -> str:
    soup = BeautifulSoup(html_string, "html.parser")

    # Find all elements with class attribute
    for element in soup.find_all(attrs={"class": True}):
        del element["class"]

    return str(soup)


def download_images(html_string: str, temp_folder: str = "./temp_images") -> list[str]:
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
    crawl_results: dict[str, str], question_image_replacements: dict[str, str]
):
    print("Creating Anki deck")
    model = genanki.Model(
        1425153742,
        "Meta",
        fields=[
            {"name": "Image"},
            {"name": "Answer"},
        ],
        templates=[
            {
                "name": "Card 1",
                "qfmt": "<div style=\"display: flex; justify-content: center;\">{{Image}}</div>",
                "afmt": "<div style=\"display: flex; justify-content: center;\">{{Answer}}</div>",
            },
        ],
    )
    deck = genanki.Deck(1798161526, "A Learnable Meta World - Basics")
    package = genanki.Package(deck)
    package.media_files = [
        os.path.join("learnablemeta_images", v)
        for v in question_image_replacements.values()
    ]
    for note_title, html_string in tqdm(crawl_results.items()):
        # TODO: render images in answer offline
        content_images = download_images(html_string)
        package.media_files += content_images
        if note_title in question_image_replacements:
            question_images = [question_image_replacements[note_title]]
        else:
            question_images = content_images
        for image in question_images:
            note = genanki.Note(
                model=model,
                fields=[
                    f"<img src={os.path.basename(image)}>",
                    remove_class_attributes(html_string),
                ],
            )
            deck.add_note(note)
    package.write_to_file("output.apkg")


def main():
    replacements: dict[str, dict[str, str]] = json.load(
        open("learnablemeta_images/overrides.json")
    )
    url = "https://geometa-web.pages.dev/maps/66fda352ee1c8ee4735e1aa8"
    crawl_results = list(scrape_table_data(url))
    create_anki_deck(
        dict(crawl_results), replacements["A Learnable Meta World - Basics"]
    )


# Example usage
if __name__ == "__main__":
    main()
