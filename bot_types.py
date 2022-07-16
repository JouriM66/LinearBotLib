import io
import typing
from aiogram.types import InlineKeyboardButton, InputFile
from aiogram import types

# ------------------------------------------------------------------------
ChatId_t = types.base.Integer
MessageId_t = types.base.Integer
UserId_t = typing.Union[str, int, None]

Message_t = types.Message
Callback_t = types.CallbackQuery

BotMarkup_t = typing.Union[types.InlineKeyboardMarkup, types.ReplyKeyboardMarkup, types.ReplyKeyboardRemove]
BotUserKey_t = typing.Union[typing.Tuple[str, typing.Any], str, types.InlineKeyboardButton, types.KeyboardButton]
BotUserKeyboard_t = typing.List[typing.List[BotUserKey_t]]
BotMessageTypes_t = typing.Optional[typing.Union['BotIMessage', Message_t, MessageId_t]]


class BotKeyboardResult:
    """Class to hold data about selected button
    :var known: Is set tot Trie if object has data for known button
    :var data: Is set to data for known button or ''
    :var index: Is set to index of known button or -1.
    """
    known: bool
    data: str
    index: int

    def __init__(self, known: bool, data: str = '', index: int = -1):
        self.known = known
        self.data = data
        self.index = index

RESULT_NONE = BotKeyboardResult(False)
"""Type used to indicate unknown result"""

BotMedia_t = typing.Union[InputFile, io.BytesIO, io.FileIO, str]

# ------------------------------------------------------------------------
NoChatId = 0
NoMessageId = 0
NoUserId = 0

PARSE_HTML = 'HTML'
PARSE_MARKDOWN = 'Markdown'
PARSE_MARKDOWNV2 = 'MarkdownV2'
PARSE_DEFAULT = PARSE_MARKDOWNV2

IDYES = 0
IDNO  = 1
IDCANCEL = 2

# ------------------------------------------------------------------------
OnMessageEvent = typing.Callable[['BotChat', Message_t], typing.Awaitable[bool]]
"""Called by message in modal form for any new messages received.

Must return True for continue to process message or False to skip processing and mark message as unknown for caller.

If return is True caller will check message and if its known modal mode will be ended with result from this message.

If return is False caller will stop message processing and pass message to the next waiting.    
"""

OnCallbackEvent = typing.Callable[['BotChat', Callback_t], typing.Awaitable[bool]]
"""Called for all callback data received in modal message form or if message have INLINE buttons.
 
Must return True for continue process message or False to skip processing and mark message as unknown for caller.

If return is True caller will check message and if its known modal mode will be ended with result from this message.

If return is False caller will stop message processing and pass message to the next waiting.    
"""

OnCommandEvent = typing.Callable[['BotChat', str, str], typing.Awaitable[bool]]
"""Called for process bot commands passed by user using '/command' form. Used by ``CommandsWaiter``

To process commands user need to register ``CommandsWaiter`` in chat.

Return True if command is known and processed, False to continue process command by next waiter.
"""
