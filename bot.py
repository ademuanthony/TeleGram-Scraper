import os
import json
import enum
import time
import csv
import jsonpickle
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import filters, ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty, InputPeerUser
from telethon.errors.rpcerrorlist import PeerFloodError

re = "\033[1;31m"
gr = "\033[1;32m"
cy = "\033[1;36m"
SLEEP_TIME = 30

load_dotenv()

TOKEN = os.getenv("TOKEN")

# OPERATION DEFINITION


class Operation(enum.Enum):
    Nothing = 0
    AddAccountPhoneNumber = 1
    APIID = 2
    AddAccountHash = 3
    SessionCode = 4
    ViewGroup_send_code_request = 5
    ChooseGroup_to_scrap = 6
    ChooseGroup_to_send_sms = 7
    EnterMessage = 8
    SendSMS_send_code_request = 9


def readJsonFile(filePath):
    with open(filePath, "r") as book:
        return json.load(book)


def getAccounts(userId):
    accountsFile = f'data/{userId}/accounts.json'
    if os.path.exists(accountsFile) is False:
        return []
    accounts = readJsonFile(accountsFile)
    if accounts is None:
        accounts = []
    return accounts


def saveAccounts(userId, data):
    filePath = f"data/{userId}/accounts.json"
    with open(filePath, "w") as book:
        json.dump(data, book, indent=2)


def getGroups(userId):
    accountsFile = f'data/{userId}/groups.json'
    if os.path.exists(accountsFile) is False:
        return []
    accounts = readJsonFile(accountsFile)
    if accounts is None:
        accounts = []
    return accounts


def saveGroups(userId, data):
    filePath = f"data/{userId}/groups.json"
    with open(filePath, "w") as book:
        content = jsonpickle.encode(data)
        book.write(content)


def getCurrentOperation(userId):
    filePath = f"data/{userId}/currentOperation.txt"
    if os.path.exists(filePath) is False:
        return None
    with open(filePath, encoding='UTF8') as f:
        content = f.read()
        return Operation[content]


def saveCurrentOperation(userId, op: Operation):
    filePath = f"data/{userId}/currentOperation.txt"
    with open(filePath, 'w') as f:
        f.write(op.name)


def getPhoneCodeHash(userId):
    filePath = f"data/{userId}/phoneCodeHash.txt"
    if os.path.exists(filePath) is False:
        return None
    with open(filePath, encoding='UTF8') as f:
        return f.read()

def savePhoneCodeHash(userId, code):
    filePath = f"data/{userId}/phoneCodeHash.txt"
    with open(filePath, 'w') as f:
        f.write(code)

def saveCurrentMsgFileName(userId, fileName):
    filePath = f"data/{userId}/saveCurrentMsgFileName.txt"
    with open(filePath, 'w') as f:
        f.write(fileName)

def getCurrentMsgFileName(userId):
    filePath = f"data/{userId}/saveCurrentMsgFileName.txt"
    if os.path.exists(filePath) is False:
        return None
    with open(filePath, encoding='UTF8') as f:
        return f.read()

def getpendingNewAccount(userId):
    filePath = f"data/{userId}/pendingNewAccount.json"
    if os.path.exists(filePath) is False:
        return {}
    with open(filePath, 'r') as f:
        return json.load(f)


def savePendingNewAccount(userId, data):
    filePath = f"data/{userId}/pendingNewAccount.json"
    with open(filePath, "w") as book:
        json.dump(data, book, indent=2)

def ensurePaths(userId):
    path = f"data/{userId}"
    if os.path.exists(path) == False:
        os.makedirs(path)
    
    path = f"data/members"
    if os.path.exists(path) == False:
        os.makedirs(path)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ensurePaths(update.message.from_user.id)
    msg = """
    Welcome to Atakoya!

    What do you want to do

    /viewAccounts to view your configured accounts
    /addAccount to add a new account
    /removeAccount <phone number> to remove an account
    /viewGroups to view the groups you have/can scrapped
    /sendMessage to send SMS
    """

    await context.bot.send_message(chat_id=update.message.chat_id, text=msg)


async def viewAccounts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    userId = update.message.from_user.id

    accounts = getAccounts(userId)
    if len(accounts) == 0:
        msg = "You have not added any account. Use /addAccount to add"
        await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
        return

    msg = f"Here is a list of all your accounts\n\n"
    for acc in accounts:
        accountDetails = f"Phone Number:\t\t\t {acc['phoneNumber']} \n ID:\t\t\t {acc['appApiId']}"
        msg = f"{msg} \n{accountDetails}"

    await context.bot.send_message(chat_id=update.message.chat_id, text=msg)


async def addAccount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    userId = update.message.from_user.id
    saveCurrentOperation(userId, Operation.AddAccountPhoneNumber)

    msg = "Please enter the phone in international formation e.g. +1xxxxxx"
    await context.bot.send_message(chat_id=update.message.chat_id, text=msg)


async def processNewAccountField(update: Update, context: ContextTypes.DEFAULT_TYPE, dataKey, nextLabel):
    phone = update.message.text
    userId = update.message.from_user.id
    data = getpendingNewAccount(userId)
    data[dataKey] = phone
    savePendingNewAccount(userId, data)
    msg = f"Please enter the App {nextLabel} gotted from my.telegram.org"
    if nextLabel is None:
        return
    await context.bot.send_message(chat_id=update.message.chat_id, text=msg)


async def fetchGroups(client):
    chats = []
    last_date = None
    chunk_size = 200
    groups = []

    result = await client(GetDialogsRequest(
        offset_date=last_date,
        offset_id=0,
        offset_peer=InputPeerEmpty(),
        limit=chunk_size,
        hash=0
    ))
    chats.extend(result.chats)

    for chat in chats:
        try:
            if chat.megagroup == True:
                groups.append(chat)
        except:
            continue

    return groups

async def viewGroups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    userId = update.message.from_user.id
    accounts = getAccounts(userId)
    if accounts is None or len(accounts) == 0:
        msg = "You've not added any account. Please /addAccount to continue"
        await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
        return

    account = accounts[0]
    client = TelegramClient(
        account["phoneNumber"], account["appApiId"], account["appApiHash"])
    await client.connect()
    if not await client.is_user_authorized():
        resp = await client.send_code_request(account["phoneNumber"])
        savePhoneCodeHash(userId, resp.phone_code_hash)
        msg = "Enter your login code"
        await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
        saveCurrentOperation(userId, Operation.ViewGroup_send_code_request)
        return

    groups = await fetchGroups(client)

    saveGroups(userId, groups)
    msg = 'Choose a group to scrap members :'
    saveCurrentOperation(userId, Operation.ChooseGroup_to_scrap)
    i = 0
    for g in groups:
        msg = f'{msg}\n[{i}] - {g.title}'
        i += 1

    msg = f'{msg}\n [+] Enter a Number : '
    await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
    client.disconnect()

async def signInAndViewGroup(update, context) -> None:
    userId = update.message.from_user.id
    accounts = getAccounts(userId)
    if accounts is None or len(accounts) == 0:
        msg = "You've not added any account. Please /addAccount to continue"
        await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
        return

    account = accounts[0]
    client = TelegramClient(
        account["phoneNumber"], account["appApiId"], account["appApiHash"])
    await client.connect()
    phone_code_hash = getPhoneCodeHash(userId)
    user = await client.sign_in(phone=account["phoneNumber"], code=update.message.text, phone_code_hash=phone_code_hash)
    print(user)
    saveCurrentOperation(userId, Operation.Nothing)
    client.disconnect()
    await viewGroups(update, context)

async def signInAndSendSMS(update, context) -> None:
    userId = update.message.from_user.id
    accounts = getAccounts(userId)
    if accounts is None or len(accounts) == 0:
        msg = "You've not added any account. Please /addAccount to continue"
        await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
        return

    account = accounts[0]
    client = TelegramClient(
        account["phoneNumber"], account["appApiId"], account["appApiHash"])
    await client.connect()
    phone_code_hash = getPhoneCodeHash(userId)
    user = await client.sign_in(phone=account["phoneNumber"], code=update.message.text, phone_code_hash=phone_code_hash)
    print(user)
    saveCurrentOperation(userId, Operation.Nothing)
    client.disconnect()
    await sendSms(update, context)

async def processChooseGroupToScrap(update, context) -> None:
    try:
        userId = update.message.from_user.id
        accounts = getAccounts(userId)
        if accounts is None or len(accounts) == 0:
            msg = "You've not added any account. Please /addAccount to continue"
            await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
            return

        account = accounts[0]
        client = TelegramClient(
            account["phoneNumber"], account["appApiId"], account["appApiHash"])
        await client.connect()
        groups = await fetchGroups(client)

        index = int(update.message.text)
        if index < 0 or index >= len(groups):
            msg = f"Invalid index. Please enter a number between 0 and {len(groups)-1}"
            await context.bot.send_message(chat_id=update.message.chat_id, text=msg)

        msg = 'Fetching Members...'
        await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
        time.sleep(1)
        target_group = groups[index]
        all_participants = []
        all_participants = await client.get_participants(
            target_group, aggressive=True)

        msg = "Saving In file..."
        await context.bot.send_message(chat_id=update.message.chat_id, text=msg)

        time.sleep(1)
        count = 0
        with open(f"data/members/{target_group.username}.csv", "w", encoding='UTF-8') as f:
            writer = csv.writer(f, delimiter=",", lineterminator="\n")
            writer.writerow(
                ['username', 'user id', 'access hash', 'name', 'group', 'group id'])
            for user in all_participants:
                if user.username:
                    username = user.username
                else:
                    username = ""
                if user.first_name:
                    first_name = user.first_name
                else:
                    first_name = ""
                if user.last_name:
                    last_name = user.last_name
                else:
                    last_name = ""
                name = (first_name + ' ' + last_name).strip()
                writer.writerow([username, user.id, user.access_hash,
                                name, target_group.title, target_group.id])
                count += 1
        msg = f'[+] {count} Members scraped successfully.'
        await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
        client.disconnect()

    except Exception as e:
        print(e)
        msg = "Something went wrong, please enter the index number of the group that you want to scrap"
        await context.bot.send_message(chat_id=update.message.chat_id, text=msg)

async def sendSms(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    userId = update.message.from_user.id
    accounts = getAccounts(userId)
    if accounts is None or len(accounts) == 0:
        msg = "You've not added any account. Please /addAccount to continue"
        await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
        return

    account = accounts[0]
    client = TelegramClient(
        account["phoneNumber"], account["appApiId"], account["appApiHash"])
    await client.connect()
    if not await client.is_user_authorized():
        resp = await client.send_code_request(account["phoneNumber"])
        savePhoneCodeHash(userId, resp.phone_code_hash)
        msg = "Enter your login code"
        await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
        saveCurrentOperation(userId, Operation.SendSMS_send_code_request)
        return

    groups = await fetchGroups(client)

    saveGroups(userId, groups)
    msg = 'Choose a group to scrap members :'
    saveCurrentOperation(userId, Operation.ChooseGroup_to_send_sms)
    i = 0
    for g in groups:
        msg = f'{msg}\n[{i}] - {g.title}'
        i += 1

    msg = f'{msg}\n [+] Enter a Number : '
    await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
    client.disconnect()

async def processChooseGroupToSendSMS(update, context) -> None:
    try:
        userId = update.message.from_user.id
        accounts = getAccounts(userId)
        if accounts is None or len(accounts) == 0:
            msg = "You've not added any account. Please /addAccount to continue"
            await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
            return

        account = accounts[0]
        client = TelegramClient(
            account["phoneNumber"], account["appApiId"], account["appApiHash"])
        await client.connect()
        msg = 'Fetching Group info...'
        await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
        groups = await fetchGroups(client)

        index = int(update.message.text)
        if index < 0 or index >= len(groups):
            msg = f"Invalid index. Please enter a number between 0 and {len(groups)-1}"
            await context.bot.send_message(chat_id=update.message.chat_id, text=msg)

        time.sleep(1)
        target_group = groups[index]

        input_file = f"data/members/{target_group.username}.csv"
        saveCurrentMsgFileName(userId, input_file)
        msg = '[+] Enter Your Message : '
        await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
        saveCurrentOperation(userId, Operation.EnterMessage)
        client.disconnect()
    except Exception as e:
        print(e)

async def processEnterMessageToSendSMS(update, context) -> None:
    try:
        userId = update.message.from_user.id
        input_file = getCurrentMsgFileName(userId)
        if input_file is None:
            sendSms(update, context)
            return
        
        accounts = getAccounts(userId)
        if accounts is None or len(accounts) == 0:
            msg = "You've not added any account. Please /addAccount to continue"
            await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
            return

        account = accounts[0]
        client = TelegramClient(
            account["phoneNumber"], account["appApiId"], account["appApiHash"])
        await client.connect()

        users = []
        with open(input_file, encoding='UTF-8') as f:
            rows = csv.reader(f,delimiter=",",lineterminator="\n")
            next(rows, None)
            for row in rows:
                user = {}
                user['username'] = row[0]
                user['id'] = int(row[1])
                user['access_hash'] = int(row[2])
                user['name'] = row[3]
                users.append(user)
        mode = 2
        message = update.message.text

        for user in users:
            if mode == 2:
                if user['username'] == "":
                    continue
                receiver = await client.get_input_entity(user['username'])
            elif mode == 1:
                receiver = InputPeerUser(user['id'],user['access_hash'])
            else:
                msg = "[!] Invalid Mode. Exiting."
                client.disconnect()
                await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
                return
            try:
                msg = "[+] Sending Message to: "+ user['name']
                await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
                await client.send_message(receiver, message.format(user['name']))
                msg = "[+] Waiting {} seconds".format(SLEEP_TIME)
                await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
                time.sleep(SLEEP_TIME)
            except PeerFloodError:
                msg = "[!] Getting Flood Error from telegram. \n[!] Script is stopping now. \n[!] Please try again after some time."
                await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
                client.disconnect()
                return
            except Exception as e:
                print(re+"[!] Error:", e)
                print(re+"[!] Trying to continue...")
                continue
        client.disconnect()
        msg = 'Done. Message sent to all users.'
        await context.bot.send_message(chat_id=update.message.chat_id, text=msg)
    except Exception as e:
        print(e)
        return

async def processResponse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    userId = update.message.from_user.id
    op = getCurrentOperation(userId)
    if op == Operation.AddAccountPhoneNumber:
        await processNewAccountField(update, context, "phoneNumber", "Api_id")
        saveCurrentOperation(userId, Operation.APIID)
    elif op == Operation.APIID:
        await processNewAccountField(update, context, "appApiId", "Api_hash")
        saveCurrentOperation(userId, Operation.AddAccountHash)
    elif op == Operation.AddAccountHash:
        await processNewAccountField(update, context, "appApiHash", None)
        data = getpendingNewAccount(userId)
        accounts = getAccounts(userId)
        accounts.append(data)
        saveAccounts(userId, accounts)
        await viewAccounts(update, context)
    elif op == Operation.ViewGroup_send_code_request:
        await signInAndViewGroup(update, context)
    elif op == Operation.SendSMS_send_code_request:
        await signInAndSendSMS(update, context)
    elif op == Operation.ChooseGroup_to_scrap:
        await processChooseGroupToScrap(update, context)
    elif op == Operation.ChooseGroup_to_send_sms:
        await processChooseGroupToSendSMS(update, context)
    elif op == Operation.EnterMessage:
        await processEnterMessageToSendSMS(update, context)

app = ApplicationBuilder().token(TOKEN).build()

echo_handler = MessageHandler(
    filters.TEXT & (~filters.COMMAND), processResponse)

app.add_handler(echo_handler)
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("viewAccounts", viewAccounts))
app.add_handler(CommandHandler("addAccount", addAccount))
app.add_handler(CommandHandler("viewGroups", viewGroups))
app.add_handler(CommandHandler("sendMessage", sendSms))

print("bot is starting")
app.run_polling()
