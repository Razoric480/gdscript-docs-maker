"""Functions to format the markdown output for the static website engine hugo.
"""
import datetime
from argparse import Namespace
from dataclasses import dataclass
from typing import List

from .config import HUGO_FRONT_MATTER, LOGGER
from .gdscript_objects import GDScriptClass


@dataclass
class HugoFrontMatter:
    """Container for required front matter data for export to hugo-friendly markdown"""

    title: str
    description: str
    author: str
    date: datetime.date

    def as_string_list(self) -> List[str]:
        strings: List[str] = [
            self.title,
            self.description,
            self.author,
            "{:%Y-%m-%d}".format(self.date),
        ]
        LOGGER.debug("Hugo front matter:\n" + repr(strings))
        strings = list(map(quote_string, strings))
        return [HUGO_FRONT_MATTER["toml"].format(*strings) + "\n"]

    @classmethod
    def from_data(cls, gdscript: GDScriptClass, arguments: Namespace):
        name: str = gdscript.name
        if "abstract" in gdscript.tags:
            name += " (abstract)"
        return HugoFrontMatter(
            name,
            gdscript.description.replace("\n", "\\n"),
            arguments.author,
            arguments.date,
        )


FRONT_MATTER_DEFAULT: HugoFrontMatter = HugoFrontMatter(
    "", "", "", datetime.date.today()
)


def highlight_code(content: str, language: str = "gdscript") -> str:
    return make_shortcode(content, "highlight", language)


def make_shortcode(content: str, shortcode: str, *arguments: str, **kwargs: str) -> str:
    key_value_pairs: str = " ".join(["{}={}" for key, value in kwargs.items()])
    return "{{{{< {0} {1} {2} >}}}}{3}{{{{< / {0} >}}}}".format(
        shortcode, " ".join(arguments), key_value_pairs, content
    )


def quote_string(text: str) -> str:
    return '"' + text.replace('"', '\\"') + '"'
