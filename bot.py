import discord
from discord.ext import commands
import sqlite3
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
from dotenv import load_dotenv
import os

#######################################################################################################

# Discord user ID(s) that are allowed to use restricted commands such as resetting kudos allocations
ALLOWED_USERS = [693530583715938306]

# The Discord channel ID that the bot should primarily interact with - this is where the weekly give thanks poll will post
CHANNEL = 1071053186124746863

########################################################################################################


# Initialize the bot
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Create a bot instance with member intents enabled
intents = discord.Intents.default()
intents.members = True  # Make sure to enable member intents
bot = commands.Bot(command_prefix='!', intents=intents)

# Database setup function
def setup_databases():
    # Setup kudos database
    conn = sqlite3.connect('kudos.db')
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

    # Setup polls database
    conn = sqlite3.connect('polls.db')
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

# Kudos command for sending kudos to a colleague
@bot.slash_command(name="kudos", description="Send kudos to a colleague")
async def kudos(ctx: discord.ApplicationContext, user: discord.Member, amount: int, *, message: str):
    # Validate the amount of kudos
    if amount < 5 or amount > 100 or amount % 5 != 0:
        await ctx.respond("Amount must be between $5 and $100, and in multiples of $5.", ephemeral=True)
        return

    conn = sqlite3.connect('kudos.db')
    cursor = conn.cursor()

    # Insert the kudos record into the database
    cursor.execute("INSERT INTO kudos (user_id, received_id, amount, message) VALUES (?, ?, ?, ?)",
                   (ctx.author.id, user.id, amount, message))

    # Update remaining allocation for the user
    cursor.execute("INSERT INTO kudos_allocations (user_id, remaining) VALUES (?, 100) ON CONFLICT(user_id) DO UPDATE SET remaining = remaining - ?",
                   (ctx.author.id, amount))

    conn.commit()

    # Retrieve the remaining allocation
    cursor.execute("SELECT remaining FROM kudos_allocations WHERE user_id = ?", (ctx.author.id,))
    remaining_allowance = cursor.fetchone()[0]

    conn.close()

    # Create and send an embed message for the kudos
    embed = discord.Embed(
        title="Kudos!",
        description=f"🎉 Kudos to {user.mention}!",
        color=discord.Color.green()
    )
    embed.add_field(name="Amount", value=f"${amount}", inline=False)
    embed.add_field(name="Message", value=message, inline=False)
    embed.set_footer(text="Keep up the great work!")

    await ctx.respond(embed=embed)

    # Notify the user in the same channel about their remaining allocation
    await ctx.respond(f"You have ${remaining_allowance} left to give.", ephemeral=True)

# Command to view kudos received by users
@bot.slash_command(name="view_kudos", description="View kudos received")
async def view_kudos(ctx: discord.ApplicationContext):

    conn = sqlite3.connect('kudos.db')
    cursor = conn.cursor()

    # Retrieve total kudos received for each user
    cursor.execute("SELECT received_id, SUM(amount) AS total_amount FROM kudos GROUP BY received_id")
    results = cursor.fetchall()

    # Create an embed to display the kudos received
    embed = discord.Embed(title="Kudos Received", color=discord.Color.blue())

    total_kudos_summary = ""  # String to accumulate the summary of total kudos per user

    for user_id, total_amount in results:
        # Get the messages sent to this user
        cursor.execute("SELECT message FROM kudos WHERE received_id = ?", (user_id,))
        messages = cursor.fetchall()
        message_list = "\n".join(message[0] for message in messages) or "No messages received."

        # Add a bullet symbol before each message
        message_list = "\n".join(f"• {message[0]}" for message in messages) or "No messages received."

        # Fetch the user object using the user ID
        user = await bot.fetch_user(user_id)

        # Add user information to the embed
        embed.add_field(name=user.name, value=f"${total_amount}\nMessages:\n{message_list}", inline=False)

        # Add to the total summary string
        total_kudos_summary += f"{user.name}: ${total_amount}\n"

    # Add a field at the bottom for the summary of totals
    embed.add_field(name="Total Kudos Summary", value=total_kudos_summary, inline=False)

    await ctx.respond(embed=embed, ephemeral=True)
    conn.close()

# Command to check remaining kudos allocations for the user
@bot.slash_command(name="my_allocations", description="View your remaining kudos allocations")
async def my_allocations(ctx: discord.ApplicationContext):
    conn = sqlite3.connect('kudos.db')
    cursor = conn.cursor()
    cursor.execute("SELECT remaining FROM kudos_allocations WHERE user_id = ?", (ctx.author.id,))
    remaining_allowance = cursor.fetchone()
    
    if remaining_allowance:
        await ctx.respond(f"You have ${remaining_allowance[0]} left to give.", ephemeral=True)
    else:
        # If not found, insert a new entry for the user with 100 allocations
        cursor.execute("INSERT INTO kudos_allocations (user_id, remaining) VALUES (?, 100)", (ctx.author.id,))
        conn.commit()
        await ctx.respond("You have $100 left to give.", ephemeral=True)
    
    conn.close()

# Command to reset kudos allocations for everyone
@bot.slash_command(name="reset_kudos", description="Reset kudos allocations for everyone")
async def reset_kudos(ctx: discord.ApplicationContext):

    if ctx.author.id not in ALLOWED_USERS:
        await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        return

    conn = sqlite3.connect('kudos.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM kudos")
    cursor.execute("DELETE FROM kudos_allocations")
    cursor.execute("INSERT INTO kudos_allocations (user_id, remaining) SELECT user_id, 100 FROM kudos_allocations")
    conn.commit()
    conn.close()
    await ctx.respond("Kudos allocations have been reset!", ephemeral=True)

# Command to start an anonymous Gold Star poll
async def start_poll_task():
    conn = sqlite3.connect('polls.db')
    cursor = conn.cursor()

    week = datetime.date.today().isocalendar()[1]
    cursor.execute("SELECT is_open FROM poll_status WHERE week = ?", (week,))
    poll_status = cursor.fetchone()

    # Load the poll into a specified channel
    channel = bot.get_channel(CHANNEL) 

    if channel is None:
        print(f"Error: Could not find channel.")
        return

    if poll_status and poll_status[0]:
        await channel.send("There is already an open poll.")
        conn.close()
        return

    await channel.send("@everyone")

    # Create the poll embed with instructions
    embed = discord.Embed(
        title="Gold Star Vote!",
        description="Happy Monday! Vote for someone to receive the Gold Star for their hard work last week.",
        color=discord.Color.gold()
    )
    embed.add_field(name="How to Vote", value="Use `/vote <user> <your comment>` to cast your vote.", inline=False)

    if poll_status is None:
        cursor.execute("INSERT INTO poll_status (week, is_open) VALUES (?, ?)", (week, True))
    else:
        cursor.execute("UPDATE poll_status SET is_open = ? WHERE week = ?", (True, week))

    conn.commit()
    conn.close()

    await channel.send(embed=embed)

# Command to start poll manually
@bot.slash_command(name="start_poll", description="Start an anonymous Gold Star poll")
async def start_poll(ctx: discord.ApplicationContext):
    if ctx.author.id not in ALLOWED_USERS:
        await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        return
    
    await start_poll_task()
    await ctx.respond("Poll started manually!", ephemeral=True)

# Schedule the poll to start automatically
scheduler = AsyncIOScheduler()
eastern = pytz.timezone('US/Eastern')  # Use the Eastern Time Zone

# Schedule the poll task to run every Sunday at 00:01 EST
scheduler.add_job(start_poll_task, 'cron', day_of_week='mon', hour=6, minute=00, timezone=eastern)

# Start the scheduler
scheduler.start()

# Command to vote for a candidate in the Gold Star poll
@bot.slash_command(name="vote", description="Vote for a candidate in the Gold Star poll")
async def vote(ctx: discord.ApplicationContext, candidate: discord.Member, comment: str):

    # Fetch the members of the current channel
    members = ctx.channel.members

    # Check if the chosen candidate is a valid member of the channel
    if candidate not in members:
        await ctx.respond("You can only vote for members of this channel!", ephemeral=True)
        return

    conn = sqlite3.connect('polls.db')
    cursor = conn.cursor()

    week = datetime.date.today().isocalendar()[1]

    # Check if the poll is open
    cursor.execute("SELECT is_open FROM poll_status WHERE week = ?", (week,))
    poll_status = cursor.fetchone()

    if not poll_status or not poll_status[0]:
        await ctx.respond("The poll is not currently open.", ephemeral=True)
        conn.close()
        return

    # Check if the user has already voted
    cursor.execute("SELECT user_id FROM votes WHERE week = ? AND user_id = ?", (week, ctx.author.id))
    already_voted = cursor.fetchone()

    if already_voted:
        await ctx.respond("You have already voted in this poll.", ephemeral=True)
        conn.close()
        return

    # Insert the vote into the database
    cursor.execute("INSERT INTO votes (week, user_id, candidate_id, comment) VALUES (?, ?, ?, ?)",
                   (week, ctx.author.id, candidate.id, comment))
    
    conn.commit()
    conn.close()

    await ctx.respond(f"Your vote for {candidate.mention} has been recorded!", ephemeral=True)

@bot.slash_command(name="vote_count", description="Tally number of votes for current open poll")
async def vote_count(ctx: discord.ApplicationContext):
    conn = sqlite3.connect('polls.db')
    cursor = conn.cursor()

    week = datetime.date.today().isocalendar()[1]

    # Check if the poll is open
    cursor.execute("SELECT is_open FROM poll_status WHERE week = ?", (week,))
    poll_status = cursor.fetchone()

    if not poll_status or not poll_status[0]:
        await ctx.respond("The poll is not currently open.", ephemeral=True)
        conn.close()
        return

    cursor.execute("SELECT COUNT(*) FROM votes WHERE week = ?", (week,))

    # Fetch the vote tally from the cursor
    vote_tally = cursor.fetchall()[0]

    vote_tally_str = "\n".join([str(vote) for vote in vote_tally])

    # Send the formatted string in the response
    await ctx.respond(f"Current vote tally:\n{vote_tally_str}", ephemeral=True)

    conn.close()

# Command to close the Gold Star poll and announce results
@bot.slash_command(name="close_poll", description="Close the Gold Star poll and announce results")
async def close_poll(ctx: discord.ApplicationContext):
    conn = sqlite3.connect('polls.db')
    cursor = conn.cursor()

    week = datetime.date.today().isocalendar()[1]

    # Check if the poll is open
    cursor.execute("SELECT is_open FROM poll_status WHERE week = ?", (week,))
    poll_status = cursor.fetchone()

    if not poll_status or not poll_status[0]:
        await ctx.respond("The poll is not currently open.", ephemeral=True)
        conn.close()
        return

    # Count votes
    cursor.execute("SELECT candidate_id, COUNT(*) as vote_count FROM votes WHERE week = ? GROUP BY candidate_id", (week,))
    vote_counts = cursor.fetchall()

    # Get all comments submitted
    cursor.execute("SELECT comment FROM votes WHERE week = ?", (week,))
    comments = cursor.fetchall()
    comments_list = "\n".join(f"• {comment[0]}" for comment in comments) or "No comments submitted."

    if vote_counts:
        max_votes = max(vote_count for _, vote_count in vote_counts)
        winners = [user_id for user_id, vote_count in vote_counts if vote_count == max_votes]

        # Determine runners up
        runner_up_candidates = [(user_id, vote_count) for user_id, vote_count in vote_counts if max_votes > vote_count > 0]
        runners_up = []

        if runner_up_candidates:
            runner_up_votes = max(vote_count for user_id, vote_count in runner_up_candidates)
            runners_up = [user_id for user_id, vote_count in runner_up_candidates if vote_count == runner_up_votes]

        # Prepare winner and runner-up mentions
        winner_mentions = ", ".join(f"<@{winner}>" for winner in winners)
        runner_up_mentions = ", ".join(f"<@{runner}>" for runner in runners_up)

        # Create the results embed
        embed = discord.Embed(
            title="Gold Star Results!",
            description=f"Congrats to {winner_mentions} for this week's Gold Star ⭐!",
            color=discord.Color.green()
        )

        if runners_up:
            embed.add_field(name="Runners Up", value=runner_up_mentions, inline=False)

        # Add comments to the embed
        embed.add_field(name="Comments Submitted", value=comments_list, inline=False)

        await ctx.respond(embed=embed)
    else:
        await ctx.respond("No votes were cast. The poll has been closed.", ephemeral=True)

    # Reset the poll in the database
    cursor.execute("UPDATE poll_status SET is_open = ? WHERE week = ?", (False, week))
    cursor.execute("DELETE FROM votes WHERE week = ?", (week,))
    conn.commit()
    conn.close()

# Run the bot
bot.run(TOKEN)
