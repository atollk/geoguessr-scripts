import argparse

import gooey

import learnable_meta_anki.main
import guess_explainer.main

@gooey.Gooey
def main():
    parser = gooey.GooeyParser(description="Utility for your Geoguessr experience.")
    subparsers: argparse._SubParsersAction = parser.add_subparsers(required=True, title="subcommand")
    learnable_meta_anki.main.add_subparser(subparsers)
    guess_explainer.main.add_subparser(subparsers)
    args = parser.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()