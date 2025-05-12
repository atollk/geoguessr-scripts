import dataclasses

BASE_URL = "https://geometa-web.pages.dev/"

@dataclasses.dataclass
class Config:
    custom_image: dict[str, str | list[str]]
    select_image: dict[str, int]