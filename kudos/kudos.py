import sqlite3
import discord
from bot_instance import bot  # Import the bot instance from the separate file
import config

# Kudos command for sending kudos to a colleague
@bot.slash_command(name="kudos", description="Send kudos to a colleague")
async def kudos(ctx: discord.ApplicationContext, user: discord.Member, amount: int, *, message: str):
    # Validate the amount of kudos
    if amount < 5 or amount > 100 or amount % 5 != 0:
        await ctx.respond("Amount must be between $5 and $100, and in multiples of $5.", ephemeral=True)
        return

    conn = sqlite3.connect('kudos/kudos.db')
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

    conn = sqlite3.connect('kudos/kudos.db')
    cursor = conn.cursor()

    # Retrieve total kudos received for each user
    cursor.execute("SELECT received_id, SUM(amount) AS total_amount FROM kudos GROUP BY received_id")
    results = cursor.fetchall()

    # Create an embed to display the kudos received
    embed = discord.Embed(title="Kudos Received", color=discord.Color.blue())

    total_kudos_summary = ""  # String to accumulate the summary of total kudos per user

    def split_long_message(message, limit=1024):
        """Splits a message into chunks of the specified character limit."""
        return [message[i:i+limit] for i in range(0, len(message), limit)]

    for user_id, total_amount in results:
        # Get the messages sent to this user
        cursor.execute("SELECT message FROM kudos WHERE received_id = ?", (user_id,))
        messages = cursor.fetchall()

        # Add a bullet symbol before each message
        message_list = "\n".join(f"• {message[0]}" for message in messages) or "No messages received."

        # Fetch the user object using the user ID
        user = await bot.fetch_user(user_id)

        # Combine the user name and total amount, making sure it fits within the character limit
        base_message = f"${total_amount}\nMessages:\n"

        # Ensure that we split the total content of the field within the limit of 1024 characters
        if len(base_message) + len(message_list) > 1024:
            message_chunks = split_long_message(message_list, 1024 - len(base_message))  # Adjust split limit
            for idx, chunk in enumerate(message_chunks):
                field_name = f"{user.name} (Part {idx + 1})" if len(message_chunks) > 1 else user.name
                embed.add_field(name=field_name, value=base_message + chunk, inline=False)
        else:
            # If it's small enough, add as one field
            embed.add_field(name=user.name, value=base_message + message_list, inline=False)

        # Add to the total summary string
        total_kudos_summary += f"{user.name}: ${total_amount}\n"

    # Ensure total_kudos_summary does not exceed 1024 characters
    if len(total_kudos_summary) > 1024:
        summary_chunks = split_long_message(total_kudos_summary)
        for idx, chunk in enumerate(summary_chunks):
            field_name = f"Total Kudos Summary (Part {idx + 1})" if len(summary_chunks) > 1 else "Total Kudos Summary"
            embed.add_field(name=field_name, value=chunk, inline=False)
    else:
        embed.add_field(name="Total Kudos Summary", value=total_kudos_summary, inline=False)

    await ctx.respond(embed=embed, ephemeral=True)
    conn.close()

# Command to check remaining kudos allocations for the user
@bot.slash_command(name="my_allocations", description="View your remaining kudos allocations")
async def my_allocations(ctx: discord.ApplicationContext):
    conn = sqlite3.connect('kudos/kudos.db')
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

    conn = sqlite3.connect('kudos/kudos.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM kudos")
    cursor.execute("DELETE FROM kudos_allocations")
    cursor.execute("INSERT INTO kudos_allocations (user_id, remaining) SELECT user_id, 100 FROM kudos_allocations")
    conn.commit()
    conn.close()
    await ctx.respond("Kudos allocations have been reset!", ephemeral=True)

