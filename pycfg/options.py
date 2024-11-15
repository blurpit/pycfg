import base64
import json
import pickle
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from typing import List

from . import Option, T


class StrOption(Option[str]):
    """ Option for strings """
    __type__ = str

    def from_str(self, string: str) -> str:
        return string

    def to_str(self, value: str) -> str:
        return value

class IntOption(Option[int]):
    """ Option for integers """
    __type__ = int

    def from_str(self, string: str) -> int:
        return int(string)

    def to_str(self, value: int) -> str:
        return str(value)

class FloatOption(Option[float]):
    """ Option for floats """
    __type__ = float

    def from_str(self, string: str) -> float:
        return float(string)

    def to_str(self, value: float) -> str:
        return str(value)

class DecimalOption(Option[Decimal]):
    """ Option for decimal.Decimal """
    __type__ = Decimal

    def from_str(self, string: str) -> Decimal:
        return Decimal(string)

    def to_str(self, value: Decimal) -> str:
        return str(value)

class BoolOption(Option[bool]):
    """ Option for booleans """
    __type__ = bool
    __truthy__ = ('true', 'yes', 'on', 'enabled')
    """ Text values that are considered truthy. """

    def from_str(self, string: str) -> bool:
        return string.lower() in self.__truthy__

    def to_str(self, value: bool) -> str:
        return str(value)

class ListOption(Option[List[T]]):
    __type__ = list
    __empty__ = (), None

    def __init__(
            self,
            name: str,
            item_type: Callable[[str], T] = str,
            delimiter: str = ', ',
            *,
            required: bool = True
    ):
        """
        Option for a list of values.

        :param item_type: A function that converts a string into the type
            you want the items in your list to be
        :param delimiter: A string delimiter that separates the items
        """
        super().__init__(name, required=required)
        self.item_type = item_type
        self.delimiter = delimiter

    def from_str(self, string: str) -> List[T]:
        if not string:
            return []

        strings = string.split(self.delimiter)

        # Convert each string into the item type
        items = []
        for item in strings:
            items.append(self.item_type(item))

        return items

    def to_str(self, value: List[T]):
        return self.delimiter.join(map(str, value))

class RangeOption(Option[range]):
    __type__ = range

    def __init__(self, name: str, delimiter: str = '-', *, required: bool = True):
        """
        Option for ranges of integers. The value is a standard python ``range()``.
        Start is inclusive, stop is exclusive.

        TODO: support non-ints, and `step` parameter

        :param delimiter: String that separates the start & stop when writing to the
            config file. Default is ``-``, e.g. range(0, 10) will be written as "0-10".
        """
        super().__init__(name, required=required)
        self.delimiter = delimiter

    def from_str(self, string: str):
        start, stop = string.split(self.delimiter)
        return range(int(start), int(stop))

    def to_str(self, value: range):
        return str(value.start) + self.delimiter + str(value.stop)

class DateTimeOption(Option[datetime]):
    ISOFORMAT = object()
    __type__ = datetime

    def __init__(self, name: str, fmt: str = ISOFORMAT, *, required: bool = True):
        """
        Option for dates & times

        :param fmt: Date/time format to use when writing the config file. If omitted,
            ISO format is used.
        """
        super().__init__(name, required=required)
        self.fmt = fmt

    def from_str(self, string: str) -> datetime:
        if self.fmt is self.ISOFORMAT:
            return datetime.fromisoformat(string)
        else:
            return datetime.strptime(string, self.fmt)

    def to_str(self, value: datetime):
        if self.fmt is self.ISOFORMAT:
            return value.isoformat()
        else:
            return value.strftime(self.fmt)

class DateOption(DateTimeOption):
    """ Option for dates """
    __type__ = date

    def from_str(self, string: str) -> date:
        return super().from_str(string).date()

class PickleOption(Option[T]):
    """
    Option for arbitrary Python objects. When writing to the config file,
    the object will be pickled and encoded as base64 text.
    """
    __type__ = None

    def from_str(self, string: str) -> T:
        encoding = self.section.cfg.encoding
        pickled = base64.b64decode(string.encode(encoding))
        return pickle.loads(pickled)

    def to_str(self, value: T):
        encoding = self.section.cfg.encoding
        pickled = pickle.dumps(value)
        return base64.b64encode(pickled).decode(encoding)

class DictOption(Option[dict]):
    """
    Option for dictionaries. When writing to the config file, the dictionary
    will be JSON stringified. Therefore the dictionary must be JSON serializable.
    If it isn't, you can use PickleOption instead.
    """
    __type__ = dict
    __empty__ = (), None

    def from_str(self, string: str) -> dict:
        return json.loads(string)

    def to_str(self, value: dict):
        return json.dumps(value)

JsonOption = DictOption
