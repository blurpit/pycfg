from typing import Optional, Tuple

import pytest

from pycfg import ConfigFile, IntOption, Option, Section
from pycfg.options import StrOption

from .conftest import make_file


def test_custom_self_option():
    """ Test that custom options can be made which return references to themselves """
    text = """
    [Sec]
    One = one, 1
    Two = two, 2
    """

    class CustomOption(Option['CustomOption']):
        def on_set(self, value: Tuple[str, int]):
            self.text, self.number = value

        def from_str(self, string: str) -> 'CustomOption':
            text, num = string.split(', ')
            self.text = text
            self.number = int(num)
            return self

        def to_str(self, value) -> str:
            return f'{self.text}, {self.number}'

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                CustomOption('One'),
                CustomOption('Two')
            )

    with make_file(text) as fn:
        t = Test(fn)
        assert t['Sec']['One'].text == 'one'
        assert t['Sec']['One'].number == 1
        assert t['Sec']['Two'].text == 'two'
        assert t['Sec']['Two'].number == 2

        t['Sec']['One'] = ('one hundred', 100)
        assert t['Sec']['One'].text == 'one hundred'
        assert t['Sec']['One'].number == 100
        t.save()
        t.read()
        assert t['Sec']['One'].text == 'one hundred'
        assert t['Sec']['One'].number == 100

def test_empty():
    """ Test setting __empty__ on an option """
    text = """
    [Sec]
    A = 14
    B = None
    C =
    D =
    """

    class IntOrNoneOption(IntOption):
        __empty__ = ('', 'none', 'null'), None
    
    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                IntOrNoneOption('A'),
                IntOrNoneOption('B'),
                IntOrNoneOption('C'),
                IntOption('D')
            )
    
    with make_file(text) as fn:
        t = Test(fn)
        assert t['Sec']['A'] == 14
        assert t['Sec']['B'] is None
        assert t['Sec']['C'] is None
        assert t['Sec']['D'] == 0

def test_empty_invalid():
    """ Test that setting an option to a value not in __empty__ raises an error """
    text = """
    [Sec]
    A = None
    """
    
    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                IntOption('A')
            )
    
    with make_file(text) as fn:
        with pytest.raises(ValueError): # int('None')
            t = Test(fn)

def test_no_empty_str():
    """ Test ``__empty__ = (), None`` makes options required """
    text = """
    [Sec]
    A = hello
    B = None
    C =
    """

    class RequiredStrOption(StrOption):
        __empty__ = (), None
    
    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                RequiredStrOption('A'),
                RequiredStrOption('B'),
                RequiredStrOption('C')
            )
    
    with make_file(text) as fn:
        t = Test(fn)
        assert t['Sec']['A'] == 'hello'
        assert t['Sec']['B'] == 'None'
        assert t['Sec']['C'] == ''

def test_set_type_check():
    text = """
    [Sec]
    A = hello
    """

    class Foo:
        def __init__(self, val: str) -> None:
            self.val = val
        
        def __str__(self) -> str:
            return f"Foo({self.val})"

    class FooOption(Option[Foo]):
        __type__ = Foo

        def to_str(self, value: Foo) -> str:
            return str(value)
        
        def from_str(self, string: str) -> Foo:
            return Foo(string)
    
    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                FooOption('A')
            )
    
    with make_file(text) as fn:
        t = Test(fn)
        foo = t['Sec']['A']
        assert isinstance(foo, Foo)
        assert foo.val == 'hello'

        with pytest.raises(TypeError):
            t['Sec']['A'] = 'goodbye'
        
        t['Sec']['A'] = Foo('goodbye')
