# LinearBotLib
Library based on *aiogram* to simplify develop Telegram bots.

# Requirements
Library: aiogram

# Goals
Allow user to programm bot logic in usual, linear way without fighting with asyncronous telegram<->API conversation model.

```python
class Logic(ILogic):
    async def main(self, chat: BotChat, params: str) -> None:
        chat.user().name = chat.last.from_user.full_name
        name = chat.user().name

        await logic_CALC(chat, name)

        if params:
            pstr = f'\nYou started me with parameters *"{escape_md(params)}"*, but I dont support any 😷\n\n'
        else:
            pstr = ''

        titleMsg = await chat.reply(
            f'Hi, *{name}*.\n'
            f'{pstr}'
            f'You are at examples section',
            media='data/Icon-Hi.png'
        )

        while True:
            rc = await chat.menu(
                'Choose test group to go',
                [[('➡ Menu tests...', 'menu')],
                 [('❓ Some asking', 'ask'), ('✌ Funny one :)', 'wait'), ('🍱', 'calc')],
                 [('❌ Close', 0), ('❌ Cancel', 0), ('❎ Abandon!', 0), ('➰ F* off!!', 0)],
                 ],
                remove_unused=True
            )
            if not rc.known: break
            if rc.data == 'menu':
                await logic_MENU(chat, name)
            elif rc.data == 'ask':
                await logic_ASK(chat, name)
            elif rc.data == 'wait':
                await logic_WAIT(chat, name)
            elif rc.data == 'calc':
                await logic_CALC(chat, name)
            else:
                break

        await titleMsg.delete()
        await chat.say(f'Calm down mate!\nIts all done already.\nSee you 👋', wait_delay=1)
        await chat.say(f'...btw, if you wanna reply you can use "/start" command.', wait_delay=2)
        await chat.say(f'Just saying...')
```

# License
Fully free to use, modify and whatever
No responsibility tho
