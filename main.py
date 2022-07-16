import asyncio.threads
import datetime
import logging
import random
import re
from re import Pattern

import aiogram
from aiogram import Bot, Dispatcher
from aiogram.utils import executor
from aiogram.utils.markdown import escape_md

from bot import BotChat, BotSession
from bot_ilogic import ILogic
from bot_imessage import BotIMessage
from bot_keyboard import KeyboardType
from bot_types import *
from utils import readAPIToken

# Configure logging
logging.basicConfig(level=logging.WARNING)
log = logging.getLogger('BOT')


# ------------------------------------------------------------------------
async def logic_MENU_Form(chat: BotChat, name):
    # --------------------
    # Its VERY stupid and brute-force form-fill test, but its just a functionality test
    titleMsg = await chat.say(
        f'Here is simple form filler example, *{name}*.\n'
        'We have several fields in our input form, lets fill it with data using multiply menus.')

    # class for every field in our form
    class Field:
        def __init__(self, name: str, value: typing.Any) -> None:
            self.name = name
            self.value = value
            self.menu = chat.build('', buttons=[['Change']])

    # fill some data
    form = [Field('name', 'John'), Field('place', 'Mars'), Field('income', 100)]

    # this will be our OK/Cancel message
    okMenu = chat.build(
        'Please check all fields data and confirm it',
        buttons=[[('Send', 'YES'), ('Cancel', 'NO')]]
    )

    # query cycle
    # on each iteration we will update fields menu and wait for action on any of them
    # cbWait is used to signal if any menus got some actions
    confirmed = False
    hasData = asyncio.Event()
    while True:
        async def cbWait(chat, data: Callback_t) -> bool:
            hasData.set()
            return True

        # update form view
        for field in form:
            await field.menu.show(
                f'Your *{field.name}* is *__{field.value}__*',
                on_callback=cbWait)
        await okMenu.show(on_callback=cbWait)

        # wait for action
        await hasData.wait()

        # check who have actions
        rc = okMenu.result
        if rc.data == 'YES':
            confirmed = True
            break
        elif rc.data == 'NO':
            break

        for field in form:
            rc = field.menu.result
            if not rc.known: continue

            msg = await chat.say(f'Plese enter new value for *__{field.name}__*:')
            await chat.waitmsg()

            # del user input
            await chat.delete()
            # del input title
            await chat.delete(msg)

            if isinstance(field.value, int):
                try:
                    field.value = int(chat.last.text)
                except:
                    field.value = -1
            else:
                field.value = chat.last.text

        # do not forget to reset action notify
        hasData.clear()

    # remove all menus by hand
    await okMenu.delete()
    for field in form: await field.menu.delete()

    # show changed data
    rc = '\n'.join(f'{field.name} = *__{field.value}__*' for field in form)
    if confirmed:
        await titleMsg.show(f'Your CONFIRM your choice and data is:\n' + rc)
    else:
        await titleMsg.show(f'Your CANCEL your choice, but changed data is:\n' + rc)


async def logic_MENU_Simple1(chat: BotChat, name):
    titleMsg = await chat.say(
        f'Here is MODAL menu sample, {name}.\n'
        'This mean menu will popup only until you select something from it.'
        'In this menu you can enter messages after menu shown')

    # sinple message
    menu = await chat.say('some menu title')

    # we can add\remove\modify its buttons any time
    menu.keyboard_inline([
        ['b'],
        ['a', 'b', 'c'],
        ['a', 'b'],
    ])

    # with buttons any messages can be "popup'-ed as modal
    rc = await menu.popup()

    await titleMsg.show(f'Was selected: {escape_md(rc.data)}')


async def logic_MENU_Simple2(chat: BotChat, name):
    titleMsg = await chat.reply(
        f'Here is another one, *{name}*.\n'
        'But this time you can ONLY choose menu buttons!')

    rc = await chat.menu('Another menu title\nPossible with several lines', [
        ['One in a row'],
        ['One', 'Two', ('Three',)],
        [('Bottom One', 'bottom1'), InlineKeyboardButton('and Two', callback_data='bottom2')],
        [InlineKeyboardButton('And finally a link:', url='to.nowhere.mars')],
    ], remove_unused=True)

    await titleMsg.show(f'Selected button: *{escape_md(rc.data)}*')


async def logic_MENU_Animation(chat: BotChat, name):
    titleMsg = await chat.reply(
        f'Little "animation" example, {name}.\n'
        'Emulates some run actions!')

    nItter = 0

    # answer() can be called JUST AFTER receive, so we need callback less delay in processing
    async def idCB(chat, data: Callback_t) -> bool:
        if data.data.isdigit():
            await data.answer(f'Stats:\nDev1: {counter}\n,Dev2: {counter1}\n,Dev3: {counter2}')
        return True

    # we can use 'with' operation with any message. On exit it will delete self
    async with chat.build('Working devices:', remove_unused=True, on_callback=idCB) as menu:
        counter = 0
        counter1 = 0
        counter1_step = 1
        counter2 = 14232343
        running = True

        # show empty message here to be sure it BEFORE "system" messages
        await menu.show()
        stateMsg = await chat.say('<devices>')
        itemsMsg = await chat.say('<devices snapshot>')

        while True:
            await asyncio.sleep(0.3)

            # do some data change
            nItter += 1
            if running:
                counter += random.randint(0, 100)
                counter1 += counter1_step
                if counter1 > 5: counter1_step = -1
                if counter1 < -5: counter1_step = 1
                counter2 -= random.randint(100, 10000)

            # set new keyboard
            menu.keyboard_inline([
                [(f'Device1: {counter}', 1)],
                [(f'Device2: {abs(counter1)}', 2)],
                [(f'Device3: {counter2}', 3)],
                [('Stop' if running else 'Resume', 'RUN'), ('Reset', 'RESET'), ('<< Close', 'BACK')]
            ])

            # update messages w menu and stats
            await stateMsg.show(f'Devices are: {"Running" if running else "Stopped"} [{nItter}]...')
            await menu.show()

            # check if menu has result
            rc = menu.result
            if not rc.known: continue

            # dispatch thru data from result
            if rc.data in ['1', '2', '3']:
                await itemsMsg.show(
                    f'Stats at __{datetime.datetime.now()}__ was:\n'
                    f'Device1: *{counter}*\n'
                    f'Device2: *{counter1}*\n'
                    f'Device3: *{counter2}*')
            elif rc.data == 'RUN':
                running = not running
            elif rc.data == 'RESET':
                counter = 0
                counter1 = 0
                counter2 = random.randint(0, 10000) * 10000
            elif rc.data == 'BACK':
                break

    await itemsMsg.delete()
    await stateMsg.delete()
    await titleMsg.show(f'Animation demo ended\nIn total *{nItter}* cycle iterations completed')


async def logic_MENU(chat: BotChat, name):
    titleMsg = await chat.reply(
        f'Hi, {name}.\n'
        'Here you can see some usage samples for menus')

    while True:
        rc = await chat.menu(
            'Please select test',
            [
                [('Simple popup', 'simple1'), ('Simple popup with filter', 'simple2')],
                [('Runtime animation test', 'anim')],
                [('Kinda form filler', 'form')],
                [('<< Back', 0)],
            ], remove_unused=True
        )
        if not rc.known: break
        if rc.data == 'simple1':
            await logic_MENU_Simple1(chat, name)
        elif rc.data == 'simple2':
            await logic_MENU_Simple2(chat, name)
        elif rc.data == 'anim':
            await logic_MENU_Animation(chat, name)
        elif rc.data == 'form':
            await logic_MENU_Form(chat, name)
        else:
            break

    titleMsg.text = f'Whats all for MENUs. See you..'
    await titleMsg.show()


async def logic_WAIT(chat: BotChat, name):
    await chat.reply(f'Hi *{name}*!', wait_delay=2)
    await chat.say(f'How are u __{name}__?', wait_delay=1, replace=True)
    await chat.say(f'U know *__{name}__*, Im fine too, thanks!', wait_delay=3, replace=True)
    await chat.say(f'Ure so boring... Lets work when!\nTry to post some text here.', replace=True)

    idle = ['Im bored', 'Boring', 'Still waiting', 'Are u even here??']
    counter = 0
    boring = await chat.say('Up to 5 times')
    while counter < 5:
        reply = False
        if await chat.waitmsg(5):
            counter += 1
            text = f'I heard *{counter}* times:\n*__{chat.last.text}__*'
            reply = random.randint(0, 10) > 5
            await chat.delete()
        else:
            text = f'{random.choice(idle)}...'
        await boring.say(text, reply_to_message_id=chat.last_id if reply else NoMessageId)

    await boring.say(f'Well, you pass this test!')
    await asyncio.sleep(2)
    await boring.say(f'Whats all for WAITing. See you..')


async def logic_ASK(chat: BotChat, name):
    # SIMPLE
    # await chat.say('Simple Question')
    # rc = await chat.popup(
    #     f'\(1\) Select a button, {name}.\n'
    #     f'You can enter messages in chat while I wait for buttons',
    #     keyboard_type=KeyboardType.KEYBOARD,
    #     buttons=[['first', 'second', 'third']],
    # )
    # await chat.say(f'reply1: {rc.data}')
    #
    # # FILTERED SIMPLE
    # await chat.say('Question with filter')

    asker2 = chat.build(
        f'\(2\) Select another button II, *{name}*.\n'
        'This time you cant enter chat messages... will you try to?',
        keyboard_type=KeyboardType.KEYBOARD,
        buttons=[['first', 'second', 'third']]
    )
    bored = chat.build('')

    async def _on_message(chat: BotChat, message: Message_t) -> bool:
        asker2.text = '\(2\) Select another button II.\nI see you trying! 😄'

        v = random.choice([
            'Really?', 'Cant you press a button?', 'Just do it!', 'U cant or you want??',
            'Im bored...', 'Are u stupid or something? ©', 'Ure tough gay!'
        ])
        await bored.say(v)
        return True

    rc = await asker2.popup(on_message=_on_message, remove_unused=True)
    await bored.delete()
    await chat.say(f'reply2: {rc.data}')


async def logic_CALC(chat: BotChat, name):
    await chat.say('We can implement calculator with **callback** processing or in **separate "While"** cycle.',
                   media='data/calc.jpg', )
    isCallback = await chat.askYesNo(
        'Which version do you want to test?',
        buttons=['with Callback', 'with Cycle'],
        remove_unused=True
    ) == IDYES

    # this message used as helper to send symbols.
    keysMsg = await chat.say(
        f'Some complex buttons \({"CALLBACK" if isCallback else "WHILE"} version\)\n'
        f'They can be more complex what u may be thinking...\n'
        f'Try to enter something to calculate',
        keyboard_type=KeyboardType.KEYBOARD,
        placeholder='Enter numbers and signs to calculate',
        buttons=[
            ['close', '<<'],
            ['1', '2', '3', '4', '5'],
            ['6', '7', '8', '9', '0'],
            ['+', '-', '*', '/', '=']
        ])
    # here we will display accumulated formula, result and error
    totalMsg = await chat.say('\(enter formula\)')

    # accumulator
    total = ''

    # Used if user choose "callback" version
    # Called for every message get while popup() working
    # This callback will need to return True to allow further processing, so we filter out all
    # keyboard buttons except "close". Popup will stop after get any known text, so "close" stop it.
    async def idMsg(chat, message) -> bool:
        nonlocal total
        # get last message
        rc = message.text
        # remove it
        await chat.delete(message)

        # "close" is known in our message, so if we allow to process further popup() will stop
        # in all other cases we return False, so popup() will run
        if rc == 'close':
            return True
        elif rc == '=':
            # execute formula
            if len(total):
                try:
                    rc = eval(total)
                    await totalMsg.say(f'Result: {escape_md(rc)}')
                except Exception as e:
                    await totalMsg.say(f'Calculation error!\nError: {escape_md(e.args[0])}')
            total = ''
            # update result on next step to allow to see result
            return False
        elif rc == '<<':
            total = total[0:-1]
        else:
            total += rc
        # update formula
        await totalMsg.say('\(enter formula\)' if not len(total) else f'Formula: *{escape_md(total)}*')
        return False

    if isCallback:
        # in this case all processing will be in on_message callback
        await keysMsg.popup(keysMsg.text, on_message=idMsg)
    else:
        # until 'close' selected or entered from keyboard
        while True:
            # get any input
            await chat.waitmsg()
            # remember it
            rc = chat.last.text
            # del its message
            await chat.delete()

            # do calc
            if rc == 'close':
                break
            elif rc == '=':
                if len(total):
                    try:
                        rc = eval(total)
                        await totalMsg.say(f'Result: {escape_md(rc)}')
                    except Exception as e:
                        await totalMsg.say(f'Calculation error!\nError: {escape_md(e.args[0])}')
                total = ''
                continue
            elif rc == '<<':
                total = total[0:-1]
            else:
                total += rc

            # update total message
            await totalMsg.say('\(enter formula\)' if not len(total) else f'Formula: *{escape_md(total)}*')

    # DONE
    await totalMsg.delete()
    # do not forget to remove keyboard
    await keysMsg.say(f'Whats all in calc. See you..', keyboard_type=KeyboardType.REMOVE)


async def TEST(chat: BotChat, name):
    ikeys = types.InlineKeyboardMarkup()
    ikeys.row(types.InlineKeyboardButton('a', callback_data='a'),
              types.InlineKeyboardButton('b', callback_data='b'))
    ikeys.row(types.InlineKeyboardButton('c', callback_data='c'))

    ikeys1 = types.InlineKeyboardMarkup()
    ikeys1.row(types.InlineKeyboardButton('1', callback_data='a'),
               types.InlineKeyboardButton('2', callback_data='b'))
    ikeys1.row(types.InlineKeyboardButton('3', callback_data='c'))

    kkeys = types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton('A'), types.KeyboardButton('b')]
    ], resize_keyboard=True)

    msg = await chat.bot.send_message(chat.chat_id, 'text', reply_markup=ikeys)
    await chat.waitmsg()
    await chat.bot.edit_message_reply_markup(chat.chat_id, message_id=msg.message_id, reply_markup=ikeys1)
    await chat.waitmsg()
    await chat.bot.edit_message_reply_markup(chat.chat_id, message_id=msg.message_id, reply_markup=ikeys)

    await chat.waitmsg()


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


# ------------------------------------------------------------------------
dp = Dispatcher(Bot(token=readAPIToken('token.api'), parse_mode=PARSE_MARKDOWNV2))
botSession = BotSession(dp, Logic)


@dp.channel_post_handler()
@dp.message_handler()
async def message_handler(message: Message_t):
    await botSession.process_message(message)


@dp.callback_query_handler()
async def callback_handler(cbd: types.CallbackQuery):
    await botSession.process_callback(cbd)

# ------------------------------------------------------------------------
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
    pass
