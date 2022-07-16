from bot_keyboard import BotKeyboard, KeyboardType
from bot_types import *
from utils import *

OnMessageApplyEvent = typing.Callable[['BotIMessage'], typing.Awaitable[None]]


class BotIMessage(Applicable):
    """ Interface for telegram message which can be
        manipulated (send or modified).
    """
    _keyboard: BotKeyboard = None
    _text: Changeable[str]
    _media: Changeable[typing.Optional[BotMedia_t]]
    _message_id: MessageId_t = NoMessageId
    _modal: bool = False
    _result: BotKeyboardResult = RESULT_NONE
    reply_to_message_id: MessageId_t = None
    remove_unused: bool = None
    timeout: float = None
    on_message: OnMessageEvent = None
    on_callback: OnCallbackEvent = None
    on_apply: OnMessageApplyEvent = None

    def __init__(self,
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
        """Create new message object

        :param text: text part on any message (is "text" for simple message, or "caption" for multimedia, etc)
        :param keyboard_type: type of keyboard message will use
        :param buttons: set of buttons message will use with specified keyboard
        :param placeholder: text will be shown in edit field if no text entered (works only with ``KeyboarType.KEYBOARD``)
        :param media: string image url, local image pathname or byte stream. If is set message will be of "photo" type
        :param reply_to_message_id: message id this message replying to
        :param remove_unused: If is set modal functions will auto delete all incoming messages
        :param timeout: If is set to nonzero value used to limit time modal functions works
        :param on_message: Called for every message in modal mode
        :param on_callback: Called for any data notification send by telegram. Called in any form if message have inline keyboard.
        :param on_apply: Called before display or update message to allow user to modify its content.
        """
        Applicable.__init__(self, ['text', 'media', 'reply_to_message_id', 'remove_unused', 'timeout','on_message','on_callback','on_apply'])
        self._keyboard = BotKeyboard(keyboard_type=keyboard_type, buttons=buttons, placeholder=placeholder)
        self._text = Changeable[str]('')
        self._media = Changeable[BotMedia_t](None)
        self.apply(locals())
        self._keyboard.apply(locals())
        self.say = self.show

    async def __aenter__(self):
        return await self.show()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.delete()

    @property
    def result(self) -> BotKeyboardResult:
        """Get last result was set in non-modal form of message with inline keyboard.

        Resets result after get, so next call will get RESULT_NONE
        :return: BotKeyboardResult class
        """
        v = self._result if not self.modal else RESULT_NONE
        self._result = RESULT_NONE
        return v

    @property
    def changed(self) -> bool:
        """Check if message was changed since last send"""
        return self._keyboard.changed or self._text.changed or self._media.changed

    def unchange(self):
        """Reset change status of message to "unchanged" """
        self._keyboard.unchange()
        self._text.unchange()
        self._media.unchange()

    @property
    def message_id(self) -> MessageId_t:
        """Get current message id. Will get NoMessageId if message was not send yet or was deleted."""
        return self._message_id

    @property
    def modal(self) -> bool:
        """Check if current message is in modal mode"""
        return self._modal

    @property
    def keyboard(self) -> BotKeyboard:
        """Current keyboard"""
        return self._keyboard

    def keyboard_inline(self, buttons: BotUserKeyboard_t = None):
        """Set keyboard to inline type and fill it buttons. It will be applied on next message send"""
        self.keyboard.set_inline(buttons)

    def keyboard_keys(self, buttons: BotUserKeyboard_t = None, placeholder: str = None):
        """Set keyboard to keyboard type and fill it buttons. It will be applied on next message send"""
        self.keyboard.set_keyboard(buttons=buttons, placeholder=placeholder)

    def keyboard_remove(self):
        """Set keyboard to remove type and remove all buttons. It will be applied on next message send"""
        self.keyboard.set_remove()

    @property
    def text(self) -> str:
        """Get current message text"""
        return self._text.value

    @text.setter
    def text(self, v: str):
        """Set message text. It will be applied on next message send"""
        self._text.value = v

    @property
    def media(self) -> BotMedia_t:
        """Get current message media"""
        return self._media.value

    @media.setter
    def media(self, v: BotMedia_t):
        """Set message media. It will be applied on next message send"""
        self._media.value = v

    async def _display(self,wait_delay:float=None) -> 'BotIMessage':
        if self.on_apply: await self.on_apply(self)

        if self.message_id and not self.changed: return self

        if self._modal and not self.keyboard.hasKeyboard:
            raise ValueError('Cant popup message without keyboard')

        if self.message_id:
            if not self.keyboard.replaceable():
                await self.delete()

        try:
            if not self.message_id:
                self._message_id = await self._createMessage()
                if self.message_id and not self.modal:
                    await self._OnShowMessage(True)
            else:
                await self._updateMessage()
                if not self.modal:
                    await self._OnShowMessage(False)
        finally:
            self.unchange()

        if self.message_id and not self.modal and wait_delay:
            await asyncio.sleep(wait_delay)

        return self

    async def show(self, /,
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
                   wait_delay: float = None,
                   ) -> 'BotIMessage':
        """Send new or update existing message

        Note: If message can not be updated in place it will be automatically deleted and sended again as new
        """
        self.apply(locals())
        self._keyboard.apply(locals())
        await self._display(wait_delay)
        return self

    async def popup(self, /,
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
                    ) -> BotKeyboardResult:
        """Display current message in modal form.
        Uses currently sent message if it is possible.
        Will delete message on exit from modal state.
        """
        self.apply(locals())
        self._keyboard.apply(locals())

        if not self.keyboard.hasKeyboard:
            raise ValueError('Can not popup message without keyboard')
        try:
            self._modal = True
            await self._display()
            if not self.message_id:
                return RESULT_NONE
            return await self._OnPopupMessage()
        finally:
            self._modal = False
            await self.delete()

    async def delete(self) -> bool:
        """Delete current message. Set ``message_id`` to ``NoMessageId``. Any attempts to show() or update() deleted message will send new one."""
        if self.message_id:
            if not await self._deleteMessage():
                return False
            self._message_id = NoMessageId
            await self._OnDeleteMessage()
        return True

    async def _deleteMessage(self) -> bool:
        """Called to delete message. Its guaranteed what message was send and message_id is valid"""
        pass

    async def _createMessage(self) -> MessageId_t:
        """Called to create new message. Called if current message was not shown yet or was deleted."""
        pass

    async def _updateMessage(self) -> None:
        """Called to update existing message. Its guaranteed what message can be updated"""
        pass

    async def _OnShowMessage(self,isCreate:bool) -> None:
        """Called for NON-MODAL messages just after create or update. Is used to do something with messages. F.i. to setup hooks to catch message buttons."""
        pass

    async def _OnDeleteMessage(self) -> None:
        """Called after message was successfully deleted. Used to free resources or remove hooks."""
        pass

    async def _OnPopupMessage(self) -> BotKeyboardResult:
        """Called to execute modal mode for message"""
        pass
