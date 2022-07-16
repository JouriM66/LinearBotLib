import re
import threading
import typing
from re import Pattern

import aiogram
from aiogram import Bot, Dispatcher
from aiogram.utils.exceptions import BadRequest
from aiogram.utils.markdown import escape_md, quote_html

from bot_ilogic import ILogic
from bot_imessage import BotIMessage, OnMessageApplyEvent
from bot_keyboard import KeyboardType
from bot_types import *
from bot_users import BotUser, BotUsers
from settings import *
from utils import *

# noinspection PyUnreachableCode
_printer = print if False else None


def PROC(*args): return PROC_(_printer, *args)


def LOG(*args): return LOG_(_printer, *args)


# ------------------------------------------------------------------------
# WAITERS
# ------------------------------------------------------------------------
class Waiter:
    """Class which is used to filter received messages and callbacks and pass execution to
    user logic.
    """
    chat: 'BotChat'
    isModal: bool = False

    def __init__(self, chat: 'BotChat', messge_id: MessageId_t, /,
                 on_message: typing.Optional[OnMessageEvent] = None,
                 on_callback: typing.Optional[OnCallbackEvent] = None):
        """ Create base waiter class

        :param chat: parent chat waiter will be attached to
        :param messge_id: message id this waiter attacked to if applicable (NoMessageId if waiter not attached to single message)
        :param on_message: Callback to call on new messages
        :param on_callback: Callback called on new INLINE buttons data
        """
        self.chat = chat
        self.messge_id = messge_id
        self._completed = asyncio.Event()
        self._completed.clear()
        self._on_message = on_message
        self._on_callback = on_callback

    async def isWaitingThisMessage(self, chat: 'BotChat', message: Message_t) -> bool:
        """Check if this waiter process specified message"""
        if self._on_message and await self._on_message(self.chat, message):
            LOG('thisMsg')
            return True
        return False

    async def isWaitingThisCallback(self, chat: 'BotChat', cbd: Callback_t) -> bool:
        """Check if this waiter process specified callback data"""
        if self._on_callback and await self._on_callback(self.chat, cbd):
            LOG('thisCB')
            return True
        return False

    def notify_complete(self):
        """Used to notify waiting user logic, what wait is complete. Called from bot loop to inform user logic"""
        LOG('notify_complete')
        self._completed.set()

    async def wait(self, timeout: float = None) -> bool:
        """Wait until complete. Called from user logic to wait waiter condition."""
        if timeout and timeout >= 0:
            try:
                LOG(f'waiting', 'modal', self.isModal, 'tm', timeout)
                await asyncio.wait_for(self._completed.wait(), timeout)
                return True
            except asyncio.TimeoutError:
                self.chat.waiterRemove(self)
                return False
        else:
            LOG(f'waiting', 'modal', self.isModal)
            await self._completed.wait()
            return True


class ModalWaiter(Waiter):
    """Waiter for modal message forms. Only one at a time modal waiter can process messages and callbacks.
    If modal waiter indicate data as known it will be removed from waiters queue and
    data dispatching will stop. If modal waiter indicate data as UNknown, waiter data dispatching
    will stop but waiter leave in waiters queue.
    """
    def __init__(self, chat: 'BotChat', messge_id: MessageId_t, /,
                 on_message: typing.Optional[OnMessageEvent] = None,
                 on_callback: typing.Optional[OnCallbackEvent] = None,
                 remove_unused: bool = None):
        super().__init__(chat, messge_id, on_message, on_callback)
        self._remove_unused = remove_unused
        self.isModal = True

    async def isWaitingThisMessage(self, chat: 'BotChat', message: Message_t) -> bool:
        if not await super().isWaitingThisMessage(chat, message):
            if self._remove_unused:
                await chat.delete(message)
            return False
        else:
            return True


class CommandsWaiter(Waiter):
    """Waiter for commands. Can process list of commands or defined by user callback. Any number of commands waiters
    may be used at a time.
    """
    on_command: typing.Optional[OnCommandEvent]
    commands: typing.Optional[typing.List[str]]

    def __init__(self, chat: 'BotChat', messge_id: MessageId_t,
                 on_command: OnCommandEvent, commands: typing.Optional[typing.List[str]] = None):
        super().__init__(chat, messge_id)
        if on_command is not None and not isinstance(self.on_command, typing.Callable):
            raise ValueError('Command callback must be Callable')
        if commands is not None and not isinstance(commands, typing.List):
            raise ValueError('Commands must be List[str]')
        self.on_command = on_command
        self.commands = commands

    async def isWaitingThisMessage(self, chat: 'BotChat', message: Message_t) -> bool:
        if len(message.text) < 2 or message.text[0] != '/': return False

        try:
            index = message.text.index(' ')
            cmd = message.text[1:index]
            params = message.text[index + 1:]
        except ValueError:
            cmd = message.text[1:]
            params = ''

        cmd = cmd.strip(' \r\n\t\b')
        if not cmd: return False
        params = params.strip(' \r\n\t\b')

        if self.commands is not None:
            return cmd in self.commands and await self.on_command(chat, cmd, params)
        else:
            return await self.on_command(chat, cmd, params)


# ------------------------------------------------------------------------
# ChatMessage
# ------------------------------------------------------------------------

class BotMessage(BotIMessage):
    """BotIMessage implementation for manipulate with channel"""
    chat: 'BotChat'
    waiter: typing.Optional[Waiter]

    def __init__(
            self, chat: 'BotChat',
            text: str = None,
            keyboard_type: KeyboardType = None,
            buttons: BotUserKeyboard_t = None,
            placeholder: str = None,
            media: BotMedia_t = None,
            reply_to_message_id: MessageId_t = None,
            remove_unused: bool = None,
            timeout: float = None,
            on_message: OnMessageEvent = None,
            on_callback: OnCallbackEvent = None,
            on_apply: OnMessageApplyEvent = None,
    ):
        super().__init__(**filterArgs(locals(), ['chat']))
        self.chat = chat
        self.waiter = None

    def _delWaiter(self):
        if self.waiter:
            LOG('M: del waiter')
            self.chat.waiterRemove(self.waiter)
            self.waiter = None

    @staticmethod
    def _loadMedia(media):
        if isinstance(media, str) and \
                not media.startswith('http:') and \
                not media.startswith('https:'):
            f = open(media, 'rb')
            if f: return f
        return media

    async def _deleteMessage(self) -> bool:
        return await self.chat.delete(self)

    async def _createMessage(self) -> MessageId_t:
        reply_to_message_id = self.reply_to_message_id
        if not reply_to_message_id: reply_to_message_id = None

        if self.media:
            msg = await self.chat.bot.send_photo(
                self.chat.chat_id, parse_mode=self.chat.bot.parse_mode,
                photo=self._loadMedia(self.media), caption=self.chat.escape_soft(self.text),
                reply_markup=self.keyboard.markup,
                reply_to_message_id=reply_to_message_id)
        else:
            msg = await self.chat.bot.send_message(
                self.chat.chat_id,
                text=self.chat.escape_soft(self.text), reply_markup=self.keyboard.markup,
                reply_to_message_id=reply_to_message_id)

        LOG('new msg', msg.message_id, 'text', self.text)
        return msg.message_id

    async def _updateMessage(self) -> None:
        if self.media:
            if self._media.changed:
                await self.chat.bot.edit_message_media(
                    media=types.InputMedia(
                        type='photo',
                        media=self._loadMedia(self.media),
                        caption=self.chat.escape_soft(self.text)
                    ),
                    chat_id=self.chat.chat_id, message_id=self.message_id,
                    reply_markup=self.keyboard.markup)
            elif self._text.changed:
                await self.chat.bot.edit_message_caption(
                    chat_id=self.chat.chat_id, message_id=self.message_id,
                    caption=self.chat.escape_soft(self.text), reply_markup=self.keyboard.markup
                )
        else:
            if self._text.changed:
                await self.chat.bot.edit_message_text(
                    text=self.chat.escape_soft(self.text),
                    chat_id=self.chat.chat_id, message_id=self.message_id,
                    reply_markup=self.keyboard.markup
                )
            elif self.keyboard.changed:
                try:
                    await self.chat.bot.edit_message_reply_markup(
                        chat_id=self.chat.chat_id, message_id=self.message_id,
                        reply_markup=self.keyboard.markup
                    )
                # just mask unchanged error instead complex keyboard comparison
                except aiogram.utils.exceptions.MessageNotModified:
                    pass

    async def _OnDeleteMessage(self) -> None:
        self._delWaiter()

    async def _OnShowMessage(self, isCreate: bool) -> None:
        async def _OnCallback(chat: 'BotChat', cbd: Callback_t) -> bool:
            self._result = self.keyboard.known(callback=cbd)
            if self._result.known:
                LOG('SM: known', self._result.data, self._result.index)
                _rc = True
                if self.on_callback:
                    old = cbd.data
                    cbd.data = self._result.data
                    _rc = await self.on_callback(chat, cbd)
                    cbd.data = old
                if _rc:
                    return True
            else:
                if self.on_callback: await self.on_callback(chat, cbd)

            await self._display()
            return False

        async def _OnMessage(chat: 'BotChat', message: Message_t) -> bool:
            self._result = self.keyboard.known(message=message)
            if self._result.known:
                LOG('SM: ok: ', self._result)
                if not self.on_message or await self.on_message(chat, message):
                    return True
            else:
                LOG('SM: unk: ', message.text)
                if self.on_message: await self.on_message(chat, message)

            if self.remove_unused:
                await chat.delete(message)

            await self._display()
            return False

        if isCreate:
            self._result = RESULT_NONE
            self._delWaiter()

        if self.keyboard.keyboard_type == KeyboardType.KEYBOARD:
            if not self.waiter:
                self.waiter = Waiter(self.chat, self.message_id, on_message=_OnMessage)
                LOG('SM: add KBD waiter', self.waiter)
                self.chat.waiterAdd(self.waiter)
        elif self.keyboard.keyboard_type == KeyboardType.INLINE:
            if not self.waiter:
                self.waiter = Waiter(self.chat, self.message_id, on_callback=_OnCallback)
                LOG('SM: add INL waiter', self.waiter)
                self.chat.waiterAdd(self.waiter)

    async def _OnPopupMessage(self) -> BotKeyboardResult:
        with PROC('msg', self.message_id):
            async def _OnCallback(chat: 'BotChat', cbd: Callback_t) -> bool:
                nonlocal localResult
                localResult = self.keyboard.known(callback=cbd)
                if localResult.known:
                    _rc = True
                    LOG('PM: cb known', localResult.data, localResult.index)
                    if self.on_callback:
                        old = cbd.data
                        cbd.data = localResult.data
                        _rc = await self.on_callback(chat, cbd)
                        cbd.data = old
                    if _rc:
                        return True
                else:
                    if self.on_callback: await self.on_callback(chat, cbd)

                await self._display()
                return False

            async def _OnMessage(chat: 'BotChat', message: Message_t) -> bool:
                nonlocal localResult
                localResult = self.keyboard.known(message=message)
                if localResult.known:
                    LOG('PM: msg OK: ', localResult)
                    if not self.on_message or await self.on_message(chat, message):
                        return True
                else:
                    LOG('PM: unk: ', message.text)
                    if self.on_message: await self.on_message(chat, message)

                if self.remove_unused:
                    await chat.delete(message)

                await self._display()
                return False

            localResult = RESULT_NONE
            self._delWaiter()

            if self.keyboard.keyboard_type == KeyboardType.KEYBOARD or \
                    self.keyboard.keyboard_type == KeyboardType.INLINE:
                LOG('PM: add waiter')
                if await self.chat.waiterAdd(
                        ModalWaiter(self.chat, self.message_id, on_callback=_OnCallback, on_message=_OnMessage)
                ).wait(self.timeout):
                    LOG('PM: lrc: ', localResult)
                    return localResult
                else:
                    return RESULT_NONE
            else:
                raise ValueError('Unsupported keyboard type for popup')


# ------------------------------------------------------------------------
# BotChat
# ------------------------------------------------------------------------
_RESTART_LOGIC_ON_EXCEPT = 'restartLogicOnException'
_ERROR_RESTART_COUNT = 'logicErrorRestartCount'
_RESTART_LOGIC_ON_EXIT = 'restartLogicOnExit'
_RESTART_COUNT = 'logicRestartCount'
_LEAVE_CHANNEL_ON_EXIT = 'leaveChannelAfterExit'
_RESTART_DELAY = 'restartDelay'
_MASK_EXCEPTIONS = 'maskExceptions'
_BOT_DOWN_MESSAGE = 'botDownMessage'

_CHAT_SETTINGS = {
    _RESTART_LOGIC_ON_EXCEPT: False,
    _ERROR_RESTART_COUNT: 5,
    _RESTART_LOGIC_ON_EXIT: True,
    _RESTART_COUNT: -1,
    _LEAVE_CHANNEL_ON_EXIT: True,
    _RESTART_DELAY: 5,
    _MASK_EXCEPTIONS: False,
    _BOT_DOWN_MESSAGE: 'The Bot is down. To force start it use /start command',
}


class BotChat(ISettings):
    """ Implementation for single telegram chat.
    Any separate chats (for any group or users) will have unique chat class.
    Automatically created for any new chats by :BotSession:`bot.BotSession`
    """
    # static
    log = logging.getLogger('BotChat')  # NullLogger()
    # ==== bot
    chat: 'BotSession'
    bot: Bot
    # ==== props
    chat_id: ChatId_t
    alive: bool = True

    def __init__(self, session: 'BotSession', chat_id: ChatId_t):
        ISettings.__init__(self, session.sub_cfg(f'chats.{chat_id}'))
        self.chat_id = chat_id
        self.session = session
        self.bot = session.bot
        self.gopt('', _CHAT_SETTINGS)
        self._initMsg()
        self._initLogic()
        self._initWaiters()

    async def chat_done(self):
        await self._closeLogic()
        self._closeWaiters()
        self._closeMsg()

    # -----------------------
    # utils
    # -----------------------
    def user(self, message: typing.Optional[Message_t] = None):
        """Get user associated with specified message"""
        return self.session.user(message if message else self.last)

    def opt(self, nm: str):
        """Get options from storge"""
        return self.gopt(nm, _CHAT_SETTINGS[nm])

    def _ensureSelf(self):
        if not self.alive:
            raise TypeError('Current channel is closed')

    # -----------------------
    # waiters
    # -----------------------
    waitersLock: threading.RLock
    waiters: typing.List[typing.Optional[Waiter]]

    def _initWaiters(self):
        self.waiters = []
        self.waitersLock = threading.RLock()

    def _closeWaiters(self):
        self._waitersDeleteAll()

    def _waitersDeleteAll(self):
        LOG('waitersDeleteAll')
        with self.waitersLock:
            self.waiters = []

    def waiterRemove(self, waiter: Waiter):
        """Remove waiter from queue"""
        if not waiter: return
        LOG(f'CH: del waiter', len(self.waiters), 'm:', waiter.isModal, 'w:', waiter)
        with self.waitersLock:
            self.waiters = [i for i in self.waiters if i is not waiter]
        LOG(f'CH: waiter deleted', len(self.waiters))

    def waiterMessageRemove(self, message_id: MessageId_t):
        """Remove from queue all waiters associated with message"""
        if not message_id: return
        LOG(f'CH: del waiter', len(self.waiters), 'msg', message_id)
        with self.waitersLock:
            self.waiters = [i for i in self.waiters if i.messge_id != message_id]
        LOG(f'CH: waiter deleted', len(self.waiters))

    def waiterAdd(self, waiter: Waiter) -> Waiter:
        """Add new waiter"""
        LOG(f'CH: add waiter[{len(self.waiters)}, m: {waiter.isModal}] : ', waiter)
        with self.waitersLock:
            if waiter not in self.waiters:
                self.waiters.append(waiter)
        LOG(f'CH: waiter added[{len(self.waiters)}]')
        return waiter

    async def waitProcess(self, message: Message_t = None, data: types.CallbackQuery = None):
        """Process received data or message thru waiters queue"""
        if not message and not data: return False

        with PROC('logic', self.logicWorking):
            # start/restart bot logic
            if message and message.text[0] == '/':
                LOG('WP: cmd: ', message.text)
                cmd = message.text[1:]
                if cmd == 'restart':
                    await self.delete()
                    await self.logicCancel()
                    cmd = 'start'
                elif cmd.startswith('restart@'):
                    await self.delete()
                    await self.logicCancel()
                    cmd = 'start@' + cmd[8:]

                if cmd == 'start':
                    await self.delete()
                    self.logicStart(True)
                    LOG('WP: cmd OK', 'logic', self.logicWorking)
                    return
                elif cmd.startswith('start@'):
                    await self.delete()
                    self.logicStart(True, cmd[6:])
                    LOG('WP: cmd OK', 'logic', self.logicWorking)
                    return

            # bot logic is down
            if not self.logicWorking:
                if not await self.logic.OnDownDecide(self, self.last):
                    await self.last.reply(
                        f"""
                        {self.opt(_BOT_DOWN_MESSAGE)}\n
                        Restarted {self.logicRestartCount} times\n
                        Last run with error: {self.logicErrorStopped}
                        """)
                    LOG('!decide')
                    return
                self.logicStart()

            # have no bot logic, nothing to do
            if not self.logicWorking: return

            # dispatch events
            LOG('WP', 'waiters', len(self.waiters))
            if len(self.waiters):
                with self.waitersLock:
                    idx: int = len(self.waiters)
                    while idx > 0:
                        idx -= 1
                        try:
                            w = self.waiters[idx]
                            if message:
                                rc = await w.isWaitingThisMessage(self, message)
                            elif data:
                                rc = await w.isWaitingThisCallback(self, data)

                            LOG(f'WP', idx, 'modal', w.isModal, 'rc', rc)
                            if rc:
                                if w.isModal: self.waiters = self.waiters[:idx]
                                w.notify_complete()
                            if rc or w.isModal:
                                LOG('WP', 'ret', len(self.waiters))
                                return
                        except Exception as e:
                            self.log.error(f'waitProcess exception: {e}')
                            raise
                LOG('WP', 'pass', len(self.waiters))

    # -----------------------
    # bot logic
    # -----------------------
    logicTask: typing.Optional[asyncio.Task] = None
    logicRestartCount = 0
    logicStopped = False
    logicErrorStopped = False
    logic: type(ILogic) = None

    def _initLogic(self):
        self.logic = self.session.logic(self, self.sub_cfg('bot logic'))

    async def _closeLogic(self):
        if self.logicWorking:
            await self.logicCancel('chat is stopped')
        self.logic = None

    @property
    def logicWorking(self) -> bool:
        """Check if user logic is working"""
        return self.alive and (self.logicTask is not None) and (not self.logicTask.cancelled())

    async def logicCancel(self, msg: str = 'manual stop'):
        """Stop user logic. Will wait until logic actually stops"""
        if not self.logicWorking: return
        self.logicTask.cancel(msg)

        tasks = [self.logicTask, asyncio.create_task(asyncio.sleep(5))]
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        if self.logicTask and not self.logicTask.cancelled():
            self.log.error('Logic cancellation took too long!')

        self.logicTask = None

    def logicStart(self, force: bool = False, params: str = None) -> bool:
        """
        Check if bot_logic coro can be started and start it.
        :param force: force to start
        :param params: parameters passed as "/start@params" or "/restart@params"
        :return: True if bot logic was succ started or already working
        """

        if self.logicWorking: return True

        async def _wrapper():
            self.log.error(f'Start bot logic task')
            try:
                if self.logicRestartCount > 0 and self.opt(_RESTART_DELAY) >= 0:
                    await asyncio.sleep(self.opt(_RESTART_DELAY))

                await self.logic.main(self, params if params else '')
                self.logicTask = None

                if self.opt(_LEAVE_CHANNEL_ON_EXIT):
                    await self.leave_channel()
            except Exception as e:
                await self.bot.send_message(
                    self.chat_id,
                    self.escape(
                        'Bot exception!\n' +
                        e.args[0] +
                        '\n\nBot will be terminated.\n'
                        'Please send situation and error description to developer'
                    )
                )
                self.log.fatal('Logic was terminated by error!')
                self.log.exception('Logic error', exc_info=e)
                self.logicErrorStopped = True
            finally:
                self._waitersDeleteAll()
                self.logicRestartCount += 1
                self.logicStopped = True
                self.logicTask = None
                self.log.error(f'Stopped bot logic task')

        def _stopped(task):
            self.logicTask = None
            if self.alive:
                try:
                    self.logic.OnExit(self, self.alive)
                except Exception as e:
                    self.log.fatal(f'Logic OnExit encounter an error!')
                    self.log.exception(f'Logic OnExit error', exc_info=e)

        if self.logicStopped:
            if force:
                self.logicRestartCount = 0
            else:
                if self.logicErrorStopped:
                    if not self.opt(_RESTART_LOGIC_ON_EXCEPT):
                        return False
                elif not self.opt(_RESTART_LOGIC_ON_EXIT):
                    return False

                cn = self.opt(_ERROR_RESTART_COUNT if self.logicErrorStopped else _RESTART_COUNT)
                rcn = self.logicRestartCount
                if cn >= 0 and rcn >= cn:
                    if rcn == cn:
                        self.log.error(f'Max bot logic restart attempts {cn} reached. Exiting')
                    self.logicRestartCount += 1
                    return False

        self.logicStopped = False
        self.logicErrorStopped = False
        self.logicTask = asyncio.get_event_loop().create_task(_wrapper())
        self.logicTask.add_done_callback(_stopped)
        return True

    # -----------------------
    # MESSAGE
    # -----------------------
    lastReceivedMessage: typing.Optional[Message_t] = None
    lastReceivedCallback: typing.Optional[Callback_t] = None
    lastMessage: typing.Optional[BotIMessage] = None

    def _initMsg(self):
        pass

    def _closeMsg(self):
        pass

    @property
    def last(self) -> Message_t:
        """Get last message receive by this channel"""
        return self.lastReceivedMessage if self.lastReceivedMessage else Message_t()

    @property
    def last_id(self) -> MessageId_t:
        """Get last message id received by this channel"""
        return self.lastReceivedMessage.message_id if self.lastReceivedMessage else NoMessageId

    async def process_message(self, message: Message_t):
        if not self.alive: return
        self.lastReceivedMessage = message
        try:
            if self.session.OnMessage and await self.session.OnMessage(self, message):
                return
        except Exception as e:
            self.log.error(f'session.OnMessage: exception {e}')
            raise
        await self.waitProcess(message=message)

    async def process_callback(self, data: types.CallbackQuery):
        if not self.alive: return
        self.lastReceivedMessage = data.message
        try:
            if self.session.OnCallback:
                if await self.session.OnCallback(self, data):
                    return
        except Exception as e:
            self.log.error(f'session.OnCallback: exception {e}')
            raise
        await self.waitProcess(data=data)

    # -----------------------
    # User interface
    # -----------------------
    def _getMessageId(self, message: BotMessageTypes_t) -> MessageId_t:
        mid = NoMessageId
        if not mid and isinstance(message, int): mid = message
        if not mid and isinstance(message, Message_t): mid = message.message_id
        if not mid and isinstance(message, BotIMessage): mid = message.message_id
        return mid

    MARKDOWN_SOFT_QUOTE_PATTERN: Pattern[str] = re.compile(r"(?<!\\)([>#+\-=|{}.!])")

    def escape_soft(self, text):
        """'Soft' version of messages text masking. Masks only these characters, which is not used
        in current parse_mode syntax. Used for text which CAN use parse syntax. Is used automatically
        for ALL text data in ALL messages. If message contains special symbols but they are not used
        for syntax these need to be masked by hand or message send will fail.
        """
        if self.bot.parse_mode.casefold() == PARSE_MARKDOWNV2.casefold() or \
                self.bot.parse_mode.casefold() == PARSE_MARKDOWN.casefold():
            return re.sub(pattern=self.MARKDOWN_SOFT_QUOTE_PATTERN, repl=r"\\\1", string=text)
        else:
            return text

    def escape(self, text):
        """'Full' version of messages text masking. Mask all characters need to be masked
        for current parse_mode. Can be used with data text, received from other sources like
        databases which do not use message parsing syntax."""
        if self.bot.parse_mode.casefold() == PARSE_MARKDOWNV2.casefold() or \
                self.bot.parse_mode.casefold() == PARSE_MARKDOWN.casefold():
            return escape_md(text)
        elif self.bot.parse_mode.casefold() == PARSE_HTML.casefold():
            return quote_html(text)
        else:
            return text

    async def chat_title(self, title: str) -> bool:
        """Change channel title. Works only on group, not personal, chats."""
        try:
            return await self.bot.set_chat_title(self.chat_id, title)
        except aiogram.utils.exceptions.BadRequest:
            return False

    async def pin(self, message: BotMessageTypes_t, disable_notification: typing.Optional[bool] = None) -> bool:
        """Pin specified message"""
        try:
            if message:
                return await self.bot.pin_chat_message(
                    self.chat_id, message_id=self._getMessageId(message), disable_notification=disable_notification)
            else:
                return False
        except aiogram.utils.exceptions.BadRequest:
            return False

    async def leave_channel(self) -> bool:
        """Leave current channel. Can be used only in group, not personal chats."""
        if not self.alive: return True
        self.log.error(f'Trying to leave channel')
        try:
            if await self.bot.leave_chat(self.chat_id):
                self.alive = False
                self.session.chat_done(self)
                return True
        except BadRequest as e:
            self.log.error(f'!leave: {e}')
            # no need to unmask this exception!
        return False

    # no exceptions, ret bool
    async def delete(self, message: BotMessageTypes_t = None) -> bool:
        """Delete message. Mask exception about deleting non-existent messages.

        :return: True: If message was successfully deleted.
        False: If error happen of message_id is not set
        """
        with PROC('msg', message):
            self._ensureSelf()

            message_id = self.last_id if message is None else self._getMessageId(message)
            if not message_id: return True

            LOG('del=', message_id)
            try:
                if await self.bot.delete_message(chat_id=self.chat_id, message_id=message_id):
                    if self.last_id == message_id:
                        self.lastReceivedMessage.message_id = NoMessageId
                        self.waiterMessageRemove(message_id)
                    return True
            except BadRequest as e:
                self.log.error(f'!delete: {e}')
                if not self.opt(_MASK_EXCEPTIONS):
                    raise
            return False

    # wait for next message or timeout
    async def waitmsg(self, timeout: float = None) -> bool:
        """Wait until any new message arrive or timeout expires.

        :return: True: if message arrive and False if on timeout.
        """
        self._ensureSelf()

        async def _onMessage(chat, message) -> bool:
            return True

        return await self.waiterAdd(ModalWaiter(self, NoMessageId, on_message=_onMessage)).wait(timeout)

    # MENU
    def build(self,
              text: str,
              keyboard_type: KeyboardType = None,
              buttons: BotUserKeyboard_t = None,
              placeholder: str = None,
              media: BotMedia_t = None,
              reply_to_message_id: MessageId_t = None,
              remove_unused: bool = None,
              timeout: float = None,
              on_message: OnMessageEvent = None,
              on_callback: OnCallbackEvent = None,
              on_apply: OnMessageApplyEvent = None,
              ) -> BotIMessage:
        """Create new message object"""
        self._ensureSelf()
        return BotMessage(chat=self, **filterArgs(locals()))

    async def say(self,
                  text: str,
                  keyboard_type: KeyboardType = None,
                  buttons: BotUserKeyboard_t = None,
                  placeholder: str = None,
                  media: BotMedia_t = None,
                  reply_to_message_id: MessageId_t = None,
                  remove_unused: bool = None,
                  timeout: float = None,
                  on_message: OnMessageEvent = None,
                  on_callback: OnCallbackEvent = None,
                  on_apply: OnMessageApplyEvent = None,
                  remove_source: bool = False,
                  replace: bool = None,
                  replace_id: BotMessageTypes_t = None,
                  wait_delay: float = None,
                  ) -> BotIMessage:
        """Create new message object and send it as non-modal"""
        self._ensureSelf()

        if remove_source and reply_to_message_id != self.last_id: await self.delete()

        if replace:
            replace_id = self.lastMessage if replace_id is None else self._getMessageId(replace_id)
            if replace_id: await self.delete(replace_id)

        params = filterArgs(locals(), ['remove_source', 'replace', 'replace_id', 'wait_delay'])
        msg = self.build(**params)
        await msg.show(wait_delay=wait_delay)

        if msg.message_id != NoMessageId:
            self.lastMessage = msg
        return msg

    async def reply(self,
                    text: str,
                    keyboard_type: KeyboardType = None,
                    buttons: BotUserKeyboard_t = None,
                    placeholder: str = None,
                    media: BotMedia_t = None,
                    reply_to_message_id: MessageId_t = None,
                    remove_unused: bool = None,
                    timeout: float = None,
                    on_message: OnMessageEvent = None,
                    on_callback: OnCallbackEvent = None,
                    on_apply: OnMessageApplyEvent = None,
                    remove_source: bool = False,
                    replace: bool = None,
                    replace_id: BotMessageTypes_t = None,
                    wait_delay: float = None,
                    ) -> BotIMessage:
        """Create new message object and send it as non-modal as reply to another message"""
        if not reply_to_message_id: reply_to_message_id = self.last_id
        return await self.say(**filterArgs(locals()))

    async def popup(self,
                    text: str,
                    keyboard_type: KeyboardType,
                    buttons: BotUserKeyboard_t,
                    placeholder: str = None,
                    media: BotMedia_t = None,
                    reply_to_message_id: MessageId_t = None,
                    remove_unused: bool = None,
                    timeout: float = None,
                    on_message: OnMessageEvent = None,
                    on_callback: OnCallbackEvent = None,
                    on_apply: OnMessageApplyEvent = None,
                    remove_source: bool = False,
                    replace: bool = None,
                    replace_id: BotMessageTypes_t = None,
                    ) -> BotKeyboardResult:
        """Create new message object and send it in modal mode.
        Only messages with keyboards can be in modal mode.
        Will return after any button selection.

        Can be message with INLINE or KEYBOARD keyboards.
        """
        with PROC('popup'):
            return await(await self.say(**filterArgs(locals()))).popup()

    async def menu(self,
                   text: str,
                   buttons: BotUserKeyboard_t,
                   media: BotMedia_t = None,
                   reply_to_message_id: MessageId_t = None,
                   remove_unused: bool = None,
                   timeout: float = None,
                   on_message: OnMessageEvent = None,
                   on_callback: OnCallbackEvent = None,
                   on_apply: OnMessageApplyEvent = None,
                   remove_source: bool = False,
                   replace: bool = None,
                   replace_id: BotMessageTypes_t = None,
                   ) -> BotKeyboardResult:
        """Create new message with INLINE keyboard and send it in modal mode"""
        with PROC('menu'):
            return await self.popup(keyboard_type=KeyboardType.INLINE, **filterArgs(locals()))

    async def ask(self,
                  text: str,
                  buttons: BotUserKeyboard_t,
                  media: BotMedia_t = None,
                  reply_to_message_id: MessageId_t = None,
                  remove_unused: bool = None,
                  timeout: float = None,
                  on_message: OnMessageEvent = None,
                  on_apply: OnMessageApplyEvent = None,
                  remove_source: bool = False,
                  replace: bool = None,
                  replace_id: BotMessageTypes_t = None,
                  ) -> int:
        """Create new message with KEYBOARD keyboard and send it in modal mode"""
        with PROC('ask'):
            rc = await self.popup(keyboard_type=KeyboardType.KEYBOARD, **filterArgs(locals()))
            return rc.index if rc.known else -1

    async def askYesNo(self,
                  text: str,
                  buttons: typing.List[str] = None,
                  media: BotMedia_t = None,
                  reply_to_message_id: MessageId_t = None,
                  remove_unused: bool = None,
                  timeout: float = None,
                  on_message: OnMessageEvent = None,
                  on_apply: OnMessageApplyEvent = None,
                  remove_source: bool = False,
                  replace: bool = None,
                  replace_id: BotMessageTypes_t = None,
                  ) -> int:
        """Create new message with two KEYBOARD buttons.
        :return: Index of button selected or -1 on timeout or error
        """
        if not buttons:
            buttons = [['YES','NO']]
        elif not isinstance(buttons,typing.List):
            raise ValueError('Buttons must be a list with buttons cations')
        elif len(buttons) < 2:
            raise ValueError('Buttons must contains at least 2 cations')
        else:
            buttons = [ [buttons[0], buttons[1] ] ]
        return await self.ask( **filterArgs(locals()) )

# ------------------------------------------------------------------
class BotChats(typing.Dict[str, typing.Optional[BotChat]]):
    """List of chats since bot start"""
    session: 'BotSession'

    def __init__(self, session: 'BotSession'):
        super(BotChats, self).__init__()
        self.session = session

    def chat(self, message: Message_t) -> BotChat:
        chat_id = message.chat.id  # let it traps here if something wrong w data

        c = self.setdefault(chat_id, None)
        if not c:
            c = BotChat(self.session, chat_id)
            self[chat_id] = c
        return c

    async def chat_done(self, chat: BotChat):
        if not chat: return
        self[chat.chat_id] = None
        await chat.chat_done()


# ------------------------------------------------------------------
# BotSession
# ------------------------------------------------------------------
_BOT_SETTINGS = {
}

class BotSession(ISettings):
    """Bot session. Singleton to process all messages and spawn BotChat objects for
    new channels and sessions.
    """
    # static
    log = logging.getLogger('BotSession')
    # ==== private
    storage: typing.Optional[SettingsIStorage] = None
    dispatcher: Dispatcher
    bot: Bot
    # ==== props
    chats: BotChats
    users: BotUsers
    # ==== events
    OnMessage: typing.Optional[OnMessageEvent] = None
    OnCallback: typing.Optional[OnCallbackEvent] = None

    # ----------------------
    def __init__(self, dispatcher: Dispatcher, logic: type(ILogic), /,
                 on_message: OnMessageEvent = None,
                 on_callback: OnCallbackEvent = None,
                 storage: typing.Optional[SettingsIStorage] = None):
        super(BotSession, self).__init__(newSettings())
        self.dispatcher = dispatcher
        self.bot = dispatcher.bot

        self.storage = storage if storage is not None else SettingsIStorage()
        self.storage.load(self)
        self.gopt('', _BOT_SETTINGS)

        self.OnMessage = on_message
        self.OnCallback = on_callback
        self.logic = logic

        # last since they may need chat initialized
        self.chats = BotChats(self)
        self.users = BotUsers(self.sub_cfg('users'))

    # ----------------------
    # utils
    # ----------------------
    def opt(self, nm: str):
        return self.gopt(nm, _BOT_SETTINGS[nm])

    def chat(self, message: Message_t) -> BotChat:
        return self.chats.chat(message)

    def chat_done(self, chat: BotChat):
        self.chats.chat_done(chat)

    def user(self, message: Message_t) -> BotUser:
        return self.users.user(message)

    def saveSettings(self):
        self.storage.save(self)

    def loadSettings(self):
        self.storage.load(self)

    # ----------------------
    # bot event dispatchers
    # ----------------------
    async def process_message(self, message: Message_t):
        """Must be called for all new messages processed by the bot"""
        await self.chat(message).process_message(message)

    async def process_callback(self, cbd: types.CallbackQuery):
        """Must be called for all new callback data processed by the bot"""
        c = self.chat(cbd.message)
        await c.process_callback(cbd)
