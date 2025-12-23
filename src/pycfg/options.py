import base64
import json
import pickle
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, List, Optional, Tuple, Union

from .cfg import Option, Section, T, UnlinkedOption


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
    __empty__ = ('',), 0

    def from_str(self, string: str) -> int:
        return int(string)

    def to_str(self, value: int) -> str:
        return str(value)

class FloatOption(Option[float]):
    """ Option for floats """
    __type__ = float
    __empty__ = ('',), 0.0

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
    __empty__ = ('',), False
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

        TODO: support non-ints, `step` parameter, and inclusive end

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
        encoded = string.encode(encoding) if encoding else string.encode()
        pickled = base64.b64decode(encoded)
        return pickle.loads(pickled)

    def to_str(self, value: T):
        encoding = self.section.cfg.encoding
        pickled = pickle.dumps(value)
        b64 = base64.b64encode(pickled)
        return b64.decode(encoding) if encoding else b64.decode()

class DictOption(Option[dict]):
    """
    Option for dictionaries. When writing to the config file, the dictionary
    will be JSON stringified. Therefore the dictionary must be JSON serializable.
    If it isn't, you can use PickleOption instead.
    """
    __type__ = dict
    __empty__ = (), None

    def from_str(self, string: str) -> dict:
        if not string:
            return {}
        return json.loads(string)

    def to_str(self, value: dict):
        return json.dumps(value)

JsonOption = DictOption

class DerivedOption(UnlinkedOption[T]):
    """ See ``DerivedOption.__init__()`` """
    def __init__(self, name: str, value: Callable[..., T], references: List[Union[str, Tuple[str, str]]]):
        """
        A DerivedOption is an option that is calculated from the values of other options.

        To make a DerivedOption, pass in a value function and a list of references. The
        references are the other options that this derived option is calculated from.
        Each reference can be one of two formats:

            1. A tuple containing the section name of the referenced option, followed by
               the option name, e.g. ``('MySection', 'MyOption')``
            2. The name of the referenced option only, if the option is in the same section
               as the derived option.

        The value function takes in as parameters the values of the referenced options,
        in the same order as the references list. It returns the value for the derived
        option.

        Examples:
        ::

            def create(self):
                Section(
                    self, 'SecOne',
                    IntOption('OptA')
                )
                Section(
                    self, 'SecTwo',
                    IntOption('OptB'),
                    # Create a derived option referencing OptB
                    # in the same section.
                    DerivedOption(
                        'TripleB',
                        lambda b: 3*b,
                        ['OptB']
                    ),
                    # Create a derived option referencing OptB
                    # as well as OptA from a different section
                    DerivedOption(
                        'ABSum',
                        lambda a, b: a+b,
                        [('SecOne', 'OptA'), 'OptB']
                    )
                )

        You can access the values of the derived options the same as any other option.
        In the above example, with ``my_cfg['SecTwo']['TripleB']`` and
        ``my_cfg['SecTwo']['ABSum']``.

        The value function is called every time the option is accessed.

        :param name: Name of the option
        :param value: Function that takes referenced option values and returns the
            derived option value
        :param references: List of referenced option names, or (section, option) name
            pairs
        """
        super().__init__(name)
        self.value_func = value

        self.references: List[Tuple[Optional[str], str]] = []
        for i, ref in enumerate(references):
            # If a section wasn't passed, fill in None to be replaced later
            if isinstance(ref, str):
                self.references.append((None, ref))
            else:
                self.references.append(ref)

    def on_set(self, _):
        raise ValueError('Cannot set value on a DerivedOption')

    @property
    def value(self) -> T:
        return self.value_func(*self._get_args())

    def _get_args(self):
        for sec_name, opt_name in self.references:
            if sec_name is None:
                section = self.section
            else:
                section = self.section.cfg[sec_name]
            yield section[opt_name]

class OptionCollection(UnlinkedOption):
    """ See ``OptionCollection.__init__()`` """
    def __init__(self, option_maker: Callable[[str], Option[Any]]):
        """
        A collection of options. An OptionCollection will read all options written under
        a section in the config file, and create an Option for each one. It takes an
        option maker as a parameter, which is a function that takes in the name of an
        option and returns a new Option.

        OptionCollections are useful for when you want the config file to determine the
        options in your config rather than the other way around, and those options all
        have the same type.

        The OptionCollection will consume all options within a section that don't already
        have an Option object attached to it. So, if you have other options in the section
        that you don't want included in the OptionCollection, put those above the
        OptionCollection when you define your Section.

        Example:
        ::

            [MySection]
            A = 1
            B = 2
            C = 3
            SomethingElse = Hello world

            def create(self):
                Section(
                    self, 'MySection',
                    StringOption('SomethingElse'),
                    OptionCollection(
                        lambda name: IntOption(name)
                    )
                )

        In this example, the ``MySection`` section will have 3 IntOptions named
        ``A``, ``B``, and ``C``, and a StringOption named ``SomethingElse``.

        For simple option types, the constructor already acts as a (str) -> Option
        function, so you can simply pass in the option class itself. In the above
        example, this would look like ``OptionCollection(IntOption)``, with no need
        for the lambda.

        :param option_maker: Function that creates an Option given the option name
        """
        super().__init__('')
        self.option_maker = option_maker

    def on_register(self, section: Section):
        super().on_register(section)
        for name in section.cfg.parser[section.name]:
            if name not in section:
                section.register_option(self.option_maker(name))
        return False
