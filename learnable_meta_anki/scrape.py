import contextlib
import dataclasses
import html
import re
from typing import Any, Generator

import selenium.webdriver.remote.webelement
import selenium.webdriver.remote.webdriver
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.wait import WebDriverWait
from tqdm import tqdm

import os.path
from shared import BASE_URL
import logging

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class MetaMap:
    name: str
    author: str
    description: str
    map_id: str
    difficulty: str


def _string_to_xpath_expr(string: str) -> str:
    # XPath doesn't have string escaping so we need to be creative.
    if "'" in string:
        parts = string.split("'")
        joined_parts = ', "\'", '.join(f"'{p}'" for p in parts)
        xpath_meta_name = f"concat({joined_parts})"
    else:
        xpath_meta_name = f"'{string}'"
    return xpath_meta_name


def _get_raw_html_text(element: selenium.webdriver.remote.webelement.WebElement) -> str:
    # Since we are using this value in Xpath later, it needs to be HTML-accurate, not the rendered text.
    return html.unescape(re.sub(r"<!--.*?-->", "", element.get_attribute("innerHTML"), flags=re.DOTALL))


@contextlib.contextmanager
def _webdriver() -> Generator[WebDriver, Any, None]:
    # try to use Chrome and fall back to Firefox
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=options)
    except Exception as e:
        logger.warning(f"Failed to initialize Chrome driver: {e}. Falling back to Firefox.")
        options = webdriver.FirefoxOptions()
        options.add_argument("--headless")
        driver = webdriver.Firefox(options=options)
    try:
        driver.implicitly_wait(time_to_wait=1)
        yield driver
    finally:
        driver.quit()


def load_map_list(base_url: str) -> list[MetaMap]:
    """
    Extracts a list of all available maps from the learnable metas site.
    base_url is the URL of the "Maps" page.
    """

    def extract_map_id(href: str) -> str | None:
        if not href:
            return None

        # Extract the map ID from URLs like "https://www.geoguessr.com/maps/66fda352ee1c8ee4735e1aa8"
        match = re.search(r"maps/([a-zA-Z0-9]+)", href)
        if match:
            return match.group(1)
        return None

    with _webdriver() as driver:
        driver.get(base_url)

        # Find all map containers
        map_containers = driver.find_elements(
            By.CSS_SELECTOR,
            "div.bg-card.text-card-foreground.rounded-xl.border.shadow.flex.flex-col",
        )

        maps_data = []
        for container in tqdm(map_containers):
            # Extract name
            name_element = container.find_element(By.CSS_SELECTOR, "h3.font-semibold.leading-none.tracking-tight")
            name = _get_raw_html_text(name_element)

            # Extract author
            author_element = container.find_element(By.CSS_SELECTOR, "p.text-muted-foreground.text-sm strong")
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


def scrape_map(meta_map: MetaMap) -> dict[str, str]:
    """
    Extracts a list of all metas from a single list.
    Returns a dict which maps meta names to their HTML content.
    """
    result: dict[str, str] = {}

    with _webdriver() as driver:
        # Navigate to the URL
        url = os.path.join(BASE_URL, "maps", meta_map.map_id)
        driver.get(url)

        # Wait for the table to load
        WebDriverWait(driver, 5).until(ec.presence_of_element_located((By.TAG_NAME, "table")))

        # Find all td elements
        td_elements = driver.find_elements(By.TAG_NAME, "td")

        xpath_map_name = _string_to_xpath_expr(meta_map.name)

        # Click on each td element and process the results
        for td in tqdm(td_elements):
            try:
                # Store the td text
                td_text = _get_raw_html_text(td)

                # Click the td element
                td.click()

                # Find the div with main contents
                xpath_meta_name = _string_to_xpath_expr(td_text)
                xpath_condition = f"[node()[contains(., {xpath_map_name})] and node()[contains(., {xpath_meta_name})]]"
                xpath = f"//*{xpath_condition}[not(./descendant::*{xpath_condition})]/div[not(./descendant::h1)]"
                target_div = driver.find_element(By.XPATH, xpath)
                # Store the data in our result list
                outer_html = target_div.get_attribute("outerHTML")
                if outer_html:
                    result[td_text] = outer_html
                else:
                    logger.warning(f"No outer HTML found for {td_text}")
            except Exception as e:
                logger.warning(str(e))

    return result
