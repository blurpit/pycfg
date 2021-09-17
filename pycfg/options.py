import codecs
import datetime as dt
import decimal
import json
import pickle
import re
from typing import Sequence, Collection

from . import Option


class StrOption(Option):
    pass

class IntOption(Option):
    """ Option with int datatype """
    __dtype__ = int

class FloatOption(Option):
    """ Option with float datatype """
    __dtype__ = float

class DecimalOption(Option):
    """ Option with decimal.Decimal datatype """
    __dtype__ = decimal.Decimal

class BoolOption(Option):
    """ Option with bool datatype. Values passed into  """
    __dtype__ = bool

    def __init__(self, name, true_values=('true', 'yes', 'on', 'enabled'), **kwargs):
        super().__init__(name, **kwargs)
        self.true_values = true_values

    def from_str(self, string):
        return string.lower() in self.true_values

class ListOption(Option):
    __empty__ = ('', '[]'), list()

    def __init__(self, name, delimiter=', ', force_dtype=True, sort=None, **kwargs):
        super().__init__(name, **kwargs)
        self.delimiter = delimiter
        self._force_dtype = force_dtype
        self._sort = sort

    def set(self, value):
        self.value = list(value)

    def from_str(self, string):
        if not string:
            return []
        if isinstance(self.delimiter, re.Pattern):
            result = self.delimiter.split(string)
        else:
            result = string.split(self.delimiter)
        if self.dtype != str:
            result = list(map(self.dtype, result))
        if self._sort:
            result.sort(key=self._sort if callable(self._sort) else None)
        return result

    def to_str(self, value):
        return self.delimiter.join(map(str, value))

    def typecheck(self, value):
        if not isinstance(value, Collection):
            raise TypeError("Wrong type for option %s: %s, expected typing.Collection" % (self.name, value))
        elif self._force_dtype:
            return all(isinstance(element, self.dtype) for element in value)
        return True

class TupleOption(ListOption):
    __empty__ = ('', '()'), tuple()

    def set(self, value):
        self.value = tuple(value)

    def from_str(self, string):
        return tuple(super().from_str(string))

class SetOption(ListOption):
    __empty__ = ('', '{}'), set()

    def set(self, value):
        self.value = set(value)

    def from_str(self, string):
        return set(super().from_str(string))

class RangeOption(Option):
    __dtype__ = tuple

    def __init__(self, name, delimiter='-', **kwargs):
        super().__init__(name, dtype=Sequence, reference=True, **kwargs)
        self.delimiter = delimiter
        self.start = 0
        self.stop = 0

    def set(self, value):
        """ Set the range. Value must be a tuple of (start, stop) """
        self.start, self.stop = value
        self.value = Option.REFERENCE

    def set_start(self, start):
        self.set((start, self.stop))

    def set_stop(self, stop):
        self.set((self.start, stop))

    def from_str(self, string):
        start, stop = string.split(self.delimiter)
        self.start = float(start.strip())
        self.stop = float(stop.strip())
        return Option

    def to_str(self, value):
        return str(self.start) + self.delimiter + str(self.stop)

    @property
    def size(self):
        return self.stop - self.start

    def __contains__(self, item):
        return self.start <= item <= self.stop

    def __str__(self):
        return "RangeOption(%s, %s)" % (self.start, self.stop)

class DateTimeOption(Option):
    ISOFORMAT = object()
    __dtype__ = dt.datetime

    def __init__(self, name, fmt=ISOFORMAT, **kwargs):
        super().__init__(name, **kwargs)
        self.fmt = fmt

    def from_str(self, string):
        if self.fmt == self.ISOFORMAT:
            return dt.datetime.fromisoformat(string)
        else:
            return dt.datetime.strptime(string, self.fmt)

    def to_str(self, value:dt.datetime):
        if self.fmt == self.ISOFORMAT:
            return value.isoformat()
        else:
            return value.strftime(self.fmt)

class DateOption(DateTimeOption):
    ISOFORMAT = "%Y-%m-%d"
    __dtype__ = dt.date

    def from_str(self, string):
        return super().from_str(string).date()

class PickleOption(Option):
    __dtype__ = None

    def __init__(self, name, pickler=pickle, encoding='base64', **kwargs):
        super().__init__(name, **kwargs)
        self.pickler = pickler
        self.encoding = encoding

    def from_str(self, string:str):
        return self.pickler.loads(codecs.decode(string.encode(), self.encoding))

    def to_str(self, value):
        return codecs.encode(self.pickler.dumps(value), self.encoding).decode()

class JSONOption(Option):
    __dtype__ = None
    __empty__ = ('', '{}'), dict()

    def from_str(self, string:str):
        return json.loads(string)

    def to_str(self, value):
        return json.dumps(value)

DictOption = JSONOption
