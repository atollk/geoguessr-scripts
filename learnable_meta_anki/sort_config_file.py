import json


def sort_dict(d):
    if isinstance(d, dict):
        return {k: sort_dict(v) for k, v in sorted(d.items())}
    elif isinstance(d, list):
        return [sort_dict(x) for x in d]
    return d


def main():
    with open('config.json', 'r') as f:
        config = json.load(f)

    config = sort_dict(config)

    with open('config.json', 'w') as f:
        json.dump(config, f, indent=2)

if __name__ == '__main__':
    main()