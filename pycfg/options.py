import base64
import codecs
import datetime as dt
import decimal
import json
import pickle
import re
from typing import Any, Collection, Type, Union

from . import Option


class StrOption(Option):
    pass

class IntOption(Option):
    """ Option with int datatype """
    __type__ = int

class FloatOption(Option):
    """ Option with float datatype """
    __type__ = float

class DecimalOption(Option):
    """ Option with decimal.Decimal datatype """
    __type__ = decimal.Decimal

class BoolOption(Option):
    """ Option with bool datatype. Values passed into  """
    __type__ = bool
    __truthy__ = ('true', 'yes', 'on', 'enabled')

    def from_str(self, string:str):
        return string.lower() in self.__truthy__

class ListOption(Option):
    __type__ = list
    __empty__ = ('', '[]'), list()

    def __init__(self, name:str, delimiter:Union[str, re.Pattern]=', ', elem_types:Type=str, *, optional:bool=False):
        super().__init__(name, optional=optional)
        self.elem_types = elem_types
        self.delimiter = delimiter

    def from_str(self, string:str):
        if not string:
            return []

        if isinstance(self.delimiter, re.Pattern):
            result = self.delimiter.split(string)
        else:
            result = string.split(self.delimiter)

        if self.elem_types is not str:
            for i, x in enumerate(result):
                result[i] = self.elem_types(x)

        return result

    def to_str(self, value:Collection):
        return self.delimiter.join(map(str, value))

class TupleOption(ListOption):
    __type__ = tuple
    __empty__ = ('', '()'), tuple()

    def from_str(self, string:str):
        return tuple(super().from_str(string))

class SetOption(ListOption):
    __type__ = set
    __empty__ = ('', '{}'), set()

    def from_str(self, string):
        return set(super().from_str(string))

class RangeOption(Option):
    __type__ = range

    def __init__(self, name:str, delimiter:str='-', *, optional:bool=False):
        super().__init__(name, optional=optional)
        self.delimiter = delimiter

    def from_str(self, string:str):
        start, stop = string.split(self.delimiter)
        return range(int(start), int(stop))

    def to_str(self, value:range):
        return str(value.start) + self.delimiter + str(value.stop)

class DateTimeOption(Option):
    ISOFORMAT = object()
    __type__ = dt.datetime

    def __init__(self, name:str, fmt:str=ISOFORMAT, *, optional:bool=False):
        super().__init__(name, optional=optional)
        self.fmt = fmt

    def from_str(self, string:str):
        if self.fmt is self.ISOFORMAT:
            return dt.datetime.fromisoformat(string)
        else:
            return dt.datetime.strptime(string, self.fmt)

    def to_str(self, value:dt.datetime):
        if self.fmt is self.ISOFORMAT:
            return value.isoformat()
        else:
            return value.strftime(self.fmt)

class DateOption(DateTimeOption):
    __type__ = dt.date

    def from_str(self, string:str):
        return super().from_str(string).date()

class PickleOption(Option):
    __type__ = None

    def from_str(self, string:str):
        encoding = self.section.cfg.encoding
        pickled = base64.b64decode(string.encode(encoding))
        return pickle.loads(pickled)

    def to_str(self, value:Any):
        encoding = self.section.cfg.encoding
        pickled = pickle.dumps(value)
        return base64.b64encode(pickled).decode(encoding)

class JSONOption(Option):
    __type__ = None
    __empty__ = ('', '{}'), dict()

    def from_str(self, string:str):
        return json.loads(string)

    def to_str(self, value:dict):
        return json.dumps(value)

DictOption = JSONOption
