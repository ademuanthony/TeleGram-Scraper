import os
import json
import enum
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import filters, ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes

load_dotenv()

TOKEN = os.getenv("TOKEN")

# OPERATION DEFINITION
class Operation(enum.Enum):
    AddAccountPhoneNumber = 1
    APIID = 2
    AddAccountHash = 3
    SessionCode = 4

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = """
    Welcome to Atakoya!

    What do you want to do

    /viewAccounts to view your configured accounts
    /addAccount to add a new account
    /removeAccount <phone number> to remove an account
    /viewGroups to view the groups you have scrapped
    /addGroup to add a new group
    /removeGroup <group id> to remvove a group
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
        viewAccounts(update, context)

app = ApplicationBuilder().token(TOKEN).build()
 
echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), processResponse)
    
app.add_handler(echo_handler)
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("viewAccounts", viewAccounts))
app.add_handler(CommandHandler("addAccount", addAccount))

print("bot is starting")
app.run_polling()
