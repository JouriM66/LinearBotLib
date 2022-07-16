from bot_types import *
from utils import *

class KeyboardType(enum.Enum):
    NONE = None
    KEYBOARD = 1
    INLINE = 2
    REMOVE = 3


class BotKeyboard(Applicable):
    """Class to hold message keyboard data."""
    _keyboard_type: Changeable[KeyboardType]
    _placeholder: Changeable[str]
    _buttons: Changeable[typing.Optional[BotUserKeyboard_t]]
    _markup: typing.Optional[BotMarkup_t] = None

    def __init__(self,
                 keyboard_type: KeyboardType = None,
                 buttons: BotUserKeyboard_t = None,
                 placeholder: str = None) -> None:
        """Create new keyboard object

        :param keyboard_type: type of keyboard
        :param buttons: buttons set
        :param placeholder: placeholder text for KEYBOARD type
        """
        Applicable.__init__(self, ['keyboard_type', 'buttons', 'placeholder'])
        self._placeholder = Changeable[str]('')
        self._keyboard_type = Changeable[KeyboardType](KeyboardType.NONE)
        self._buttons = Changeable[BotUserKeyboard_t](None)
        self.apply(locals())
        if buttons and keyboard_type == KeyboardType.NONE:
            self.keyboard_type = KeyboardType.INLINE
        self._dummy = 1

    @staticmethod
    def _checkStr(v):
        v = str(v).strip() # may raise error is inconvertible to str
        if len(v) == 0: raise ValueError('Button text can not be empty')

    def _checkItem(self, v, kbd: KeyboardType) -> KeyboardType:
        if isinstance(v, types.InlineKeyboardButton):
            if kbd == KeyboardType.KEYBOARD: raise ValueError('Keyboard cant use Inline keys!')
            return KeyboardType.INLINE
        if isinstance(v, types.KeyboardButton):
            if kbd == KeyboardType.INLINE: raise ValueError('Inline Keyboard cant use Keyboard keys!')
            return KeyboardType.KEYBOARD
        if isinstance(v, typing.Tuple):
            if len(v) == 0: raise ValueError('Key tuple must have at least one element')
            self._checkStr(v[0])
            return kbd
        self._checkStr(v)
        return kbd

    def _check(self):
        if self.keyboard_type == KeyboardType.INLINE or self.keyboard_type == KeyboardType.KEYBOARD:
            if not self.buttons: raise ValueError('Buttons is not set!')
            if not isinstance(self.buttons, typing.List): raise ValueError('Buttons must be a list')
            for row in self.buttons:
                if isinstance(row, typing.List):
                    for v in row: self._keyboard_type.value = self._checkItem(v, self._keyboard_type.value)
                else:
                    self._keyboard_type.value = self._checkItem(row, self._keyboard_type.value)
        else:
            return True

    def _prefix(self) -> str:
        return str(id(self)) + ':'

    @property
    def changed(self):
        """Check if keyboard was changed since last reset"""
        return self._placeholder.changed or self._buttons.changed or self._keyboard_type.changed

    def unchange(self):
        """Mark keyboard as unchanged"""
        self._placeholder.unchange()
        self._buttons.unchange()
        self._keyboard_type.unchange()

    @property
    def buttons(self) -> BotUserKeyboard_t:
        """Get current buttons set"""
        return self._buttons.value

    @buttons.setter
    def buttons(self, v: BotUserKeyboard_t):
        """Set or remove buttons set. If ``v`` is None, will set keyboard type to NONE.
        If current keyboard type is NONE and ``v`` is not Noe will set keyboard type to INLINE"""
        if not v:
            self.keyboard_type = KeyboardType.NONE
        elif self.keyboard_type == KeyboardType.NONE:
            self.keyboard_type = KeyboardType.INLINE
        self._buttons.value = v

    @property
    def placeholder(self) -> str:
        """Get current edit field placeholder text"""
        return self._placeholder.value

    @placeholder.setter
    def placeholder(self, v: str):
        """Set new edit field placeholder text"""
        self._placeholder.value = v

    @property
    def keyboard_type(self) -> KeyboardType:
        """Get current keyboard type"""
        return self._keyboard_type.value

    @keyboard_type.setter
    def keyboard_type(self, v: KeyboardType):
        """Set new keyboard type. Will not change current buttons set"""
        self._keyboard_type.value = v

    def set_inline(self, buttons: BotUserKeyboard_t = None):
        """Set keyboard type to INLINe and apply new buttons set"""
        self.keyboard_type = KeyboardType.INLINE
        self.buttons = buttons

    def set_keyboard(self, buttons: BotUserKeyboard_t = None, placeholder: str = None):
        """Set keyboard type to KEYBOARD and apply new buttons set"""
        self.keyboard_type = KeyboardType.KEYBOARD
        self.buttons = buttons
        self.placeholder = placeholder

    def set_remove(self):
        """Set keyboard type to REMOVE"""
        self.keyboard_type = KeyboardType.REMOVE

    def set_none(self):
        """Set keyboard type to NONE"""
        self.keyboard_type = KeyboardType.NONE

    def _locateCBButton(self, data: str) -> BotKeyboardResult:
        if data.startswith(self._prefix()):
            nRow = 0
            for row in self._markup.inline_keyboard:
                nCol = 0
                for col in row:
                    if col.callback_data == data:
                        return BotKeyboardResult(True, data[len(self._prefix()):], nRow + nCol)
                    nCol += 1
                nRow += self._markup.row_width
        return RESULT_NONE

    def _locateKBButton(self, data: str) -> BotKeyboardResult:
        nRow = 0
        for row in self._markup.keyboard:
            nCol = 0
            for col in row:
                if col.text == data:
                    return BotKeyboardResult(True, data, nRow + nCol)
                nCol += 1
            nRow += self._markup.row_width
        return RESULT_NONE

    def known(self, callback: Callback_t = None, message: Message_t = None) -> BotKeyboardResult:
        """Check if data from callback or message is known as one of keyboard buttons
        :return: button id for known data or RESULT_NONE
        """
        if not self._markup: return RESULT_NONE

        if self.keyboard_type == KeyboardType.INLINE:
            return RESULT_NONE if not callback else self._locateCBButton(callback.data)
        elif self.keyboard_type == KeyboardType.KEYBOARD:
            return RESULT_NONE if not message else self._locateKBButton(message.text)
        else:
            return RESULT_NONE

    def replaceable(self) -> bool:
        """Check if message with new and old keyboard types can be edited in place or need to be recreated"""
        if self._keyboard_type.old == KeyboardType.KEYBOARD or \
                self._keyboard_type.value == KeyboardType.KEYBOARD:
            return False
        return True

    @property
    def hasKeyboard(self):
        """Check if current object have INLINE or KEYBOARD keyboard"""
        return self.keyboard_type == KeyboardType.KEYBOARD or \
               self.keyboard_type == KeyboardType.INLINE

    @property
    def hadKeyboard(self):
        """Check if current object has INLINE or KEYBOARD keyboard before change"""
        return self._keyboard_type.old == KeyboardType.KEYBOARD or \
               self._keyboard_type.old == KeyboardType.INLINE

    @property
    def markup(self) -> BotMarkup_t:
        """Create markup for current keyboard type and buttons set"""
        self._check()

        def _calcWidth() -> typing.Optional[int]:
            if self.buttons is None or len(self.buttons) == 0: return None
            v = 0
            for row in self.buttons:
                if not isinstance(row, typing.List):
                    v = max(v, 1)
                else:
                    v = max(v, len(row))
            return v

        def _makeButton(v):
            if isinstance(v, types.InlineKeyboardButton):
                if v.callback_data:
                    v.callback_data = self._prefix() + v.callback_data
                else:
                    v.callback_data = self._prefix() + 'none'
                return v
            if isinstance(v, types.KeyboardButton): return v

            if isinstance(v, typing.Tuple):
                if len(v) == 0: raise ValueError('Tuple button must have at least one field!')
                s, c = (v[0], '') if len(v) == 1 else v
            else:
                s, c = str(v), ''

            if self.keyboard_type == KeyboardType.KEYBOARD:
                return types.KeyboardButton(s)
            else:
                if not c or len(str(c)) == 0: c = s
                return types.InlineKeyboardButton(s, callback_data=self._prefix() + str(c))

        def setButtons():
            for row in self._buttons.value:
                if isinstance(row, typing.List):
                    self._markup.row(*(_makeButton(v) for v in row))
                else:
                    self._markup.row(_makeButton(row))

        kbd = self.keyboard_type

        if kbd == KeyboardType.KEYBOARD:
            self._markup = types.ReplyKeyboardMarkup(
                resize_keyboard=True,
                input_field_placeholder=self._placeholder.value)
            setButtons()
        elif kbd == KeyboardType.INLINE:
            self._markup = types.InlineKeyboardMarkup(row_width=_calcWidth())
            setButtons()
        elif kbd == KeyboardType.REMOVE:
            self._markup = types.ReplyKeyboardRemove()
        elif kbd == KeyboardType.NONE:
            self._markup = None
        else:
            raise ValueError('Unknown keyboard type')

        return self._markup
