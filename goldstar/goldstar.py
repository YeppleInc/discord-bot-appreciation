import sqlite3
import pytz
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import discord
from bot_instance import bot  # Import the bot instance from the separate file
import config

# Command to start an anonymous Gold Star poll
async def start_poll_task():
    conn = sqlite3.connect('goldstar/polls.db')
    cursor = conn.cursor()

    week = datetime.date.today().isocalendar()[1]
    cursor.execute("SELECT is_open FROM poll_status WHERE week = ?", (week,))
    poll_status = cursor.fetchone()

    # Load the poll into a specified channel
    channel = bot.get_channel(config.CHANNEL)  # Get the channel object


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
    if ctx.author.id not in config.ALLOWED_USERS:
        await ctx.respond("You do not have permission to use this command.", ephemeral=True)
        return

    await start_poll_task()
    await ctx.respond("Poll started manually!", ephemeral=True)

# Schedule the poll to start automatically
scheduler = AsyncIOScheduler()
eastern = pytz.timezone('US/Eastern')  # Use the Eastern Time Zone

# Schedule the poll task to run every Sunday at 00:01 EST
scheduler.add_job(start_poll_task, 'cron', day_of_week='mon', hour=6, minute=18, timezone=eastern)

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

    conn = sqlite3.connect('goldstar/polls.db')
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
    conn = sqlite3.connect('goldstar/polls.db')
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
    conn = sqlite3.connect('goldstar/polls.db')
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

