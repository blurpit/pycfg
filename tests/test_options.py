from datetime import date, datetime
from decimal import Decimal
from random import random
from typing import Any, Dict

import pytest

from pycfg import BoolOption, ConfigFile, DateOption, DateTimeOption, DecimalOption, \
    DerivedOption, DictOption, FloatOption, IntOption, ListOption, OptionCollection, PickleOption, \
    RangeOption, Section, SectionCollection, StrOption

from .conftest import make_file


def test_simple_types():
    """ Test that options convert strings into python types """
    text = """
    [Sec]
    String = Hello
    Integer = 17
    Float = 3.14159
    Decimal = 3.14159
    Boolean = Yes
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                StrOption('String'),
                IntOption('Integer'),
                FloatOption('Float'),
                DecimalOption('Decimal'),
                BoolOption('Boolean'),
            )

    with make_file(text) as fn:
        t = Test(fn)
        assert t['Sec']['String'] == 'Hello'
        assert t['Sec']['Integer'] == 17
        assert t['Sec']['Float'] == 3.14159
        assert t['Sec']['Decimal'] == Decimal('3.14159')
        assert t['Sec']['Boolean'] is True

def test_set_simple_types():
    """ Test that options convert python types into strings """
    text = """
    [Sec]
    String = Hello
    Integer = 17
    Float = 3.14159
    Decimal = 3.14159
    Boolean = Yes
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                StrOption('String'),
                IntOption('Integer'),
                FloatOption('Float'),
                DecimalOption('Decimal'),
                BoolOption('Boolean'),
            )

    with make_file(text) as fn:
        t = Test(fn)
        t['Sec']['String'] = 'Goodbye'
        t['Sec']['Integer'] = 71
        t['Sec']['Float'] = 2.71828
        t['Sec']['Decimal'] = Decimal('2.71828')
        t['Sec']['Boolean'] = False

        # Save, read, and check values again
        t.save()
        t.read()
        assert t['Sec']['String'] == 'Goodbye'
        assert t['Sec']['Integer'] == 71
        assert t['Sec']['Float'] == 2.71828
        assert t['Sec']['Decimal'] == Decimal('2.71828')
        assert t['Sec']['Boolean'] is False

def test_set_simple_types_wrong():
    """ Test that using the wrong type when setting an option raises a TypeError """
    text = """
    [Sec]
    String = Hello
    Integer = 17
    Float = 3.14159
    Decimal = 3.14159
    Boolean = Yes
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                StrOption('String'),
                IntOption('Integer'),
                FloatOption('Float'),
                DecimalOption('Decimal'),
                BoolOption('Boolean'),
            )

    with make_file(text) as fn:
        t = Test(fn)
        with pytest.raises(TypeError):
            t['Sec']['String'] = 53
        with pytest.raises(TypeError):
            t['Sec']['Integer'] = 'hi'
        with pytest.raises(TypeError):
            t['Sec']['Float'] = [3.14]
        with pytest.raises(TypeError):
            t['Sec']['Decimal'] = 17
        with pytest.raises(TypeError):
            t['Sec']['Boolean'] = 'False'

def test_list_option():
    """ Test that list options convert a string into a list of values, and convert
        each item into the correct type """
    text = """
    [Sec]
    Strs = abc, def, ghi, jkl
    Ints = 3, 5, 7, -2, 128
    Semicoloned = lorem;ipsum;dolor;sit;amet
    Empty =
    None = None
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                ListOption('Strs'),
                ListOption('Ints', int),
                ListOption('Semicoloned', delimiter=';'),
                ListOption('Empty'),
                ListOption('None'),
            )

    with make_file(text) as fn:
        t = Test(fn)
        assert t['Sec']['Strs'] == ['abc', 'def', 'ghi', 'jkl']
        assert t['Sec']['Ints'] == [3, 5, 7, -2, 128]
        assert t['Sec']['Semicoloned'] == ['lorem', 'ipsum', 'dolor', 'sit', 'amet']
        assert t['Sec']['Empty'] == []
        assert t['Sec']['None'] == ['None'] # listoption should not have None

        # test setting
        t['Sec']['Strs'] = ['mno', 'pqr']
        t['Sec']['Ints'] = [512, 1024]
        t['Sec']['None'] = []
        t.save()
        t.read()
        assert t['Sec']['Strs'] == ['mno', 'pqr']
        assert t['Sec']['Ints'] == [512, 1024]
        assert t['Sec']['None'] == []

def test_range_option():
    """ Test that range options convert a string into a range() """
    text = """
    [Sec]
    One = 5-10
    Two = -5 to 6
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                RangeOption('One'),
                RangeOption('Two', ' to ')
            )

    with make_file(text) as fn:
        t = Test(fn)
        assert t['Sec']['One'] == range(5, 10)
        assert t['Sec']['Two'] == range(-5, 6)
        assert 7 in t['Sec']['One']
        assert 3 not in t['Sec']['One']

        # test setting
        t['Sec']['One'] = range(10, 15)
        t['Sec']['Two'] = range(-10, -5)
        t.save()
        t.read()
        assert t['Sec']['One'] == range(10, 15)
        assert t['Sec']['Two'] == range(-10, -5)


def test_date_option():
    """ Test that Date/DateTime options read str formatted dates & times and convert
        them into datetime objects """
    text = """
    [Sec]
    Christmas = 2024-12-26
    NewYear = 2025-01-01T00:00:00
    Timestamp = 2024-11-16T14:43:08.828316
    AmericanDate = 7/4/24
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                DateOption('Christmas'),
                DateTimeOption('NewYear'),
                DateTimeOption('Timestamp'),
                DateOption('AmericanDate', '%m/%d/%y'),
            )

    with make_file(text) as fn:
        t = Test(fn)
        assert t['Sec']['Christmas'] == date(2024, 12, 26)
        assert t['Sec']['NewYear'] == datetime(2025, 1, 1)
        assert t['Sec']['Timestamp'] == datetime(2024, 11, 16, 14, 43, 8, 828316)
        assert t['Sec']['AmericanDate'] == date(2024, 7, 4)

        # test setting
        t['Sec']['Christmas'] = date(2025, 12, 26)
        t['Sec']['NewYear'] = datetime(2026, 1, 1)
        t.save()
        t.read()
        assert t['Sec']['Christmas'] == date(2025, 12, 26)
        assert t['Sec']['NewYear'] == datetime(2026, 1, 1)

def test_pickle_option():
    """ Test that PickleOption takes any pickleable object and converts it to base64 text
        in the config file """
    text = """
    [Sec]
    Pickler =
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                PickleOption('Pickler')
            )

    pickle: Any = [{'cucumber', 'zucchini'}, {'dill': 2.99, 'oregano': 4.95, 'parsely': 3}]

    with make_file(text) as fn:
        t = Test(fn)
        assert t['Sec']['Pickler'] is None

        # test setting pickle
        t['Sec']['Pickler'] = pickle
        t.save()
        t.read()
        assert t['Sec']['Pickler'] == pickle

        # test setting back to none
        t['Sec']['Pickler'] = None
        t.save()
        t.read()
        assert t['Sec']['Pickler'] is None

def test_dict_option():
    """ Test that DictOptions take any json serializable object (dicts) and convert it to
        json text in the config file """
    text = """
    [Sec]
    Json = {}
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                DictOption('Json')
            )

    json: Dict[str, Any] = {
        'apple': ['fuji', 'granny smith'],
        'banana': 127,
        'grape': {'green': 20, 'red': 'yes'}
    }

    with make_file(text) as fn:
        t = Test(fn)
        assert t['Sec']['Json'] == {}

        # test setting json
        t['Sec']['Json'] = json
        t.save()
        t.read()
        assert t['Sec']['Json'] == json

        # test setting to None
        with pytest.raises(TypeError):
            t['Sec']['Json'] = None

def test_derived_option():
    """ Test that DerivedOptions run a function that calculates a value based on the
        values of other options """
    text = """
    [Sec]
    A = 3
    B = 12
    
    [Sec2]
    C = -1
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                IntOption('A'),
                IntOption('B'),
                DerivedOption(
                    'APlusB',
                    lambda a, b: a + b,
                    ['A', 'B']
                ),
                DerivedOption(
                    'ATimesC',
                    lambda a, c: a * c,
                    ['A', ('Sec2', 'C')]
                ),
                DerivedOption(
                    'ATimesRand',
                    lambda a: a * random(),
                    ['A']
                ),
                DerivedOption(
                    'Hello',
                    lambda: 'hello!',
                    []
                )
            )
            Section(
                self, 'Sec2',
                IntOption('C')
            )

    with make_file(text) as fn:
        t = Test(fn)

        # test a + b
        assert t['Sec']['APlusB'] == 15
        # test a * c
        assert t['Sec']['ATimesC'] == -3
        # test that the function runs every time it's called
        assert t['Sec']['ATimesRand'] != t['Sec']['ATimesRand']
        # test derived option with no references
        assert t['Sec']['Hello'] == 'hello!'

        # test setting derived option
        with pytest.raises(ValueError):
            t['Sec']['Hello'] = 'goodbye!'

def test_option_collection():
    """ Test that OptionCollections read and register all options in a section """
    text = """
    [Sec]
    A = 1
    B = 2
    SomethingElse = hello
    C = 3
    D = 4
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Sec',
                StrOption('SomethingElse'),
                OptionCollection(IntOption)
            )

    with make_file(text) as fn:
        t = Test(fn)
        assert t['Sec']['A'] == 1
        assert t['Sec']['B'] == 2
        assert t['Sec']['C'] == 3
        assert t['Sec']['D'] == 4
        assert t['Sec']['SomethingElse'] == 'hello'

        # test setting
        t['Sec']['A'] = 100
        t.save()
        t.read()
        assert t['Sec']['A'] == 100
        assert t['Sec']['B'] == 2
        assert t['Sec']['C'] == 3
        assert t['Sec']['D'] == 4
        assert t['Sec']['SomethingElse'] == 'hello'

def test_section_collection():
    """ Test that SectionCollections read and register all sections in the config """
    text = """
    [Sec1]
    A = 1
    B = one
    
    [Sec2]
    A = 2
    B = two
    
    [Unrelated]
    Test = hello world!
    
    [Sec3]
    A = 3
    B = three
    """

    class Test(ConfigFile):
        def create(self):
            Section(
                self, 'Unrelated',
                StrOption('Test')
            )
            SectionCollection(
                self,
                IntOption('A'),
                StrOption('B')
            )

    with make_file(text) as fn:
        t = Test(fn)
        assert t['Unrelated']['Test'] == 'hello world!'
        assert t['Sec1']['A'] == 1
        assert t['Sec1']['B'] == 'one'
        assert t['Sec2']['A'] == 2
        assert t['Sec2']['B'] == 'two'
        assert t['Sec3']['A'] == 3
        assert t['Sec3']['B'] == 'three'

        # test setting
        t['Sec2']['A'] = 200
        t['Sec2']['B'] = 'two hundred'
        t.save()
        t.read()
        assert t['Unrelated']['Test'] == 'hello world!'
        assert t['Sec1']['A'] == 1
        assert t['Sec1']['B'] == 'one'
        assert t['Sec2']['A'] == 200
        assert t['Sec2']['B'] == 'two hundred'
        assert t['Sec3']['A'] == 3
        assert t['Sec3']['B'] == 'three'
