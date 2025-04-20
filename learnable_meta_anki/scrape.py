import dataclasses
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from tqdm import tqdm


@dataclasses.dataclass
class MetaMap:
    name: str
    author: str
    description: str
    map_id: str
    difficulty: str


def load_map_list(base_url: str) -> list[MetaMap]:
    """
    Extracts a list of all available maps from the learnable metas site.
    base_url is the URL of the "Maps" page.
    """
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
        name = name_element.text

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

    driver.quit()

    return [MetaMap(**x) for x in maps_data]


def scrape_table_data(url: str) -> dict[str, str]:
    """
    Extracts a list of all metas from a single list.
    Returns a dict which maps meta names to their HTML content.
    """
    result = {}

    # Set up the webdriver
    options = webdriver.FirefoxOptions()
    options.add_argument("--headless")  # Run in headless mode (optional)
    driver = webdriver.Firefox(options=options)
    driver.implicitly_wait(time_to_wait=1)

    # Navigate to the URL
    driver.get(url)

    # Wait for the table to load
    WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "table")))

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
        xpath_condition = (
            f"[node()[contains(., '{page_title}')] and node()[contains(., '{td_text.replace("'", "\\'")}')]]"
        )
        xpath = f"//*{xpath_condition}[not(./descendant::*{xpath_condition})]/div[not(./descendant::h1)]"
        target_div = driver.find_element(By.XPATH, xpath)

        if target_div is None:
            print(f"Error: Could not find a div containing the text '{page_title}'")
            continue

        # Store the data in our results list
        result[td_text] = target_div.get_attribute("outerHTML")

    driver.quit()
    return result
