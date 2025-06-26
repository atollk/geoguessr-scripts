import dataclasses

BASE_URL = "https://learnablemeta.com/"


@dataclasses.dataclass
class Config:
    custom_image: dict[str, str | list[str]]
    select_image: dict[str, int]
