from bot_types import *
from settings import *

_UOPT_NAME = 'name'
_USER_SETTINGS = {
    _UOPT_NAME: ''
}


class BotUser(ISettings):
    """Class for single user parameters"""
    user_id: UserId_t

    def __init__(self, cfg: ISettings, user_id: UserId_t):
        super().__init__(cfg)
        self.user_id = user_id
        self.gopt('', _USER_SETTINGS)

    def opt(self, nm: str): return self.gopt(nm, _USER_SETTINGS[nm])

    @property
    def name(self): return self.opt(_UOPT_NAME)

    @name.setter
    def name(self, val): self.sopt(_UOPT_NAME, val)


# -------------------------------------------------------------------
class BotUsers(typing.Dict[str, typing.Optional[BotUser]]):
    """List of all users"""
    _cfg: ISettings

    def __init__(self, cfg: ISettings):
        super().__init__()
        self._cfg = cfg

    def user(self, message: Message_t) -> BotUser:
        user_id = message.from_user.id  # let it traps here if something wrong w data
        user = self.setdefault(user_id, None)
        if user is None:
            self[user_id] = BotUser(cfg=self._cfg.sub_cfg(str(user_id)), user_id=user_id)
            return self[user_id]
        else:
            return user
