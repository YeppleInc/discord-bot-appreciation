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

    def split_long_message(message, limit=1024):
        """Splits a message into chunks of the specified character limit."""
        return [message[i:i + limit] for i in range(0, len(message), limit)]

    # List to store embeds
    embeds = []

    current_embed = discord.Embed(title="Kudos Received", color=discord.Color.blue())
    current_size = len(current_embed.title)  # Start with the size of the title

    for user_id, total_amount in results:
        # Get the messages sent to this user
        cursor.execute("SELECT message FROM kudos WHERE received_id = ?", (user_id,))
        messages = cursor.fetchall()

        # Add a bullet symbol before each message
        message_list = "\n".join(f"• {message[0]}" for message in messages) or "No messages received."

        # Fetch the user object using the user ID
        user = await bot.fetch_user(user_id)

        # Create the field content
        base_message = f"${total_amount}\nMessages:\n"
        total_content = base_message + message_list

        # If adding this field exceeds the 6000-character limit, create a new embed
        if current_size + len(total_content) > 6000:
            embeds.append(current_embed)
            current_embed = discord.Embed(title="Kudos Received (Continued)", color=discord.Color.blue())
            current_size = len(current_embed.title)

        # If a single field content exceeds 1024 characters, split it
        if len(total_content) > 1024:
            chunks = split_long_message(message_list, 1024 - len(base_message))
            for idx, chunk in enumerate(chunks):
                field_name = f"{user.name} (Part {idx + 1})" if len(chunks) > 1 else user.name
                current_embed.add_field(name=field_name, value=base_message + chunk, inline=False)
                current_size += len(field_name) + len(base_message) + len(chunk)
        else:
            current_embed.add_field(name=user.name, value=total_content, inline=False)
            current_size += len(user.name) + len(total_content)

    # Append the last embed
    embeds.append(current_embed)

    # Send each embed separately
    for embed in embeds:
        await ctx.respond(embed=embed, ephemeral=True)

    conn.close()


# Command to check remaining kudos allocations for the user
@bot.slash_command(name="my_allocations", description="View your remaining kudos allocations")
async def my_allocations(ctx: discord.ApplicationContext):
    conn = sqlite3.connect('kudos/kudos.db')
    cursor = conn.cursor()
    
    # Check remaining kudos allowance
    cursor.execute("SELECT remaining FROM kudos_allocations WHERE user_id = ?", (ctx.author.id,))
    remaining_allowance = cursor.fetchone()

    # Prepare the response for remaining allowance
    if remaining_allowance:
        allowance_message = f"You have ${remaining_allowance[0]} left to give."
    else:
        # If not found, insert a new entry for the user with 100 allocations
        cursor.execute("INSERT INTO kudos_allocations (user_id, remaining) VALUES (?, 100)", (ctx.author.id,))
        conn.commit()
        allowance_message = "You have $100 left to give."

    # Retrieve summary of kudos given by this user
    cursor.execute("""
        SELECT received_id, SUM(amount) 
        FROM kudos 
        WHERE user_id = ? 
        GROUP BY received_id
    """, (ctx.author.id,))
    kudos_given = cursor.fetchall()

    # Format the summary of kudos given
    if kudos_given:
        summary_message = "Kudos you've given:\n" + "\n".join(
            f"• <@{received_id}>: ${total_amount}" for received_id, total_amount in kudos_given
        )
    else:
        summary_message = "You haven't given any kudos yet."

    # Combine both messages and send the response
    await ctx.respond(f"{allowance_message}\n\n{summary_message}", ephemeral=True)

    conn.close()

# Command to reset kudos allocations for everyone
@bot.slash_command(name="reset_kudos", description="Reset kudos allocations for everyone")
async def reset_kudos(ctx: discord.ApplicationContext):

    if ctx.author.id not in config.ALLOWED_USERS:
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

