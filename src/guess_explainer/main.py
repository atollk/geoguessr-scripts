import argparse
import io
import os
import re
import urllib.parse
from time import sleep

import streetview
import tqdm
from PIL import Image
from google import genai
from google.genai import types
from playwright.sync_api import sync_playwright

PLONKIT_COUNTRIES = [
    # Africa
    "botswana",
    "egypt",
    "eswatini",
    "ghana",
    "kenya",
    "lesotho",
    "madagascar",
    "mali",
    "namibia",
    "reunion",
    "sao-tome-and-principe",
    "senegal",
    "south-africa",
    "tanzania",
    "tunisia",
    "nigeria",
    "uganda",
    "rwanda",
    # Asia
    "bhutan",
    "china",
    "bangladesh",
    "iraq",
    "cambodia",
    "hong-kong",
    "jordan",
    "laos",
    "israel-west-bank",
    "kazakhstan",
    "japan",
    "kyrgyzstan",
    "macau",
    "malaysia",
    "singapore",
    "pakistan",
    "south-korea",
    "qatar",
    "philippines",
    "sri-lanka",
    "mongolia",
    "oman",
    "united-arab-emirates",
    "nepal",
    "taiwan",
    "turkey",
    "thailand",
    "india",
    "indonesia",
    "lebanon",
    "vietnam",
    # Europe
    "andorra",
    "belarus",
    "azores",
    "albania",
    "austria",
    "croatia",
    "bulgaria",
    "denmark",
    "estonia",
    "czechia",
    "faroe-islands",
    "gibraltar",
    "finland",
    "hungary",
    "greece",
    "iceland",
    "germany",
    "france",
    "cyprus",
    "isle-of-man",
    "ireland",
    "jersey",
    "latvia",
    "liechtenstein",
    "lithuania",
    "luxembourg",
    "italy",
    "monaco",
    "malta",
    "montenegro",
    "madeira",
    "north-macedonia",
    "poland",
    "netherlands",
    "portugal",
    "norway",
    "san-marino",
    "serbia",
    "romania",
    "slovenia",
    "svalbard",
    "slovakia",
    "switzerland",
    "ukraine",
    "russia",
    "united-kingdom",
    "spain",
    "sweden",
    "belgium",
    # North America
    "united-states",
    "alaska",
    "dominican-republic",
    "costa-rica",
    "martinique",
    "guatemala",
    "hawaii",
    "puerto-rico",
    "panama",
    "canada",
    "us-virgin-islands",
    "greenland",
    "mexico",
    # South America
    "argentina",
    "bolivia",
    "chile",
    "brazil",
    "curacao",
    "colombia",
    "falkland-islands",
    "ecuador",
    "peru",
    "uruguay",
    # Oceania
    "american-samoa",
    "christmas-island",
    "cocos-islands",
    "guam",
    "northern-mariana-islands",
    "australia",
    "pitcairn-islands",
    "vanuatu",
    "new-zealand",
]


def load_plonkit_countries() -> None:
    os.makedirs("cache", exist_ok=True)
    with sync_playwright() as playwright:
        with playwright.chromium.launch(headless=True) as browser:
            page = browser.new_page()
            for country in tqdm.tqdm(PLONKIT_COUNTRIES):
                path = f"cache/plonk_{country}.pdf"
                if os.path.exists(path):
                    continue
                url = f"https://www.plonkit.net/{country}"
                page.goto(url)
                sleep(1)
                # todo: scroll to bottom before PDF, to load all images
                page.pdf(path=path)


def extract_panorama_id(url: str) -> str:
    """Extract the Street View panorama ID from a Google Maps URL."""
    url_decoded = urllib.parse.unquote(url)
    match = re.search("panoid=([^!]+)[&$]", url_decoded)
    if match:
        return match.group(1)
    match = re.search(r"!1s([^!]+)!", url)
    if match:
        return match.group(1)
    return ""


def ask_gemini(panorama_image: Image.Image, countries: list[str], api_key: str) -> str:
    # Load the plonkit files
    plonkit_files = [f"cache/plonk_{country}.pdf" for country in countries]
    guides_content = [types.Part.from_bytes(data=open(f, "rb").read(), mime_type="application/pdf") for f in
                      plonkit_files]

    # Encode the panorama
    buffer = io.BytesIO()
    panorama_image.save(buffer, format="JPEG")
    image_bytes = buffer.getbuffer().tobytes()
    image_content = [types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")]

    # Consult Gemini
    gemini_client = genai.Client(api_key=api_key)
    response = gemini_client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=image_content + guides_content,
        config=types.GenerateContentConfig(
            system_instruction="Your job is to analyze the given panorama image taken from Google Street View, and, using the provided descriptions of different countries, describe which of these countries you think the image is taken in. Provide reasons based on the documents why that country is likely and the others are less likely."
        )
    )
    return response.text


def add_subparser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "guess_explainer",
        help="Use AI to understand how a guess for a location can be explained.",
    )
    parser.add_argument(
        "--maps_url",
        type=str,
        required=True,
        help="The Google Maps URL of the Street View panorama.",
    )

    parser.add_argument(
        "--country",
        "-c",
        dest="countries",
        nargs="+",
        type=str,
        choices=sorted(PLONKIT_COUNTRIES),
        required=True,
        help="List of country names to consider.",
        widget="Listbox",
    )
    parser.add_argument(
        "--gemini_api_key",
        type=str,
        required=False,
        help="API key for Google Gemini. Alternatively, set the GEMINI_API_KEY environment variable.",
        default="",
    )

    def entry(args: argparse.Namespace):
        main(maps_url=args.maps_url, countries=args.countries,
             gemini_api_key=args.gemini_api_key or os.environ["GEMINI_API_KEY"])

    parser.set_defaults(func=entry)


# https://www.google.com/maps/@38.0691925,22.2390295,3a,90y,302.4h,92.61t/data=!3m7!1e1!3m5!1sC7dD4mGuuHHm6SjUq80gtw!2e0!6shttps:%2F%2Fstreetviewpixels-pa.googleapis.com%2Fv1%2Fthumbnail%3Fcb_client%3Dmaps_sv.tactile%26w%3D900%26h%3D600%26pitch%3D-2.612560000000002%26panoid%3DC7dD4mGuuHHm6SjUq80gtw%26yaw%3D302.40146!7i16384!8i8192?entry=ttu&g_ep=EgoyMDI2MDEwNC4wIKXMDSoASAFQAw%3D%3D

def main(maps_url: str, countries: list[str], gemini_api_key: str) -> None:
    print("Loading Plonkit country data... This may take a while the first time, but will be cached after.")
    load_plonkit_countries()
    print("Loading the Street View panorama image...")
    panorama_id = extract_panorama_id(maps_url)
    image = streetview.get_panorama(panorama_id)  # , multi_threaded=True)
    print("Asking AI to analyze the image...")
    response = ask_gemini(image, countries, gemini_api_key)
    print(response)


if __name__ == '__main__':
    main()
