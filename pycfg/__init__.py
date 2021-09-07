import codecs
from abc import abstractmethod
from configparser import ConfigParser, NoSectionError, NoOptionError, DuplicateSectionError, DuplicateOptionError


class ConfigFile:
    """ Base class for config objects """
    __immutable__ = False
    __autowrite__ = False

    def __init__(self, file=None, encoding=None, **kwargs):
        self.file = file
        self.encoding = encoding

        # Overwrite class options
        self.__immutable__ = kwargs.get('immutable', self.__immutable__)
        self.__autowrite__ = kwargs.get('autowrite', self.__autowrite__)

        self.parser:ConfigParser = None
        self._sections = {}
        if self.file:
            self.read()

    def read(self, file=None, encoding=None):
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
            raise FileNotFoundError("No file was given.")

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
            section._parse(self.parser)

    def register(self, section):
        if section in self:
            raise DuplicateSectionError(section)
        section.cfg = self
        self._sections[section.name] = section

    def create_section(self, name, *options):
        self.parser.add_section(name)
        Section(self, name, *options)

    def remove_section(self, section):
        if section not in self:
            raise NoSectionError(section)
        self.parser.remove_section(section)
        self._sections.pop(section)

    def __getitem__(self, section:str):
        if section not in self:
            raise NoSectionError(section)
        return self._sections[section]

    def set(self, section, option, value):
        if self.__immutable__:
            raise PermissionError("Config file '%s' is immutable." % self.filename)

        if not isinstance(section, Section):
            section = self[section]
        if not isinstance(option, Option):
            option = section.ref(option)

        if option.typecheck is not None and not option.typecheck(value):
            raise TypeError("Wrong type for option %s: %s, expected: %s." % (option.name, value, option.dtype))
        option.set(value)

        if not isinstance(option, UnlinkedOption):
            self.parser.set(
                section.name, option.name,
                option.to_str(value)
            )
            if self.__autowrite__:
                self.write()

    def write(self):
        """ Writes changes to the config parser to the file. """
        if not self.__immutable__:
            with open(self.file.name, 'w', encoding=self.encoding) as file:
                self.parser.write(file)

    def __len__(self):
        return len(self._sections)

    def __iter__(self):
        return iter(self._sections.values())

    @property
    def section_names(self):
        return list(self._sections.keys())

    def __contains__(self, section):
        return section in self._sections

    @abstractmethod
    def create(self):
        """ Override this method in a child class to parse config options """
        raise NotImplementedError('PyCfgFile needs to implement the create() method.')

    def __str__(self):
        return "<%s at %s>" % (self.__class__.__name__, self.file.name or '(unknown)')


class Section:
    def __init__(self, cfg:ConfigFile, name:str, *options):
        if not isinstance(name, str):
            raise TypeError("Section name must be a string.")
        if len(name) == 0:
            raise ValueError("Section name cannot be empty.")
        self.cfg = cfg
        self.name = name

        self._options = {}
        for option in options:
            self.register(option)

        if self.cfg is not None:
            self.cfg.register(self)

    def register(self, option):
        if isinstance(option, OptionCollection):
            option._register(self)
            return

        if option.name in self:
            raise DuplicateOptionError(self.name, option.name)
        option.sec = self
        self._options[option.name] = option
        if hasattr(option, '_initial_val'):
            self.set(option, option._initial_val)
            delattr(option, '_initial_val')

    def ref(self, option):
        if option not in self:
            raise NoOptionError(option, self.name)
        return self._options[option]

    def get(self, option, fallback=None):
        return self[option] if option in self else fallback

    def set(self, option, value):
        self.cfg.set(self, option, value)

    def raw(self, option, fallback=None):
        return self.ref(option).raw if option in self else fallback

    def __getitem__(self, option):
        return self.ref(option).get_value()

    def __setitem__(self, option, value):
        self.set(option, value)

    def __len__(self):
        return len(self._options)

    def __iter__(self):
        return iter(self._options)

    def __contains__(self, name):
        return name in self._options

    def keys(self):
        return self._options.keys()

    def values(self):
        for k in self:
            yield self[k]

    def items(self):
        for k in self:
            yield k, self[k]

    def _parse(self, parser:ConfigParser):
        for option in self._options.values():
            option._parse(parser, self.name)

    def __str__(self):
        return "<Section '%s'>" % self.name

    def __repr__(self):
        return "Section('%s')" % self.name


class Option:
    REFERENCE = object()
    __dtype__ = str
    __empty__ = ('', 'none', 'null'), None
    __optional__ = False

    def __init__(self, name, **kwargs):
        self.name = name
        self.sec:Section = None

        self.dtype = kwargs.get('dtype', self.__dtype__)
        self.empty = kwargs.get('empty', self.__empty__)
        self.optional = kwargs.get('optional', self.__optional__)
        if 'value' in kwargs: self._initial_val = kwargs['value']

    def set(self, value):
        self.value = value

    def from_str(self, string:str):
        return self.dtype(string)

    def to_str(self, value):
        return str(value)

    def typecheck(self, value):
        return self.dtype is None or isinstance(value, self.dtype)

    def _parse(self, parser:ConfigParser, section):
        """ Read the option value from the config file """
        try:
            self.raw = parser.get(section, self.name)
        except NoOptionError as e:
            if self.optional:
                self.value = self.empty[1]
                return
            else:
                raise e from None
        self.value = self.raw.replace('\n', ' ').strip()

        if self.value.lower() in self.empty[0]:
            self.value = self.empty[1]
        else:
            self.value = self.from_str(self.value)

    def get_value(self):
        if self.value is Option.REFERENCE: return self
        elif callable(self.value): return self.value()
        else: return self.value

    def __str__(self):
        return "<%s '%s/%s'>" % (self.__class__.__name__, self.sec.name, self.name)

    def __repr__(self):
        return "%s('%s')" % (self.__class__.__name__, self.name)

class UnlinkedOption(Option):
    def _parse(self, parser, section):
        # Unlinked, nothing to read
        pass

class DependentOption(UnlinkedOption):
    def __init__(self, name, value=None, references=None, pass_section=False, **kwargs):
        super().__init__(name, **kwargs)
        self._func = value or (lambda *args: None)
        self._refs = references or []
        self._pass_sec = pass_section
        if isinstance(self._refs, tuple):
            self._refs = list(self._refs)
        elif not isinstance(self._refs, list):
            self._refs = [self._refs]
        self._parse_references(self._refs)

    def set(self, value):
        raise PermissionError("Cannot set value on dependent option.")

    def _parse_references(self, refs):
        for i, reference in enumerate(refs):
            if isinstance(reference, str):
                reference = reference.split('/')
            elif not isinstance(reference, (tuple, list)):
                raise TypeError("Unexpected type for dependent option reference: %s %s, expected: str, tuple, list" % (reference, type(reference)))

            if len(reference) == 1:
                reference = (None, reference[0])
            if len(reference) > 2 or len(reference) <= 0:
                raise ValueError("Dependent option reference must be 1 or 2 elements in length (section, option), got: %s" % str(reference))
            elif not (reference[0] is None or isinstance(reference[0], str) and isinstance(reference[1], str)):
                raise ValueError("Dependent option references must be strings, got: %s" % str(reference))

            refs[i] = tuple(reference)

    def value(self):
        args = (self.sec.cfg[ref[0] or self.sec.name][ref[1]] for ref in self._refs)
        if self._pass_sec:
            return self._func(self.sec, *args)
        else:
            return self._func(*args)

class OptionCollection:
    def __init__(self, option_cls, *args, **kwargs):
        if not isinstance(option_cls, type):
            raise TypeError("Class expected for OptionCollection type, got '%s'." % option_cls)
        if not issubclass(option_cls, Option):
            raise TypeError("OptionCollection type %s does not inherit from Option." % option_cls)
        self._cls = option_cls
        self._filter = kwargs.get('name_filter')
        self._limit = kwargs.get('match_limit')
        self._args = args
        self._kwargs = kwargs

    def _register(self, sec):
        count = 0
        for name in sec.cfg.parser[sec.name]:
            if name not in sec \
                    and (self._limit is None or count < self._limit) \
                    and (not self._filter or self._filter(name)):
                sec.register(self._cls(name, *self._args, **self._kwargs))
                count += 1

class SectionCollection:
    class Option:
        def __init__(self, option_cls, *args, **kwargs):
            if not isinstance(option_cls, (type, OptionCollection)):
                raise TypeError("Class or OptionCollection expected for SectionCollection.Option type, got %s." % option_cls)
            if not (isinstance(option_cls, OptionCollection) or issubclass(option_cls, Option) or issubclass(option_cls, OptionCollection)):
                raise TypeError("SectionCollection.Option type %s does not inherit from Option or OptionCollection." % option_cls)
            self._cls = option_cls
            self._args = args
            self._kwargs = kwargs

        def __call__(self):
            if isinstance(self._cls, OptionCollection): return self._cls
            return self._cls(*self._args, **self._kwargs)

    def __init__(self, cfg:ConfigFile, *options:Option, **kwargs):
        self._filter = kwargs.get('name_filter')
        self._limit = kwargs.get('match_limit')
        self._register(cfg, options)

    def _register(self, cfg, options):
        count = 0
        for name in cfg.parser:
            if name != 'DEFAULT' \
                    and name not in cfg \
                    and (self._limit is None or count < self._limit) \
                    and (not self._filter or self._filter(name)):
                Section(cfg, name, *(option() for option in options))
                count += 1
