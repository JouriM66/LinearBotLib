import asyncio
import enum
import inspect
import logging
import typing
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup

# ------------------------------------------------------------------------
class NullLogger(logging.Logger):
    """ Logger replacement with cut actual log function for fast LOG-noLOG
        switching in single code scope
        Usage:
            # Just change single line in 'log' definition to switch logging
            class A:
                log = NullLogger() #logging.getLogger()
                ...
                def proc(self):
                    self.log.warning( 'some text' )
    """

    def __init__(self):
        super().__init__(name='')

    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False, stacklevel=1):
        pass


# ------------------------------------------------------------------------
TDataType_t = typing.TypeVar('TDataType_t')


class DataAccess(typing.Generic[TDataType_t]):
    """ Holder for data with concurent access to it: many_writers->single_reader
        Used to process telegram messages received from many tasks by single dispatcher in separate task
        Usage:
          callback(data):
            #will block until dispatcher get data
            await data.process(data) # will return ONLY after dispatcher process message

          dispatcher:
            d = await data.get() # will block until any data received
            ...
    """
    log = NullLogger()  # logging.getLogger()
    lock = asyncio.Lock()
    hasData = asyncio.Event()
    doneData = asyncio.Event()
    data: typing.Optional[TDataType_t] = None

    async def process(self, data: TDataType_t):
        self.log.warning('DAp: w lock')
        async with self.lock:
            self.data = data

            self.log.warning('DAp: s has')
            self.hasData.set()

            self.log.warning('DAp: w done')
            await self.doneData.wait()
            self.doneData.clear()

            self.log.warning('DAp: complete')

    async def get(self) -> TDataType_t:
        self.log.warning('DAg: w has')
        await self.hasData.wait()

        d = self.data
        self.data = None
        self.hasData.clear()

        self.log.warning('DAg: s done')
        self.doneData.set()
        return d


Changeable_t = typing.TypeVar('Changeable_t')


class Changeable(typing.Generic[Changeable_t]):
    _value: Changeable_t
    _old: Changeable_t
    changed : bool

    def __init__(self, val: Changeable_t) -> None:
        super().__init__()
        self._value = val
        self._old = val

    @property
    def changed(self):
        return self._value != self._old

    @property
    def old(self) -> Changeable_t: return self._old

    @property
    def value(self) -> Changeable_t: return self._value

    @value.setter
    def value(self, v: typing.Optional[Changeable_t]):
        if self._value != v:
            self._old = self._value
            self._value = v

    def unchange(self):
        self._old = self._value

class Applicable:
    """ Helper for set class attributes from function parameters
        The list of attributes need to be set must be passed to constructor.

        Will work ONLY with named parameters.

        Will set values only for attributes listed on initialization and
        from only non-None parameters.

        Usage::

        class A(Applicable):
            # some class attributes
            a:int
            b:str

            def __init__(..):
                # tell Applicable which attributes need to be taken from args
                super().__init__(self,['a','b'])
                self.apply( locals() ) # will set class attributes from parameters
    """
    _apply_props: typing.List[str]

    def __init__(self, props: typing.List[str]) -> None:
        super().__init__()
        self._apply_props = props

    def apply(self, vals_list) -> None:
        """ Set class attributes from values list.
        ``locals()`` can be used as values list.
        Will sett only values which is non-None in the list and do not touch others.

        :param vals_list: values list
        """
        for k in self._apply_props:
            if k not in vals_list: continue
            val = vals_list[k]
            if val is None: continue

            attr = getattr(self, k)
            if isinstance(attr, Changeable):
                attr.value = val
            else:
                setattr(self, k, val)


# ------------------------------------------------------------------------
def isPrimitive(v) -> bool:
    """Check if specified value is primitive type"""
    return v is None or isinstance(v, (int, str, float, complex, tuple, range))


def PProps(self, level=0):
    for v in self.__dir__():
        if v.startswith('__'): continue
        try:
            data = getattr(self, v)
            if isinstance(data, str): data = f'"{data}"'
        except Exception as ex:
            data = f' Exception: "{ex.args[0]}"'
        else:
            if isinstance(data, typing.Callable): continue
        print('  ' * level + ' = '.join([v, str(data)]))
        if isinstance(data, enum.Enum): continue
        if hasattr(data, '__dict__'):
            PProps(data, level + 1)

def readAPIToken(fnm: str) -> str:
    """Read bot user API token from specified file or raise ``ValueError``. The key must be in separate line
    started with "key=" text.

    :param fnm: file name
    :return: str,
    """
    f = open(fnm, 'rt')
    if not f: raise ValueError('Cant open API file')

    for s in f:
        s = s.strip(' \t\r\n')
        if s.startswith('#'):
            pass
        if s.startswith('key='):
            s = s[4:].strip(' \t\r\n')
            f.close()
            return s
    f.close()
    raise ValueError('Cant find API key in file')

def filterArgs(dictionary:typing.Dict, noParams:typing.Optional[typing.List[str]] = None) ->typing.Dict:
    """
    Remove 'self' named parameter from dictionary + all parameters listed in
    optional `noParams`.

    Usage::

    def F( ... ): # with lot of named parameters
        pass

    def P( ... ): # with lot of named parameters
        F( **filterArgs(locals()) )   # pass filtered out named parameters to F()
    ``

    :param dictionary:
    :param noParams: If is set contains additional keys need to be removed
    :return: filtered dictionary
    """
    if noParams is None: noParams = []
    return {k:v for k,v in dictionary.items() if k != 'self' and k not in noParams and not k.startswith('__')}

# ------------------------------------------------------------------------
PROC_LEVEL = 0

class _PEnter:

    def __init__(self,plog,h):
        self.plog = plog
        self.h = h

    def __enter__(self):
        global PROC_LEVEL
        if self.plog:
            self.plog('  ' * PROC_LEVEL + self.h)
        PROC_LEVEL += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        global PROC_LEVEL
        PROC_LEVEL -= 1
        if self.plog:
            self.plog('  ' * PROC_LEVEL + '}')


def PROC_(plog, *args):
    if plog is None: return _PEnter(plog,'')
    v = inspect.stack()
    if isinstance(v,typing.List):
        v = v[2]
        v = f'{v.filename}[{v.lineno}]::{v.function}'
    else:
        v = '<unk>'
    return _PEnter(plog, v + '( ' + ', '.join([str(a) for a in args]) + ' ) {')

def LOG_(plog, *args):
    if plog is None: return
    global PROC_LEVEL
    plog('  ' * PROC_LEVEL + ' '.join([str(a) for a in args]))
