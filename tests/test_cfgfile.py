from configparser import NoOptionError, NoSectionError

import pytest

from pycfg import ConfigFile, Section, StrOption
from .conftest import make_file


def test_read_file():
    """ Reading a cfg file works """
    text = """
    [Sec]
    Hello = World
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                StrOption('Hello')
            )

    with make_file(text) as fn:
        t = Test(fn)
        assert t['Sec']['Hello'] == 'World'

def test_read_file_deferred():
    """ Reading a cfg file in read() instead of the constructor works """
    text = """
    [Sec]
    Hello = World
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                StrOption('Hello')
            )

    with make_file(text) as fn:
        t = Test()
        t.read(fn)
        assert t['Sec']['Hello'] == 'World'

def test_no_file():
    """ Raises a FileNotFoundError if no file was given """
    class Test(ConfigFile):
        def create(self):
            pass

    t = Test()
    with pytest.raises(FileNotFoundError):
        t.read()

def test_no_section():
    """ Raises a NoSectionError when accessing a section that doesnt exist """
    text = """
    [Sec]
    Hello = World
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                StrOption('Hello')
            )

    with make_file(text) as fn:
        t = Test(fn)
        with pytest.raises(NoSectionError):
            print(t['Foo']['Hello'])

def test_no_option():
    """ Raises a NoOptionError when accessing an option that doesnt exist """
    text = """
    [Sec]
    Hello = World
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                StrOption('Hello')
            )

    with make_file(text) as fn:
        t = Test(fn)
        with pytest.raises(NoOptionError):
            print(t['Sec']['Foo'])

def test_missing_section():
    """ Raises a NoSectionError when reading a cfg file that doesnt have a section """
    text = """
    [Oh no]
    Hello = World
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                StrOption('Hello')
            )

    with make_file(text) as fn:
        with pytest.raises(NoSectionError, match="No section: 'Sec'"):
            Test(fn)

def test_missing_option():
    """ Raises a NoOptionError when reading a file that doesnt have a required option """
    text = """
    [Sec]
    OhNo = World
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                StrOption('Hello')
            )

    with make_file(text) as fn:
        with pytest.raises(NoOptionError, match="No option 'Hello' in section: 'Sec'"):
            Test(fn)

def test_set_option():
    """ Setting options work with all 3 methods """
    text = """
    [Sec]
    Hello = World
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                StrOption('Hello')
            )

    with make_file(text) as fn:
        t = Test(fn)

        t['Sec']['Hello'] = 'One'
        assert t['Sec']['Hello'] == 'One'

        t['Sec'].set('Hello', 'Two')
        assert t['Sec']['Hello'] == 'Two'

        t.set('Sec', 'Hello', 'Three')
        assert t['Sec']['Hello'] == 'Three'

def test_save_file():
    """ Using save() writes to the file """
    text = """
    [Sec]
    Hello = World
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                StrOption('Hello')
            )

    with make_file(text) as fn:
        t = Test(fn)

        # read again without saving
        t['Sec']['Hello'] = 'Foo'
        t.read()
        assert t['Sec']['Hello'] == 'World'

        # set, save, then read again
        t['Sec']['Hello'] = 'Bar'
        t.save()
        t.read()
        assert t['Sec']['Hello'] == 'Bar'

        # make a change and read again without saving
        # to make sure saving & rereading works
        t['Sec']['Hello'] = 'Baz'
        t.read() # undo change
        assert t['Sec']['Hello'] == 'Bar'

def test_readonly():
    """ Raises a PermissionError if an option is set on a readonly config """
    text = """
    [Sec]
    Hello = World
    """

    class Test(ConfigFile):
        __readonly__ = True
        def create(self):
            Section(
                self, 'Sec',
                StrOption('Hello')
            )

    with make_file(text) as fn:
        t = Test(fn)
        with pytest.raises(PermissionError):
            t['Sec']['Hello'] = 'Goodbye'

def test_optional_option():
    """ Options with required=False should have an empty value if the
        option is not present in the file """
    text = """
    [Sec]
    Hello = World
    """

    class Test(ConfigFile):
        __readonly__ = True

        def create(self):
            Section(
                self, 'Sec',
                StrOption('Hello'),
                StrOption('Foo', required=False)
            )

    with make_file(text) as fn:
        t = Test(fn)
        assert t['Sec']['Foo'] is None

