
import asyncio
import re
from typing import List, Optional, Union
from playwright.async_api import async_playwright, Page, Browser, ElementHandle
from dataclasses import dataclass
from PIL import Image
import requests
from io import BytesIO


@dataclass
class ImageData:
    """Represents an image with its source URL and optional Pillow object."""
    src_url: str
    pillow_image: Optional[Image.Image] = None


@dataclass
class TextContentBlock:
    """A content block containing only text."""
    text: str


@dataclass
class ImageContentBlock:
    """A content block containing only an image."""
    image: ImageData


@dataclass
class TextWithImageContentBlock:
    """A content block containing both text and an image with a link."""
    text: str
    image: ImageData
    image_link_url: str


# Union type for all possible content block types
StepContentBlock = Union[TextContentBlock, ImageContentBlock, TextWithImageContentBlock]


@dataclass
class Step:
    """Represents a step with its title and content blocks."""
    title: str
    blocks: List[StepContentBlock]


@dataclass
class PageData:
    """Represents the parsed data from a sub-page."""
    steps: List[Step]


async def download_image(url: str) -> Optional[Image.Image]:
    """
    Download an image from a URL and return it as a Pillow Image object.

    Args:
        url: The URL of the image to download

    Returns:
        PIL Image object or None if download fails
    """
    try:
        # Make sure the URL is absolute
        if url.startswith('//'):
            url = 'https:' + url
        elif url.startswith('/'):
            url = 'https://www.plonkit.net' + url

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # Create PIL Image from response content
        image = Image.open(BytesIO(response.content))
        return image

    except Exception as e:
        print(f"Warning: Failed to download image from {url}: {e}")
        return None


async def extract_text_with_link_replacement(element: ElementHandle) -> str:
    """
    Extract text from an element, replacing <a> tag content with their href URLs.

    Args:
        element: The Playwright element to extract text from

    Returns:
        Text with link replacements
    """
    # Get all anchor tags within the element
    links = await element.query_selector_all('a')

    # Build a mapping of link text to URLs
    link_replacements = {}
    for link in links:
        href = await link.get_attribute('href')
        text = await link.inner_text()
        if href and text:
            # Make href absolute if needed
            if href.startswith('/'):
                href = 'https://www.plonkit.net' + href
            elif href.startswith('//'):
                href = 'https:' + href
            link_replacements[text] = href

    # Get the full text
    full_text = await element.inner_text()

    # Replace link text with URLs
    for text, url in link_replacements.items():
        full_text = full_text.replace(text, url)

    return full_text.strip()


async def parse_step_content_section(section_element: ElementHandle) -> StepContentBlock:
    """
    Parse a content section into the appropriate StepContentBlock type.
    Handles three types: text-only, image-only, and text-with-image.

    Args:
        section_element: The Playwright element representing a section

    Returns:
        A StepContentBlock of the appropriate type
    """
    # Check for figure > a > img pattern (text with image)
    figure_link_img = await section_element.query_selector('figure a img')

    if figure_link_img:
        # Type 3: Text with image
        # Get the image source
        img_src = await figure_link_img.get_attribute('src')
        if not img_src:
            img_src = await figure_link_img.get_attribute('data-src')  # Fallback for lazy loading

        # Get the link URL (from the parent <a> element)
        link_element = await section_element.query_selector('figure a')
        image_link_url = await link_element.get_attribute('href') if link_element else ''

        # Make URLs absolute
        if img_src and img_src.startswith('/'):
            img_src = 'https://www.plonkit.net' + img_src
        elif img_src and img_src.startswith('//'):
            img_src = 'https:' + img_src

        if image_link_url and image_link_url.startswith('/'):
            image_link_url = 'https://www.plonkit.net' + image_link_url
        elif image_link_url and image_link_url.startswith('//'):
            image_link_url = 'https:' + image_link_url

        # Download the image
        pillow_image = await download_image(img_src) if img_src else None

        # Extract text with link replacements
        text_content = await extract_text_with_link_replacement(section_element)

        # Create image data
        image_data = ImageData(src_url=img_src or '', pillow_image=pillow_image)

        return TextWithImageContentBlock(
            text=text_content,
            image=image_data,
            image_link_url=image_link_url or ''
        )

    # Check for standalone image (not in figure > a > img pattern)
    standalone_img = await section_element.query_selector('img')

    if standalone_img:
        # Type 2: Image only
        img_src = await standalone_img.get_attribute('src')
        if not img_src:
            img_src = await standalone_img.get_attribute('data-src')  # Fallback for lazy loading

        # Make URL absolute
        if img_src and img_src.startswith('/'):
            img_src = 'https://www.plonkit.net' + img_src
        elif img_src and img_src.startswith('//'):
            img_src = 'https:' + img_src

        # Download the image
        pillow_image = await download_image(img_src) if img_src else None

        # Create image data
        image_data = ImageData(src_url=img_src or '', pillow_image=pillow_image)

        return ImageContentBlock(image=image_data)

    # Type 1: Text only (default case)
    text_content = await extract_text_with_link_replacement(section_element)

    return TextContentBlock(text=text_content)

async def extract_onclick_parameters(page: Page, url: str) -> list[str]:
    """
    Opens a Playwright browser, navigates to the given URL, and extracts
    the first parameter from onclick attributes matching the pattern
    onclick="window.open('/parameter','_blank')".

    Args:
        url: The URL to navigate to

    Returns:
        List of extracted parameters (strings)
    """
    parameters: List[str] = []

    # Navigate to the URL
    await page.goto(url)

    # Wait for the page to load completely
    await page.wait_for_load_state('networkidle')

    # Find all elements with onclick attributes
    elements = await page.query_selector_all('[onclick]')

    # Regular expression to match the pattern and extract the first parameter
    # This matches: window.open('/parameter','_blank') or window.open("/parameter","_blank")
    pattern = re.compile(r"window\.open\(['\"]([^'\"]+)['\"],\s*['\"]_blank['\"]")

    for element in elements:
        onclick_value = await element.get_attribute('onclick')
        if onclick_value:
            match = pattern.search(onclick_value)
            if match:
                # Extract the parameter (remove leading slash if present)
                parameter = match.group(1)
                if parameter.startswith('/'):
                    parameter = parameter[1:]
                parameters.append(parameter)


    return parameters


async def parse_subpage(page: Page, subpage_url: str) -> PageData:
    """
    Navigates to a sub-page URL and parses it into a structured data format.

    Args:
        page: The Playwright page object to use for navigation
        subpage_url: The URL of the sub-page to parse

    Returns:
        PageData containing the parsed steps and their content blocks
    """
    await page.goto(subpage_url)
    await page.wait_for_load_state('networkidle')

    # Find the main article content
    article = await page.query_selector('body main article')
    if not article:
        print(f"Warning: Could not find main article content on {subpage_url}")
        return PageData(steps=[])

    # Get all section children
    sections = await article.query_selector_all('section')

    steps: List[Step] = []
    current_step: Optional[Step] = None

    # Pattern to match "Step [number] - [title]"
    step_pattern = re.compile(r'Step\s+\d+\s*[-–]\s*(.+)', re.IGNORECASE)

    for section in sections:
        section_text = (await section.inner_text()).strip()

        # Check if this section defines a new step
        step_match = step_pattern.match(section_text)

        if step_match:
            # This is a step header - save the previous step if it exists
            if current_step is not None:
                steps.append(current_step)

            # Start a new step
            step_title = step_match.group(1).strip()
            current_step = Step(title=step_title, blocks=[])

        else:
            # This is a content section
            if current_step is not None:
                # Parse the content section and add it to the current step
                content_block = await parse_step_content_section(section)
                current_step.blocks.append(content_block)
            else:
                # Content section found before any step header - could be intro content
                #print(f"Warning: Found content section before step header on {subpage_url}")
                pass

    # Don't forget to add the last step
    if current_step is not None:
        steps.append(current_step)

    return PageData(steps=steps)


async def process_all_subpages(base_url: str) -> dict[str, PageData]:
    """
    Extracts onclick parameters from the main page and processes all sub-pages.

    Args:
        base_url: The base URL to start from

    Returns:
        Dictionary mapping parameter names to their parsed PageData
    """
    results: dict[str, PageData] = {}

    async with async_playwright() as playwright:
        browser: Browser = await playwright.chromium.launch(headless=True)

        try:
            page: Page = await browser.new_page()
            parameters = await extract_onclick_parameters(page, base_url)

            for param in parameters[0:1]:
                print(param)
                subpage_url = f"https://www.plonkit.net/{param}"
                page_data = await parse_subpage(page, subpage_url)
                results[param] = page_data

        finally:
            await browser.close()

    return results


async def main() -> None:
    """Main function to demonstrate usage."""
    base_url = "https://www.plonkit.net/guide"

    # Process all sub-pages
    all_data = await process_all_subpages(base_url)

    print(f"Processed {len(all_data)} pages:")

    for param, page_data in all_data.items():
        print(f"\n{param}:")
        print(f"  Steps: {len(page_data.steps)}")
        for i, step in enumerate(page_data.steps, 1):
            print(f"    {i}. {step.title} ({len(step.blocks)} blocks)")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())