import inspect
import typing

SettingsBase_t = typing.Dict[str, typing.Any]
"""Settings storage type"""

TSettingsOption_t = typing.TypeVar('TSettingsOption_t')
"""Generic single options"""

# ------------------------------------------------------------------------
# Settings
# ------------------------------------------------------------------------
class ISettings(typing.Sized):
    """Interface for ``Settings`` class"""
    _cfg: 'ISettings'

    def __init__(self,cfg:'ISettings'):
        self._cfg = cfg

    def gopt(self, path: str, default: TSettingsOption_t) -> TSettingsOption_t:
        """Get data from settings or set it to default if data not found"""
        return self._cfg.gopt(path,default)

    def sopt(self, path: str, value: TSettingsOption_t) -> TSettingsOption_t:
        """Set settings option to value """
        return self._cfg.sopt(path,value)

    def sub_cfg(self, nm: str) ->'ISettings':
        """Get settings sub-key by full path in form of 'key.key'... """
        return self._cfg.sub_cfg(nm)

    def __len__(self) -> int:
        return self._cfg.__len__()

    def __getitem__(self, key: str):
        return self._cfg.__getitem__(key)

    def __setitem__(self, key: str, value):
        return self._cfg.__setitem__(key,value)

    def __iter__(self):
        return self._cfg.__iter__()

    def __next__(self):
        return self._cfg.__next__()


def newSettings() -> ISettings:
    """Create new settings storage"""
    return Settings()

class Settings(ISettings):
    """
    Dictionary for store, get and sync values accessible by unique name
    Its a dictionary from which you can request value by its full path

    See:
      :class:`gopt`, :class:`sopt()`, :class:`opt()`
    """
    _dict: typing.Optional[SettingsBase_t]
    _selfKey: str

    def __init__(self, cfg: typing.Optional['Settings'] = None, key_name: str = ''):
        ISettings.__init__(self,cfg)
        self._selfKey = key_name
        if cfg:
            self.gopt(key_name, {})
            self._dict = None
        else:
            self._dict = {}

    def __len__(self) -> int:
        if self._cfg:
            return len(self._cfg)
        else:
            return len(self._dict)

    def __getitem__(self, key: str):
        return self.gopt(key, None)

    def __setitem__(self, key: str, value):
        self.sopt(key, value)

    def __iter__(self):
        if self._cfg:
            return self._cfg.__iter__()
        else:
            return self._dict.__iter__()

    def __next__(self):
        if self._cfg:
            return self._cfg.__next__()
        else:
            return self._dict.__next__()

    def sub_cfg(self, path: str) -> ISettings:
        """
        Create new cfg object linked to specified base path in current cfg.
        Changes made in new object will be made in this object
        NOTE: If path will point to value it will be converted to Dict

        Usage:
        .. code-block:: python3
            class A:
                cfg:Settings
                def __init(self,cfg:Settings):
                    self.cfg = cfg.sub_cfg( 'for.class.A' )
            class B:
                cfg:Settings
                def __init(self,cfg:Settings):
                    self.cfg = cfg.sub_cfg( 'for.class.B' )

            cfg = Settings()
            a = A(cfg)
            b = B(cfg)

            # will use global cfg structure: { 'for': { 'class' : { 'A':{}, 'B':{} } }

        :param path: base path-name of sub-branch
        :return: new Settings object
        """
        if not isinstance(path,str): raise KeyError
        if not path or not path.strip(' \r\n\t\b'): return self
        return Settings(self, path)

    def gopt(self, path: str, default: TSettingsOption_t) -> TSettingsOption_t:
        """
        Get option(s) from cfg.
        See :class:opt() for details.
        :param path: option path-name
        :param default: default value
        :return: setting or cfg sub-key branch
        """
        if not path or not path.strip(' \r\n\t\b'): path = ''
        if self._cfg:
            return self._cfg.gopt(f'{self._selfKey}.{path}', default)
        else:
            return self.opt(path, default, write_data=False)

    def sopt(self, path: str, default: TSettingsOption_t) -> TSettingsOption_t:
        """
        Set option(s) to cfg.
        See :class:opt() for details.
        :param path: option path-name
        :param default: default value
        :return: setting value or cfg sub-key branch
        """
        if not path or not path.strip(' \r\n\t\b'): path = ''
        if self._cfg:
            return self._cfg.sopt(f'{self._selfKey}.{path}', default)
        else:
            return self.opt(path, default, write_data=True)

    def key_path(self, path: str) -> (SettingsBase_t, str):
        """
        Get cfg branch for child specified by full path-name
        Will create branch if it not exists
        Any numbers of dots ('.') inside path will be compressed to one, all start and leading
        spaces will be trimmed, and all empty names will be ignored:
            'a..a'='a.a', 'a..'='a', '   a'= 'a',  etc

        Last part of the path is the child name, so:
          path='', return=self,''
          path='a', return self,'a'
          path='a.a', return self['a'], 'a'
          path='a.b.c.d', return self['a']['b']['c'], 'd'

        :param path: full path-name of child delimited by '.'
        :return: (SettingsData_t,str) tuple with branch containing specified child and child name
        """
        if self._cfg:
            return self._cfg.key_path(f'{self._selfKey}.{path}')

        ar = []
        for n in path.split('.'):
            n = n.strip(' \r\n\t\b')
            if len(n) != 0:
                ar.append(n)
        match len(ar):
            case 0:
                return self._dict, ''
            case 1:
                return self._dict, ar[0]

        dest = self._dict
        for i in range(0, len(ar) - 1):
            n = ar[i]
            v = dest.setdefault(n, {})
            if not isinstance(v, typing.Dict):
                dest[n] = {}
                v = dest[n]
            dest = v
        return dest, ar[len(ar) - 1]

    def opt(self, path: str, default: typing.Any, write_data: bool = False) -> typing.Any:
        """
        Get value from cfg by it full name.
        If key not exists, it will be created with value from default.
        Can work with primitive types (int,str,float,complex,tuple,range), classes and dictionaries.
        All other types will be silently ignored.

        If working with class or Dict default its possible to use cfg branch as config with automatic
        sinchronisation:

        .. code-block:: python3
            class A:
                cfg : { 'value':10, 'another':'some text' }

                def __init__(self, settings:Settings ):
                    # the self.cfg object will be replaced with direct link to cfg branch
                    self.cfg = settings.gopt('place.for.A',self)

                def proc(self):
                    self.cfg['addon'] = 156 # Will change key in cfg passed in constructor


        :param path: full value path delimited with '.'
        .. code-block:: python3
            cfg.opt('root',v) # address to branch with name 'root' as in { 'root':XX }
            cfg.opt('',v)     # address to cfg itself
            cfg.opt('a.b',v)  # address to RETURN branch as in { 'a':{ 'b': {RETURN} } }

        :param write_data:
            If is set to True default will be set to cfg or key deleted if default is None
            If is set to False default will be synchronised with cfg.

        :param default: default object: class, Dict or primitive
            1. class instance
                Class object is interpreted as Dictionary where all attributes with names started with
                SINGLE underscore ('_') will be used as keys, and they values as key values.
                Underscores will be removed, pure name will be used as a key. F.i. attribute with
                name "_SomeClassMember" will be used as a key w name "SomeClassMember".

            .. code-block:: python3
                class A:
                    field:int # will not be used since name do not start with '_'
                    __filed:str # will not be used since name do not start with SINGLE '_'
                    _field:float # will be used. Key name will be 'field'

                SYNCHRONISATION (GET):
                All attribute values will be recursively synchronised with cfg:
                - If attribute value is None, no changes will be made
                - If this key not exist in cfg, or its type is different, new key will be added
                  with attribute name and its value
                - If this key exists, attribute value will be set to its value from cfg

                UPDATE (SET):
                - Values for all class attributes will be recursively applied to cfg
                - If some attribute has None value the key with its name will be removed from cfg

            .. code-block:: python3
                class A:
                    _a = 12
                    notIn1 = ""
                    _cfg = {'a': 10, 'b': {'a': None, 'b': {}, 'c': 18}}

                    def __init__(self):
                        self._d = 15
                        self._eqAAAqw = 'asdasd'

                cfg = Settings()
                a = A()

                #sync cfg settings with class
                cfg.gopt('',a)
                print(cfg,'==', a._cfg['b']['c'])
                # {'a': 12, 'cfg': {'a': 10, 'b': {'b': {}, 'c': 18}}, 'd': 15, 'eqAAAqw': 'asdasd'} == 18

                # change in cfg not affect class
                cfg['cfg']['b']['c'] = 138
                print(cfg,'==', a._cfg['b']['c'])
                # {'a': 12, 'cfg': {'a': 10, 'b': {'b': {}, 'c': 138}}, 'd': 15, 'eqAAAqw': 'asdasd'} == 18

                # sync class with cfg, read changed value
                cfg.gopt('',a)
                print( cfg,'==', a._cfg['b']['c'])
                # {'a': 12, 'cfg': {'a': 10, 'b': {'b': {}, 'c': 138}}, 'd': 15, 'eqAAAqw': 'asdasd'} == 138

                # mark key to delete from cfg
                a._cfg = None
                cfg.sopt('',a)
                print( cfg,'==',a._cfg )
                # {'a': 12, 'd': 15, 'eqAAAqw': 'asdasd'} == None

            2. Dictionary
                All COMPATIBLE (primitive or Dict) key/value pair from dictionary will be used.

                SYNCHRONISATION (GET):
                All compatible pairs will be recursively synchronised with cfg:
                - If pair value is None, no changes will be made
                - If this key not exist in cfg, or its type is different, new key will be added
                  with key name and its value
                - If this key exists, value IN default Dict will be set to value from cfg

                UPDATE (SET):
                - Values for all compatible key/value pairs will be recursively applied to cfg
                - If some compatible key has None value the key with its name will be removed from cfg

            .. code-block:: python3
                cfg = Settings()

                # Config will synchronized with 'l'.
                # New value added to config, existing copied to 'l'
                # None values from 'l' are ignored.
                l = {'a': 10, 'b': {'a': None, 'b': {'c':15}}}
                v = cfg.gopt('',l)
                assert len(cfg) == 2 and cfg['b']['b']['c'] == 15 and v == cfg

                # get from cfg
                l = {}
                v = cfg.gopt('',l)
                assert len(l) == 2 and l['b']['b']['c'] == 15 and v == cfg

                #remove item, get BASE as result
                l['b']['b'] = None
                l1 = cfg.sopt('', l)
                assert len(cfg['b']) == 0 and l1 == cfg

                # change value by link
                l1['a'] = 12
                assert cfg['a'] == 12
                cfg['a'] = 16
                assert l1['a'] == 16

            3. Primitive value
                Last path name will be used as key name and default value as its value.
                NOTE: On any value access synchronise it type with default!
                GET:
                 Get value from cfg if key exist or return default.
                SET:
                 Change value in cfg.

            .. code-block:: python3
                cfg = Settings()
                # put some data to cfg
                cfg.gopt('',{'a': 12})

                v = cfg.gopt('',10)  # getting value without name just get default
                assert isinstance(v,int) and v == 10

                v = cfg.sopt('',10) # setting value without name just get default
                assert isinstance(v,int) and v == 10 and len(cfg) == 1

                v = cfg.sopt('',None) # Setting None without name do nothing
                assert v is None and len(cfg) == 1

                v = cfg.sopt('a',None) # setting value to None deletes it
                assert isinstance(v,int) and v == 12 and len(cfg) == 0

                v = cfg.sopt('a',None) # setting nont to non existent value do nothing
                assert v is None and len(cfg) == 0

                # put bigger data in cfg
                cfg.gopt('',{'a': 12, 'cfg': {'a': 'text'}, 'd': 15})

                v = cfg.gopt('a',120) # return existing value
                assert isinstance(v,int) and v == 12

                v = cfg.sopt('a',210) # change cfg value
                assert isinstance(v,int) and v == 210

                v = cfg.gopt('a','some text') # change type of existing item to the type of default
                assert isinstance(v,str) and v == 'some text'

                v = cfg.gopt('cfg.a','another') # nested value
                assert isinstance(v,str) and v == 'text'

                v = cfg.gopt('cfg.a.b.c','another') # create new path in cfg for value
                assert isinstance(v,str) and v == 'another' and cfg['cfg']['a']['b']['c'] == 'another'

                v = cfg.gopt('a.a',164)  # change type of existing key and ceate new one inside
                assert isinstance(v,int) and v == 164 and cfg['a']['a'] == 164

                v = cfg.sopt('cfg',None)  # remove key, return its value before remove
                assert isinstance(v,typing.Dict) and v['a']['b']['c'] == 'another' and 'cfg' not in cfg

        :return: value from cfg
            1. Class, Dict - cfg branch pointing to class/Dict reflection in cfg
            2. primitive - single value
        """

        def _is_primitive(v):
            return v is None or isinstance(v, (int, str, float, complex, tuple, range))

        def _is_class(v):
            return inspect.isclass(type(v)) and hasattr(v, '__dict__')

        def _is_compatible(v):
            return v is None or _is_primitive(v) or isinstance(v, typing.Dict)

        def _is_valid_name(nm: str):
            return len(nm) > 1 and nm[0] == '_' and nm[1].isalpha()

        class __NoValue:
            pass

        _NoValue = __NoValue()

        def _getOrUpdate(key, nm, val, is_write_data):
            if val is None:
                if key is not None and nm in key:
                    if is_write_data:
                        return key.pop(nm)
                    return key[nm]
                return None

            vv = key.setdefault(nm, val)
            if type(vv) != type(val) or (_is_primitive(vv) and is_write_data):
                if val is not None: key[nm] = val
                return key[nm]
            return vv

        def _synchronise(key, key_name, value):
            if _is_primitive(value):
                return value if not key_name else _getOrUpdate(key, key_name, value, write_data)
            elif isinstance(value, typing.Dict):
                key = key if not key_name else _getOrUpdate(key, key_name, {}, True)

                # get new values from dict, sync privitives
                for n in value:
                    if not isinstance(n, str): continue
                    v = value[n]
                    if v is None:
                        if write_data and n in key:
                            key.pop(n)
                        continue
                    if not _is_compatible(v): continue
                    v = _synchronise(key, n, v)
                    if v is not None and v is not __NoValue: value[n] = v
                # add keys from cfg not existing in dict
                if not write_data:
                    for n in key:
                        if n not in value:
                            _synchronise(value, n, key[n])

            elif _is_class(value):
                key = key if not key_name else _getOrUpdate(key, key_name, {}, True)
                # attribs from dir() and vars()
                for n in dir(value) + list(vars(value)):
                    if not _is_valid_name(n): continue
                    v = getattr(value, n)
                    cfg_name = n.removeprefix('_')
                    if v is None:
                        if write_data and cfg_name in key:
                            key.pop(cfg_name)
                        continue
                    if not _is_compatible(v): continue
                    v = _synchronise(key, cfg_name, v)
                    if v is not __NoValue: setattr(value, n, v)
            return __NoValue

        key, lastname = self.key_path(path)
        v = _synchronise(key, lastname, default)
        if v is not __NoValue:
            return v
        if lastname in key:
            return key[lastname]
        return key


# ------------------------------------------------------------------
# SettingsStorage
# ------------------------------------------------------------------
class SettingsIStorage:
    """Interface for load\save storage"""
    def load(self, settings: ISettings):
        pass

    def save(self, settings: ISettings):
        pass

# ------------------------------------------------------------------------
# TESTS
# ------------------------------------------------------------------------
# noinspection PyProtectedMember
def pCLASS(config:ISettings):
    class A:
        _a = 12
        notIn1 = ""
        _cfg = {'a': 10, 'b': {'a': None, 'b': {}, 'c': 18}}

        def __init__(self):
            self._d = 15
            self._eqAAAqw = 'asdasd'

    a: A = A()

    # cfg has data from class
    config.gopt('', a)
    assert len(config) == 4 and a._cfg['b']['c'] == 18

    # fields not linked
    config['cfg']['b']['c'] = 138
    assert config['cfg']['b']['c'] == 138 and a._cfg['b']['c'] == 18

    # refresh data in class
    config.gopt('', a)
    assert a._cfg['b']['c'] == 138

    # delete cfg key
    a._cfg = None
    v = config.sopt('', a)

    assert len(config) == 3 and 'cfg' not in config and a._cfg is None and v == config._dict

    # new empty key in cfg
    a._cfg = {}
    config.gopt('', a)
    assert len(config) == 4 and 'cfg' in config and len(config['cfg']) == 0

    print('Setting CLASS test passed')


# noinspection PyUnresolvedReferences
def pDICT(cfg:ISettings):

    # fill data
    l = {'a': 10, 'b': {'a': None, 'b': {'c': 15}}}
    v = cfg.gopt('', l)
    assert len(cfg) == 2 and cfg['b']['b']['c'] == 15 and v == cfg._dict
    assert cfg['b.b.c'] == 15

    # get from cfg
    l = {}
    v = cfg.gopt('  ', l)
    assert len(l) == 2 and l['b']['b']['c'] == 15 and v == cfg._dict

    # remove item, get BASE as result
    l['b']['b'] = None
    l1 = cfg.sopt('', l)
    assert len(cfg['b']) == 0 and l1 == cfg._dict

    # change value by link
    l1['a'] = 12
    assert cfg['a'] == 12
    cfg['a'] = 16
    assert l1['a'] == 16
    print('Setting DICT test passed')

def pSINGLE(cfg:ISettings):
    cfg.gopt('', {'a': 12})

    v = cfg.gopt('', 10)
    assert isinstance(v, int) and v == 10

    v = cfg.sopt('', 10)
    assert isinstance(v, int) and v == 10 and len(cfg) == 1

    v = cfg.sopt('', None)
    assert v is None and len(cfg) == 1

    v = cfg.sopt('a', None)
    assert isinstance(v, int) and v == 12 and len(cfg) == 0

    v = cfg.sopt('a', None)
    assert v is None and len(cfg) == 0

    cfg.gopt('', {'a': 12, 'cfg': {'a': 'text'}, 'd': 15})

    v = cfg.gopt('a', 120)
    assert isinstance(v, int) and v == 12

    v = cfg.sopt('a', 210)
    assert isinstance(v, int) and v == 210

    v = cfg.gopt('a', 'some text')
    assert isinstance(v, str) and v == 'some text'

    v = cfg.gopt('  cfg.  a', 'another')
    assert isinstance(v, str) and v == 'text'

    v = cfg.gopt('...cfg  ...a..  b  .  c  ', 'another')
    assert isinstance(v, str) and v == 'another' and cfg['cfg']['a']['b']['c'] == 'another'

    v = cfg.gopt('a.a', 164)
    assert isinstance(v, int) and v == 164 and cfg['a']['a'] == 164

    v = cfg.sopt('cfg', None)

    assert isinstance(v, typing.Dict) and v['a']['b']['c'] == 'another' and 'cfg' not in cfg

    print('Setting SINGLE test passed')


def pLINK(cfg:ISettings):

    cfg.gopt('', {
        'a': 10,
        'b': {
            'a': None,
            'b': {'c': 15}
        },
        'c': {
            'a': 'text',
            'b': {'c': 25}
        },
        'd': {
            'a': 16,
            'b': {'c': 38}
        }
    })

    cfg.sub_cfg('b').sopt('b.c', 18)
    cfg.sub_cfg('').sopt('c.b.c', 13)
    assert cfg['b']['b']['c'] == 18 and cfg['c']['b']['c'] == 13
    assert cfg['b.b.c'] == 18 and cfg['c.b.c'] == 13

    l = cfg.sub_cfg('b.none')
    l.gopt('a', 12)
    assert cfg['b']['none']['a'] == 12

    print('Setting LINK test passed')


def _test_Settings():
    pCLASS(newSettings())
    pDICT(newSettings())
    pSINGLE(newSettings())
    pLINK(newSettings())

# _test_Settings()
