import discord
import os
import json
from discord.ext import commands

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Load config 
with open('config.json', 'r') as file:
    config = json.load(file)

version = "0.1"
token = config["token"]
botColour = config["bot_colour"]
botColourInt = int(botColour, 16)
intents = discord.Intents.all()

client = commands.Bot(command_prefix="!", help_command=None, intents=intents)

print(bcolors.HEADER + "Logging in || Bot running version " + version + bcolors.ENDC)

tree = client.tree

# Triggers when the bot is 'ready'/logged in  
@client.event
async def on_ready():
    print(bcolors.OKGREEN + 'We have logged in as {0.user}'.format(client) + bcolors.ENDC)
    
    # Loading all cogs
    print(bcolors.HEADER + "Loading extensions" + bcolors.ENDC)

    for filename in os.listdir('./cogs'):
      if filename.endswith('.py'):
        await client.load_extension(f'cogs.{filename[:-3]}')
        print(bcolors.OKBLUE + filename + " loaded" + bcolors.ENDC)

    print(bcolors.OKGREEN + "Extensions Loaded" + bcolors.ENDC)

    # await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='you '+ config('PREFIX') +'rtd | v' + version))
    await tree.sync()

client.run(token)