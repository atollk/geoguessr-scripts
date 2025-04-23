# learnable-meta Anki generator

Generate [Anki](https://apps.ankiweb.net/) decks from [Learnable Meta](https://geometa-web.pages.dev/) maps.

At the moment, the distribution license of Learnable Meta does not allow its content to be shared, so there is no Anki
deck you can just download and use.
You can, however, run this script yourself to generate the deck on your computer.

## Running the script

Requirements are:
- Python 3.12 or newer
- Firefox (I'll probably add Chrome support soon)

You need to download this git repository (either via `git clone` or the download button on the GitHub website).
Then, run the following code in your command line (from the geoguessr-scripts folder) to build the Anki deck.
This is written for Linux (bash); it should work on macOS, but if you are on Windows, you probably need to make some
adaptions to get it working with cmd.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m learnable_meta_anki.learnablemetas
```

## Bad cards / Contribution

The script works by creating one or multiple Anki cards for each meta in a map.
For each image detected in the meta's explanation, one card is created with that image on the front and the entire
explanation on the back.

This works for most metas on the website, but for some the images contain hints to the answers, which defeats the
purpose of that card.
The file `config.json` contains a list of manual fixes.
That list is created and maintained entirely by hand, so if you encounter a card with a bad front image, create a GitHub
issue for this project, or, even better, a pull request to fix it.