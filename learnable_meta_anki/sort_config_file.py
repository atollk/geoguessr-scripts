import json
from typing import Any, overload


@overload
def sort_dict(d: dict[str, Any]) -> dict[str, Any]:
    ...
@overload
def sort_dict(d: list[Any]) -> list[Any]:
    ...
@overload
def sort_dict(d: Any) -> Any:
    ...
def sort_dict(d: list[Any] | dict[str, Any] | Any) -> list[Any] | dict[str, Any] | Any:
    if isinstance(d, dict):
        return {k: sort_dict(v) for k, v in sorted(d.items())}
    elif isinstance(d, list):
        return [sort_dict(x) for x in d]
    return d


def main():
    with open('config.json', 'r') as f:
        config_raw: dict[str, Any] = json.load(f)

    config = sort_dict(config_raw)

    with open('config.json', 'w') as f:
        json.dump(config, f, indent=2)

if __name__ == '__main__':
    main()