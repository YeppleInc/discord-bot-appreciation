import discord
from discord.ext import commands
import sqlite3
from dotenv import load_dotenv
import os
import config
from bot_instance import bot  # Import the bot instance from the separate file

if config.ENABLE_KUDOS:
    import kudos.kudos

if config.ENABLE_GOLDSTAR:
    import goldstar.goldstar

# Initialize the bot using the token in the .env file
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Create a bot instance with member intents enabled
intents = discord.Intents.default()
intents.members = True

# Database setup function
def setup_databases():

    if config.ENABLE_KUDOS:
        # Setup kudos database
        conn = sqlite3.connect('kudos/kudos.db')
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kudos (
                user_id INTEGER,
                received_id INTEGER,
                amount INTEGER,
                message TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kudos_allocations (
                user_id INTEGER PRIMARY KEY,
                remaining INTEGER DEFAULT 100
            )
        ''')
        conn.commit()
        conn.close()

    if config.ENABLE_GOLDSTAR:
        # Setup polls database
        conn = sqlite3.connect('goldstar/polls.db')
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS poll_status (
                week INTEGER PRIMARY KEY,
                is_open BOOLEAN
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS votes (
                week INTEGER,
                user_id INTEGER,
                candidate_id INTEGER,
                comment TEXT
            )
        ''')
        conn.commit()
        conn.close()

# Initialize databases
setup_databases()

@bot.event
async def on_ready():
    # Log a message when the bot is ready
    print(f'Logged in as {bot.user}!')

# Run the bot
bot.run(TOKEN)

