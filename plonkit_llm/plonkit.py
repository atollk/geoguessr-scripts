from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import os
import time
import json
import re
import base64
from urllib.parse import urljoin


class GeoGuessrScraper:
    def __init__(self, output_dir="pdfs"):
        """Initialize the scraper with configuration."""
        self.output_dir = output_dir
        self.options = webdriver.ChromeOptions()
        self.options.add_argument("--headless")
        self.options.add_argument("--disable-gpu")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")

        # Add PDF printing preferences
        self.options.add_experimental_option(
            "prefs",
            {
                "printing.print_preview_sticky_settings.appState": json.dumps(
                    {
                        "recentDestinations": [{"id": "Save as PDF", "origin": "local", "account": ""}],
                        "selectedDestinationId": "Save as PDF",
                        "version": 2,
                        "isHeaderFooterEnabled": False,
                    }
                )
            },
        )

        os.makedirs(output_dir, exist_ok=True)

    def start_driver(self):
        """Start a new Chrome driver instance."""
        self.driver = webdriver.Chrome(options=self.options)
        return self.driver

    def scroll_to_bottom(self, pause_time=1.0):
        """Smoothly scroll through the page to load all dynamic content."""
        print("Scrolling through page to load dynamic content...")

        # Get initial page height
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        while True:
            # Calculate current viewport height
            viewport_height = self.driver.execute_script("return window.innerHeight")
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            current_position = self.driver.execute_script("return window.pageYOffset")

            # Scroll in smaller increments (1/4 of viewport) for smoother loading
            scroll_increment = viewport_height / 4

            # Scroll until we reach bottom
            while current_position < total_height:
                next_position = min(current_position + scroll_increment, total_height)
                self.driver.execute_script(f"window.scrollTo(0, {next_position})")
                time.sleep(pause_time / 2)  # Shorter pause for incremental scrolls
                current_position = next_position

            # Wait for potential dynamic content to load
            time.sleep(pause_time)

            # Check if page height has changed
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                # Scroll back to top
                self.driver.execute_script("window.scrollTo(0, 0)")
                break
            last_height = new_height

    def get_country_links(self, base_url):
        """Extract all country subpage links from the main guide page."""
        try:
            self.driver.get(base_url)
            # Wait for initial content to load
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "mdb-table-row")))

            # Scroll through page to load all dynamic content
            self.scroll_to_bottom(pause_time=0.1)

            # Find all table rows with country data
            rows = self.driver.find_elements(By.CLASS_NAME, "mdb-table-row")
            country_links = []

            for row in rows:
                try:
                    onclick = row.get_attribute("onclick")
                    if onclick:
                        match = re.search(r"window\.open\('([^']+)'", onclick)
                        if match:
                            path = match.group(1)
                            full_url = urljoin(base_url, path)
                            country_name = row.find_element(By.CLASS_NAME, "flag-name").text
                            country_links.append({"url": full_url, "name": country_name})
                except Exception as e:
                    print(f"Error processing row: {e}")
                    continue

            return country_links
        except TimeoutException:
            print(f"Timeout while loading {base_url}")
            return []
        except Exception as e:
            print(f"Error getting country links: {e}")
            return []

    def save_as_pdf(self, url, filename):
        """Save a webpage as PDF without header and footer."""
        try:
            self.driver.get(url)
            # Wait for initial load
            time.sleep(2)

            # Scroll through page to load all dynamic content
            self.scroll_to_bottom(pause_time=0.1)

            # Remove header and footer if present
            try:
                header = self.driver.find_element(By.TAG_NAME, "header")
                footer = self.driver.find_element(By.TAG_NAME, "footer")
                self.driver.execute_script("arguments[0].style.display = 'none';", header)
                self.driver.execute_script("arguments[0].style.display = 'none';", footer)
            except:
                pass

            print(f"Saving {url} as PDF...")
            pdf = self.driver.execute_cdp_cmd(
                "Page.printToPDF",
                {
                    "printBackground": True,
                    "marginTop": 0,
                    "marginBottom": 0,
                    "marginLeft": 0,
                    "marginRight": 0,
                },
            )

            filepath = os.path.join(self.output_dir, filename)
            pdf_data = base64.b64decode(pdf["data"])
            with open(filepath, "wb") as f:
                f.write(pdf_data)

            print(f"Saved {filepath}")
            return True
        except Exception as e:
            print(f"Error saving PDF for {url}: {e}")
            return False

    def process_all_pages(self, base_url):
        """Process the main guide page and all country subpages."""
        try:
            self.start_driver()

            # Save main guide page
            main_page_filename = "main_guide.pdf"
            self.save_as_pdf(base_url, main_page_filename)

            # Get all country links
            country_links = self.get_country_links(base_url)
            print(f"Found {len(country_links)} country pages")

            # Process each country page
            for country in country_links:
                filename = f"{country['name'].lower().replace(' ', '_')}.pdf"
                self.save_as_pdf(country["url"], filename)
                time.sleep(1)  # Be nice to the server

        except Exception as e:
            print(f"Error in main process: {e}")
        finally:
            self.driver.quit()


def main():
    base_url = "https://www.plonkit.net/guide"
    scraper = GeoGuessrScraper(output_dir="plonkit_guides")
    scraper.process_all_pages(base_url)


if __name__ == "__main__":
    main()
