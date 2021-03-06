"""Converts the json representation of GDScript classes as dictionaries into objects
"""
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple
import itertools
import operator

BUILTIN_VIRTUAL_CALLBACKS = [
    "_process",
    "_physics_process",
    "_input",
    "_unhandled_input",
    "_gui_input",
    "_draw",
    "_get_configuration_warning",
    "_ready",
    "_enter_tree",
    "_exit_tree",
    "_get",
    "_get_property_list",
    "_notification",
    "_set",
    "_to_string",
    "_clips_input",
    "_get_minimum_size",
    "_gui_input",
    "_make_custom_tooltip",
]

TYPE_CONSTRUCTOR = "_init"


@dataclass
class ProjectInfo:
    name: str
    descrption: str
    version: str

    @classmethod
    def from_dict(cls, data: dict):
        return ProjectInfo(data["name"], data["description"], data["version"])


@dataclass
class Argument:
    name: str
    type: str


@dataclass
class Signal:
    signature: str
    name: str
    description: str
    arguments: List[str]


class FunctionTypes(Enum):
    METHOD = 1
    VIRTUAL = 2
    STATIC = 3


@dataclass
class Function:
    signature: str
    kind: FunctionTypes
    name: str
    description: str
    return_type: str
    arguments: List[Argument]
    rpc_mode: int
    tags: List[str]

    def summarize(self) -> List[str]:
        return [self.return_type, self.signature]


@dataclass
class Enumeration:
    """Represents an enum with its constants"""

    signature: str
    name: str
    description: str
    values: dict

    @classmethod
    def from_dict(cls, data: dict):
        return Enumeration(
            data["signature"], data["name"], data["description"], data["value"]
        )


@dataclass
class Member:
    """Represents a property or member variable"""

    signature: str
    name: str
    description: str
    type: str
    default_value: str
    is_exported: bool
    setter: str
    getter: str
    tags: List[str]

    def summarize(self) -> List[str]:
        return [self.type, self.name]


@dataclass
class GDScriptClass:
    name: str
    extends: str
    description: str
    path: str
    functions: List[Function]
    members: List[Member]
    signals: List[Signal]
    enums: List[Enumeration]
    tags: List[str]
    category: str

    @classmethod
    def from_dict(cls, data: dict):
        description, tags, category = get_metadata(data["description"])
        return GDScriptClass(
            data["name"],
            data["extends_class"],
            description.strip(" \n"),
            data["path"],
            _get_functions(data["methods"])
            + _get_functions(data["static_functions"], is_static=True),
            _get_members(data["members"]),
            _get_signals(data["signals"]),
            [
                Enumeration.from_dict(entry)
                for entry in data["constants"]
                if entry["data_type"] == "Dictionary"
            ],
            tags,
            category,
        )

    def extends_as_string(self) -> str:
        return " < ".join(self.extends)


class GDScriptClasses(list):
    """Container for a list of GDScriptClass objects

    Provides methods for filtering and grouping GDScript classes"""

    def __init__(self, *args):
        super(GDScriptClasses, self).__init__(args[0])

    def _get_grouped_by(self, attribute: str) -> List[List[GDScriptClass]]:
        if not self or attribute not in self[0].__dict__:
            return []

        groups = []
        get_attribute = operator.attrgetter(attribute)
        data = sorted(self, get_attribute)
        for key, group in itertools.groupby(data, get_attribute):
            groups.append(list(group))
        return groups

    def get_grouped_by_category(self) -> List[List[GDScriptClass]]:
        """Returns a list of lists of GDScriptClass objects, grouped by their `category`
attribute"""
        return self._get_grouped_by("category")

    @classmethod
    def from_dict_list(cls, data: List[dict]):
        return GDScriptClasses(
            [GDScriptClass.from_dict(entry) for entry in data if "name" in entry]
        )


def get_metadata(description: str) -> Tuple[str, List[str], str]:
    """Returns a tuple of (description, tags, category) from a docstring.

metadata should be of the form key: value, e.g. category: Category Name"""
    tags: List[str] = []
    category: str = ""

    lines: List[str] = description.split("\n")
    description_trimmed: List[str] = []
    for index, line in enumerate(lines):
        line_stripped: str = line.strip().lower()

        if line_stripped.startswith("tags:"):
            tags = line[line.find(":") + 1 :].split(",")
            tags = list(map(lambda t: t.strip(), tags))
            continue
        elif line_stripped.startswith("category:"):
            category = line[line.find(":") + 1 :].strip()
            continue
        else:
            description_trimmed.append(line)
    return "\n".join(description_trimmed), tags, category


def _get_signals(data: List[dict]) -> List[Signal]:
    signals: List[Signal] = []
    for entry in data:
        signal: Signal = Signal(
            entry["signature"], entry["name"], entry["description"], entry["arguments"],
        )
        signals.append(signal)
    return signals


def _get_functions(data: List[dict], is_static: bool = False) -> List[Function]:
    functions: List[Function] = []
    for entry in data:
        name: str = entry["name"]
        if name in BUILTIN_VIRTUAL_CALLBACKS:
            continue
        if name == TYPE_CONSTRUCTOR and not entry["arguments"]:
            continue

        description, tags, _ = get_metadata(entry["description"])
        is_virtual: bool = "virtual" in tags and not is_static
        is_private: bool = name.startswith("_") and not is_virtual
        if is_private:
            continue

        kind: FunctionTypes = FunctionTypes.METHOD
        if is_static:
            kind = FunctionTypes.STATIC
        elif is_virtual:
            kind = FunctionTypes.VIRTUAL

        function: Function = Function(
            entry["signature"].replace("-> null", "-> void", 1),
            kind,
            name,
            description.strip(" \n"),
            entry["return_type"].replace("null", "void", 1),
            _get_arguments(entry["arguments"]),
            entry["rpc_mode"] if "rpc_mode" in entry else 0,
            tags,
        )
        functions.append(function)
    return functions


def _get_arguments(data: List[dict]) -> List[Argument]:
    arguments: List[Argument] = []
    for entry in data:
        argument: Argument = Argument(
            entry["name"], entry["type"],
        )
        arguments.append(argument)
    return arguments


def _get_members(data: List[dict]) -> List[Member]:
    members: List[Member] = []
    for entry in data:
        # Skip private members
        if entry["name"].startswith("_"):
            continue
        description, tags, _ = get_metadata(entry["description"])
        member: Member = Member(
            entry["signature"],
            entry["name"],
            description.strip(" \n"),
            entry["data_type"],
            entry["default_value"],
            entry["export"],
            entry["setter"],
            entry["getter"],
            tags,
        )
        members.append(member)
    return members
