from __future__ import annotations

import codecs
from abc import ABC, abstractmethod
from configparser import ConfigParser, DuplicateOptionError, DuplicateSectionError, NoOptionError, NoSectionError
from copy import copy
from typing import Any, Dict, Generic, Iterable, List, Optional, TextIO, Tuple, Type, TypeVar, Union


class ConfigFile:
    """
    The base class for python config files. Create a class that inherits from ConfigFile
    and override the ``create()`` method to make your config file definition.
    ::

        class MyConfig(ConfigFile):
            def create(self):
                Section(
                    self, 'Section One',
                    ...
                )
    """

    __readonly__ = False
    """
    Set ``__readonly__`` to True to prevent changing the values of any options, adding/removing
    sections, or writing to the config file in any way.
    """

    def __init__(self, file: Union[TextIO, str, None] = None, encoding: Optional[str] = None):
        """
        Instantiate your config object. If a file or filepath is given here, the file will
        be read. If a file isn't given in the constructor, you can read one later using ``read()``.

        :param file: File-like object or a file path to read, or None.
        :param encoding: File encoding, or None.
        """
        self.file = file
        self.encoding = encoding

        self.parser: Optional[ConfigParser] = None
        self._sections: Dict[str, Section] = {}
        if self.file:
            self.read()

    def read(self, file: Union[TextIO, str, None] = None, encoding: Optional[str] = None):
        """
        Read a config file.

        :param file: File-like object or a file path to read, if not already given in the constructor.
        :param encoding: File encoding. Default is platform-specific
        :raise FileNotFoundError: if no file was given or if the file wasn't found
        """
        # Get the file
        if file:
            self.file = file
        if encoding:
            self.encoding = encoding
        if not self.file:
            raise FileNotFoundError('No file was given.')

        # Create parser
        self.parser = ConfigParser()
        self.parser.optionxform = str

        # Open file
        if isinstance(self.file, str):
            # Open file path
            self.file = codecs.open(
                self.file,
                mode='r' if self.__readonly__ else 'r+',
                encoding=self.encoding
            )
        elif self.file.closed:
            # Open file if not already open
            self.file = codecs.open(
                self.file.name,
                mode='r' if self.__readonly__ else 'r+',
                encoding=self.encoding
            )

        # Read the file using configparser, and close the file
        self.parser.read_file(self.file)
        self.file.close()

        # Call create() to register all sections, then parse them all
        self._sections = {}
        self.create()
        for section in self:
            section.parse(self.parser)

    def register_section(self, section: Section):
        """ Register a section with this config file. """
        if section in self:
            raise DuplicateSectionError(section.name)

        if section.on_register(self):
            self._sections[section.name] = section

    def create_section(self, section: Section):
        """
        Create a new section in the config file.

        :param section: New Section to write into the file
        """
        self.parser.add_section(section.name)

    def delete_section(self, section_name: str) -> Section:
        """
        Delete a section from the file, and returns the removed Section.

        :param section_name: Name of the section to delete
        :return: Section object that was deleted
        """
        if section_name not in self:
            raise NoSectionError(section_name)
        self.parser.remove_section(section_name)
        return self._sections.pop(section_name)

    def __getitem__(self, section: str) -> 'Section':
        """ Get a Section by name """
        if section not in self:
            raise NoSectionError(section)
        return self._sections[section]

    def set(self, section: Union['Section', str], option: Union['Option', str], value: Any):
        """
        Set the value of an option in the config.

        The following are all equivalent:
        ::

            my_config.set('Section One', 'SomeOption', 3)
            my_config['Section One'].set('SomeOption', 3)
            my_config['Section One']['SomeOption'] = 3

        :param section: Section, or name of the section the option is in
        :param option: The option, or name of the option to change
        :param value: New value to set the option to
        """
        if self.__readonly__:
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
                option.raw_value
            )

    def save(self):
        """
        Writes changes to the file. If this ConfigFile is readonly, do nothing.
        """
        if not self.__readonly__:
            with open(self.filename, 'w', encoding=self.encoding) as file:
                self.parser.write(file)

    def __len__(self):
        """ Number of sections in this config """
        return len(self._sections)

    def __iter__(self):
        """ Iterates the Section objects in this config """
        return iter(self._sections.values())

    def __contains__(self, section: Union['Section', str]):
        """
        Return whether the config contains the given section. Can be either the section
        name, or a Section object. If given a Section object, it must be registered to
        this ConfigFile.

        :param section: Section or section name
        :return: True if this config contains the section
        """
        if isinstance(section, Section):
            return section.cfg is self and section.name in self._sections
        elif isinstance(section, str):
            return section in self._sections
        else:
            return False

    @abstractmethod
    def create(self) -> None:
        """
        Override this method in a child class to define the structure of your config file.
        For each section in your config, simply create a Section object inside ``create()``.
        ::

            def create(self):
                Section(
                    self, 'Section One',
                    ...
                )
                Section(
                    self, 'Section Two',
                    ...
                )
                ...
        """
        raise NotImplementedError('ConfigFile classes need to implement the create() method')

    @property
    def filename(self) -> str:
        """ Name of the file this ConfigFile is attached to, or (unknown). """
        if isinstance(self.file, TextIO):
            return self.file.name
        elif isinstance(self.file, str):
            return self.file
        else:
            return '(unknown)'

    @property
    def section_names(self) -> List[str]:
        """ List of all the section names in this config file. """
        return list(self._sections.keys())

    def __str__(self):
        return "<{} at {}>".format(type(self).__name__, self.filename)


class Section:
    def __init__(self, cfg: ConfigFile, name: str, *options: Option):
        """
        Create a new section and attach it to a ConfigFile. Call this constructor inside
        your ``create()`` method of your ConfigFile.

        :param cfg: ConfigFile to attach this section to
        :param name: Name of the section
        :param options: List of options that this section contains
        """
        self.cfg = cfg
        self.name = name
        self._options: Dict[str, Option] = {}

        self.cfg.register_section(self)
        for option in options:
            self.register_option(option)

    def register_option(self, option: Option):
        """
        Register an option with this section.

        :param option: Option object to register
        :raise DuplicateOptionError: if an option with the same name already
            exists in the section
        """
        if option.name in self:
            raise DuplicateOptionError(self.name, option.name)

        if option.on_register(self):
            self._options[option.name] = option

    def on_register(self, cfg: ConfigFile) -> bool:
        """ Callback function when this section is registered with a ConfigFile """
        self.cfg = cfg
        return True

    def get_ref(self, option_name: str) -> 'Option':
        """
        Get a reference to the Option object itself, rather than the value of
        that option, given an option name.

        :param option_name: Name of the option to get
        :return: Option object
        :raise NoOptionError: if the option name is not found in this section
        """
        if option_name not in self:
            raise NoOptionError(option_name, self.name)
        return self._options[option_name]

    def get(self, option_name: str, default: Any = None) -> Any:
        """
        Get the value of an option if it exists, otherwise return the given default.
        Similar to ``dict.get()``.
        ::

            my_config['MySection'].get('MyOption', -1) # returns the value of MyOption
            my_config['MySection'].get('BogusOption', -1) # returns -1

        :param option_name: Name of the option to get
        :param default: Default value to return if the option doesn't exist. If not
            given, the default will be None.
        :return: Value of the option, or the default
        """
        if option_name in self:
            return self[option_name]
        else:
            return default

    def set(self, option: Union['Option', str], value: Any):
        """
        Set the value of an option in the config.

        The following are all equivalent:
        ::

            my_config.set('Section One', 'SomeOption', 3)
            my_config['Section One'].set('SomeOption', 3)
            my_config['Section One']['SomeOption'] = 3

        :param option: The option, or name of the option to change
        :param value: New value to set the option to
        """
        self.cfg.set(self, option, value)

    def get_raw(self, option_name) -> str:
        """
        Get the 'raw value' of the option. The raw value is the string value
        of the option exactly as written in the config file.

        :param option_name: Name of the option to get
        :return: String value of the option
        """
        return self.get_ref(option_name).raw_value

    def __getitem__(self, option_name: str) -> Any:
        """ Get the value of an option """
        return self.get_ref(option_name).value

    def __setitem__(self, option_name: str, value: Any):
        """ Set the value of an option using assignment operator syntax. """
        self.set(option_name, value)

    def __len__(self):
        """ Number of options in this section """
        return len(self._options)

    def __iter__(self):
        """ Iterates the names of the options in this section """
        return iter(self._options)

    def __contains__(self, option: Union['Option', str]):
        """
        Return whether the section contains the given option. Can be either the option
        name, or an Option object. If given an Option object, it must be registered to
        this section.

        :param option: Option or option name
        :return: True if this section contains the option
        """
        if isinstance(option, Option):
            return option.section is self and option.name in self._options
        elif isinstance(option, str):
            return option in self._options
        else:
            return False

    def keys(self) -> Iterable[str]:
        """ Names of all the options in this section """
        return self._options.keys()

    def values(self) -> Iterable[Any]:
        """ Values of every option in this section """
        for k in self:
            yield self[k]

    def items(self) -> Iterable[Tuple[str, Any]]:
        """ (option name, option value) for every option in this section """
        for k in self:
            yield k, self[k]

    def parse(self, parser: ConfigParser):
        """ Parse all the option values in this section given a ConfigParser """
        for option in self._options.values():
            option.parse(parser, self.name)

    def __str__(self):
        return "<Section '%s'>" % self.name

    def __repr__(self):
        return "Section('%s')" % self.name


T = TypeVar('T')
class Option(ABC, Generic[T]):
    """
    Base class for Options.
    """

    __type__: Type[T] = NotImplemented
    """
    Type to check the option's value against when setting a new value. Set it to
    None to skip type checks. This is used with an ``isinstance()`` call, so you
    should avoid using types from ``typing``.
    """

    __empty__: Tuple[Tuple[str, ...], Optional[T]] = ('', 'none', 'null'), None
    """
    Defines the values that count as empty. The first element should be a tuple
    of all the strings in a config file that should be interpreted as empty (these
    are case insensitive). The second element is the empty value, for example 
    ``None``, ``0``, ``()``, etc. The empty value should be either None or a falsey
    value of whatever type the option value is.

    Because __empty__ is defined at the class level, the same empty value will be 
    returned for every instance of the Option. As such, you should avoid using
    mutable objects as your empty value. Instead, set ``__empty__ = (), None`` and
    implement a falsey check in ``from_str()``.
    """

    def __init__(self, name: str, *, required: bool = True):
        """
        Instantiate an option. You should create your option objects inside
        the constructor of a Section, inside your ``create()`` method.
        ::

            def create(self):
                Section(
                    self, 'My Section',
                    StringOption('Hello'),
                    ...
                )

        :param name: Name of the option
        :param required: Required options need to be present in the config file
            or a NoOptionError will be raised. If an option is not required, it
            can be missing from the config file, in which case its value will be
            the empty value defined by ``__empty__``
        """
        self.name = name
        self.section: Optional[Section] = None
        self.required = required
        self.value: T = self.__empty__[1]
        self.raw_value: Optional[str] = None

    def set(self, value: T):
        """
        Set the value of this option.

        The following are all equivalent:
        ::

            my_config.set('Section One', 'SomeOption', 3)
            my_config['Section One'].set('SomeOption', 3)
            my_config['Section One']['SomeOption'] = 3

        :param value: New value to set the option to
        :raises TypeError: if the type of value does not match the option's __type__
        """
        # Check value type
        if self.__type__ is not None and not isinstance(value, self.__type__):
            raise TypeError("{}/{} expected type '{}', got '{}'".format(
                self.section.name, self.name, self.__type__.__name__, type(value).__name__
            ))

        self.value = value
        self.raw_value = self.to_str(value)

    @abstractmethod
    def from_str(self, string: str) -> T:
        """
        This function takes a string value for this option and should convert it to
        whatever Python type you want. The return value of this function will be used
        when getting a value from the config.

        For example, an IntOption would convert the given string into an int.

        Some options may want to use the Option object itself as the value for more
        complex behavior. In that case, you can simply return ``self``.

        This function is called when the config file is read.

        :param string: Text representation of the option value
        :return: Python representation of the option value
        """
        raise NotImplementedError

    @abstractmethod
    def to_str(self, value: T) -> str:
        """
        This function takes the value returned by ``from_str()`` and should convert it
        to a string. The return value of this function will be put into the config file.

        This function is called when the value of the option changes. The result will be
        put into ``self.raw_value``.

        :param value: Python representation of the option value
        :return: Text representation of the option value
        """
        raise NotImplementedError

    def on_register(self, section: Section) -> bool:
        """
        Callback function for when this option is registered to a Section.

        This function should return True if the option should be added into the section's
        list of options. For most options this is true, however there may be some cases where
        you want to return False. For example, if the option replaces itself with one or more
        other options, as is the case with OptionCollection.

        :param section: The section to register this option to
        :return: Whether the option should be added to the section's option list
        """
        self.section = section
        return True

    def parse(self, parser: ConfigParser, section_name: str):
        """ Read the option value from the config file """
        try:
            self.raw_value = parser.get(section_name, self.name)
        except NoOptionError as e:
            if self.required:
                raise e from None
            else:
                self.value = self.__empty__[1]
                return

        val = self.raw_value.replace('\n', ' ').strip()
        if val.lower() in self.__empty__[0]:
            # Empty value
            self.value = self.__empty__[1]
        else:
            # Set value using from_str
            self.value = self.from_str(val)

    def __str__(self):
        return "<{} '{}/{}'>".format(type(self).__name__, self.section.name, self.name)

    def __repr__(self):
        return "{}('{}')".format(type(self).__name__, self.name)


class UnlinkedOption(Option[T]):
    """
    An UnlinkedOption is an option that exists only in the ConfigFile object in
    Python, and is not actually written in the config file.

    UnlinkedOptions do not need to implement ``to_str`` and ``from_str``. Instead,
    you can set ``self.value`` in the constructor or by overloading ``on_register()``,
    or you can implement ``self.value`` as a property. Examples:
    ::

        class FortyTwoOption(UnlinkedOption):
            def __init__(self, name, *, required=False):
                super().__init__(name, required=required)
                self.value = 42

        # always returns 42
        my_config['MySection']['MyFortyTwo']

        class RandomOption(UnlinkedOption):
            @property
            def value(self):
                return random.random()

        # returns a different random number every time
        my_config['MySection']['MyRandom']
    """

    def to_str(self, value: T) -> str:
        pass

    def from_str(self, string: str) -> T:
        pass

    def parse(self, parser: ConfigParser, section_name: str):
        pass


class SectionCollection:
    """ See ``SectionCollection.__init__()`` """

    def __init__(self, cfg: ConfigFile, *options: Option):
        """
        A collection of sections. A SectionCollection will read all the sections in
        the config file, and create a Section for each one. It takes as parameters all
        the Options you want in each section, the same way you'd make a regular Section.

        SectionCollections are useful for when you want the config file to determine the
        sections in your config rather than the other way around, and those sections all
        share the same structure.

        The SectionCollection will consume all sections that aren't already defined in
        the ConfigFile. So, if you have other sections in the config that you don't want
        included in the SectionCollection, define those first in your ``create()`` method.

        Example:
        ::

            [SecOne]
            Name = Alice

            [SecTwo]
            Name = Bob

            [SecThree]
            Name = Charlie

            def create(self):
                SectionCollection(
                    self,
                    StringOption('Name')
                )

        In this example, the config will have three sections in it: ``SecOne``, ``SecTwo``,
        and ``SecThree``. Each section will have a StringOption called ``Name``.

        :param cfg: ConfigFile to attach all the Sections to
        :param options: Options to create for each Section
        """
        for section_name in cfg.parser:
            if section_name != 'DEFAULT' and section_name not in cfg:
                opt_copies = (copy(option) for option in options)
                Section(cfg, section_name, *opt_copies)
