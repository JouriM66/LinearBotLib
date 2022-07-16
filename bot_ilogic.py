from bot_types import *
from settings import ISettings

# ------------------------------------------------------------------------
class ILogic(ISettings):
    """Interface for linear logic implementation for each ``BotChat`` channel.

    Each ``BotChat`` object uses this interface to call user logic
    functions. Each channel will have separate, unique logic object.
    """
    chat: 'BotChat'

    def __init__(self, chat: 'BotChat', cfg: ISettings):
        super().__init__(cfg)
        self.session = chat

    async def main(self,chat:'BotChat',params:typing.List[str]) -> None:
        """Main user logic function. Called after '/start' or '/restart' command and will run until
        exception happen or finished.

        Executed in parallel with bot task.

        Note: MUST NOT block on operations called from outside (like callbacks).

        :param chat: parent chat executing logic
        :param params: string with parameters passed to '/start' or '/restart' commands.
        """
        pass

    def OnExit(self,chat:'BotChat',isAlive:bool) -> None:
        """Called after logic procedure finished.
        Used just for notification. Can be used f.i. to free resources.

        :param chat: parent chat executing logic
        :param isAlive: True is chat object is alive (can be used to communicate with channel), False if chat is closed.
        """
        pass

    # ret false to disable bot_ilogic restart
    async def OnDownDecide(self, chat: 'BotChat', message: Message_t) -> bool:
        """Called to decide what to do if some notifications received in channel but logic is down (finished or terminated by error)

        :param chat: parent chat executing logic
        :param message: message object which "wake up" channel
        :return: True to restart logic task or False to stay dead.
        """
        return True
