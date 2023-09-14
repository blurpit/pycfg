import codecs
from abc import abstractmethod
from configparser import ConfigParser, DuplicateOptionError, DuplicateSectionError, NoOptionError, NoSectionError
from typing import Any, Dict, Iterable, List, Optional, TextIO, Tuple, Type, Union


class ConfigFile:
    """ Base class for config objects """
    __immutable__ = False

    def __init__(self, file:Union[TextIO, str, None], encoding:Optional[str]=None):
        self.file = file
        self.encoding = encoding

        self.parser:Optional[ConfigParser] = None
        self._sections:Dict[str, Section] = {}
        if self.file:
            self.read()

    def read(self, file:Union[TextIO, str, None]=None, encoding:Optional[str]=None):
        """
        Read config file.

        :param file: File-like object or a file path to read, if not already given in the constructor.
        :param encoding: File encoding. Default is platform-specific
        """
        if file:
            self.file = file
        if encoding:
            self.encoding = encoding
        if not self.file:
            raise FileNotFoundError('No file was given.')

        self.parser = ConfigParser()
        self.parser.optionxform = str

        if isinstance(self.file, str):
            self.file = codecs.open(
                self.file,
                mode='r' if self.__immutable__ else 'r+',
                encoding=self.encoding
            )
        elif self.file.closed:
            self.file = codecs.open(
                self.file.name,
                mode='r' if self.__immutable__ else 'r+',
                encoding=self.encoding
            )
        self.parser.read_file(self.file)
        self.file.close()

        self._sections = {}
        self.create()
        for section in self:
            section.parse(self.parser)

    def register(self, section:'Section'):
        if section in self:
            raise DuplicateSectionError(section.name)
        section.cfg = self
        self._sections[section.name] = section

    def create_section(self, section_name:str, *options:'Option') -> 'Section':
        self.parser.add_section(section_name)
        return Section(self, section_name, *options)

    def remove_section(self, section_name:str) -> 'Section':
        if section_name not in self:
            raise NoSectionError(section_name)
        self.parser.remove_section(section_name)
        return self._sections.pop(section_name)

    def __getitem__(self, section:str) -> 'Section':
        if section not in self:
            raise NoSectionError(section)
        return self._sections[section]

    def set(self, section:Union['Section', str], option:Union['Option', str], value:Any):
        if self.__immutable__:
            raise PermissionError("Config file '%s' is immutable." % self.filename)

        # Convert str -> Section and make sure it is in the config
        if isinstance(section, str):
            section = self[section]
            if section not in self:
                raise NoSectionError(section.name)

        # Convert str -> Option and make sure it is in the section
        if isinstance(option, str):
            option = section.get_ref(option)
            if option not in section:
                raise NoOptionError(option.name, section.name)

        # Set option value
        option.set(value)

        if not isinstance(option, UnlinkedOption):
            self.parser.set(
                section.name, option.name,
                option.to_str(value)
            )

    def save(self):
        """ Writes changes to the config parser to the file. """
        if not self.__immutable__:
            with open(self.filename, 'w', encoding=self.encoding) as file:
                self.parser.write(file)

    def __len__(self):
        return len(self._sections)

    def __iter__(self):
        return iter(self._sections.values())

    def __contains__(self, section:Union['Section', str]):
        if isinstance(section, Section):
            return section.cfg is self and section.name in self._sections
        elif isinstance(section, str):
            return section in self._sections
        else:
            return False

    @abstractmethod
    def create(self):
        """ Override this method in a child class to parse config options """
        raise NotImplementedError('PyCfgFile needs to implement the create() method.')

    @property
    def filename(self) -> str:
        if isinstance(self.file, TextIO):
            return self.file.name
        elif isinstance(self.file, str):
            return self.file
        else:
            return '(unknown)'

    @property
    def section_names(self) -> List[str]:
        return list(self._sections.keys())

    def __str__(self):
        return "<%s at %s>" % (type(self).__name__, self.filename)


class Section:
    def __init__(self, cfg:ConfigFile, name:str, *options:'Option'):
        self.cfg = cfg
        self.name = name

        self._options:Dict[str, Option] = {}
        for option in options:
            self.register(option)

        self.cfg.register(self)

    def register(self, option:'Option'):
        if option.name in self:
            raise DuplicateOptionError(self.name, option.name)
        option.section = self
        self._options[option.name] = option
        if hasattr(option, '_initial_val'):
            self.set(option, option._initial_val)
            delattr(option, '_initial_val')

    def get_ref(self, option_name:str) -> 'Option':
        if option_name not in self:
            raise NoOptionError(option_name, self.name)
        return self._options[option_name]

    def get(self, option_name:str, default:Any=None) -> Any:
        if option_name in self:
            return self[option_name]
        else:
            return default

    def set(self, option:Union['Option', str], value:Any):
        self.cfg.set(self, option, value)

    def get_raw(self, option) -> str:
        return self.get_ref(option).raw

    def __getitem__(self, option_name:str) -> Any:
        return self.get_ref(option_name).get_value()

    def __setitem__(self, option:Union['Option', str], value:Any):
        self.set(option, value)

    def __len__(self):
        return len(self._options)

    def __iter__(self):
        return iter(self._options)

    def __contains__(self, option:Union['Option', str]):
        if isinstance(option, Option):
            return option.section is self and option.name in self._options
        elif isinstance(option, str):
            return option in self._options
        else:
            return False

    def keys(self) -> Iterable[str]:
        return self._options.keys()

    def values(self) -> Iterable[Any]:
        for k in self:
            yield self[k]

    def items(self) -> Iterable[Tuple]:
        for k in self:
            yield k, self[k]

    def parse(self, parser:ConfigParser):
        for option in self._options.values():
            option.parse(parser, self.name)

    def __str__(self):
        return "<Section '%s'>" % self.name

    def __repr__(self):
        return "Section('%s')" % self.name


class Option:
    __type__ = str
    __empty__ = ('', 'none', 'null'), None

    def __init__(self, name:str, optional:bool=False):
        self.name = name
        self.section:Optional[Section] = None
        self.optional = optional
        self.value = self.__empty__[1]
        self.raw_value:Optional[str] = None

    def set(self, value:Any):
        # Check value type
        if not isinstance(value, self.__type__):
            raise TypeError("{}/{} expected type '{}', got '{}'".format(
                self.section.name, self.name, self.__type__.__name__, type(value).__name__
            ))

        self.value = value

    def from_str(self, string:str) -> Any:
        return self.__type__(string)

    def to_str(self, value:Any) -> str:
        return str(value)

    def parse(self, parser:ConfigParser, section_name:str):
        """ Read the option value from the config file """
        try:
            self.raw_value = parser.get(section_name, self.name)
        except NoOptionError as e:
            if self.optional:
                self.value = self.__empty__[1]
                return
            else:
                raise e from None
        self.value = self.raw_value.replace('\n', ' ').strip()

        if self.value.lower() in self.__empty__[0]:
            # Empty value
            self.value = self.__empty__[1]
        else:
            # Set value using from_str
            self.value = self.from_str(self.value)

    def __str__(self):
        return "<{} '{}/{}'>".format(type(self).__name__, self.section.name, self.name)

    def __repr__(self):
        return "{}('{}')".format(type(self).__name__, self.name)

class UnlinkedOption(Option):
    def parse(self, parser, section_name):
        # Unlinked options have nothing to read
        pass

# class DependentOption(UnlinkedOption):
#     def __init__(self, name, value=None, references=None, pass_section=False, **kwargs):
#         super().__init__(name, **kwargs)
#         self._func = value or (lambda *args: None)
#         self._refs = references or []
#         self._pass_sec = pass_section
#         if isinstance(self._refs, tuple):
#             self._refs = list(self._refs)
#         elif not isinstance(self._refs, list):
#             self._refs = [self._refs]
#         self._parse_references(self._refs)
#
#     def set(self, value):
#         raise PermissionError("Cannot set value on dependent option.")
#
#     def _parse_references(self, refs):
#         for i, reference in enumerate(refs):
#             if isinstance(reference, str):
#                 reference = reference.split('/')
#             elif not isinstance(reference, (tuple, list)):
#                 raise TypeError("Unexpected type for dependent option reference: %s %s, expected: str, tuple, list" % (reference, type(reference)))
#
#             if len(reference) == 1:
#                 reference = (None, reference[0])
#             if len(reference) > 2 or len(reference) <= 0:
#                 raise ValueError("Dependent option reference must be 1 or 2 elements in length (section, option), got: %s" % str(reference))
#             elif not (reference[0] is None or isinstance(reference[0], str) and isinstance(reference[1], str)):
#                 raise ValueError("Dependent option references must be strings, got: %s" % str(reference))
#
#             refs[i] = tuple(reference)
#
#     def value(self):
#         args = (self.sec.cfg[ref[0] or self.sec.name][ref[1]] for ref in self._refs)
#         if self._pass_sec:
#             return self._func(self.sec, *args)
#         else:
#             return self._func(*args)
#
# class OptionCollection:
#     def __init__(self, option_cls, *args, **kwargs):
#         if not isinstance(option_cls, type):
#             raise TypeError("Class expected for OptionCollection type, got '%s'." % option_cls)
#         if not issubclass(option_cls, Option):
#             raise TypeError("OptionCollection type %s does not inherit from Option." % option_cls)
#         self._cls = option_cls
#         self._filter = kwargs.get('name_filter')
#         self._limit = kwargs.get('match_limit')
#         self._args = args
#         self._kwargs = kwargs
#
#     def _register(self, sec):
#         count = 0
#         for name in sec.cfg.parser[sec.name]:
#             if name not in sec \
#                     and (self._limit is None or count < self._limit) \
#                     and (not self._filter or self._filter(name)):
#                 sec.register(self._cls(name, *self._args, **self._kwargs))
#                 count += 1
#
# class SectionCollection:
#     class Option:
#         def __init__(self, option_cls, *args, **kwargs):
#             if not isinstance(option_cls, (type, OptionCollection)):
#                 raise TypeError("Class or OptionCollection expected for SectionCollection.Option type, got %s." % option_cls)
#             if not (isinstance(option_cls, OptionCollection) or issubclass(option_cls, Option) or issubclass(option_cls, OptionCollection)):
#                 raise TypeError("SectionCollection.Option type %s does not inherit from Option or OptionCollection." % option_cls)
#             self._cls = option_cls
#             self._args = args
#             self._kwargs = kwargs
#
#         def __call__(self):
#             if isinstance(self._cls, OptionCollection): return self._cls
#             return self._cls(*self._args, **self._kwargs)
#
#     def __init__(self, cfg:ConfigFile, *options:Option, **kwargs):
#         self._filter = kwargs.get('name_filter')
#         self._limit = kwargs.get('match_limit')
#         self._register(cfg, options)
#
#     def _register(self, cfg, options):
#         count = 0
#         for name in cfg.parser:
#             if name != 'DEFAULT' \
#                     and name not in cfg \
#                     and (self._limit is None or count < self._limit) \
#                     and (not self._filter or self._filter(name)):
#                 Section(cfg, name, *(option() for option in options))
#                 count += 1
