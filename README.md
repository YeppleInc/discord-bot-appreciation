# Discord Appreciation Bot

This is a Discord bot designed to encourage team member satisfaction, communications, and engagement. This bot facilitates two key features in your Discord server:
1) A weekly "Gold Star" poll that allows channel members to vote for teammates who provided significant contributions during the last week. Once votes have been submitted the admin has the ability to close the poll and the bot will automatically tally the votes and display the winner, runners up, as well as comments provided.
2) The ability to allocate "Kudos Dollars" to channel members for going above and beyond in their work. Dollar allocations begin at $100 and can be awarded in increments of $5. The server admin has the ability to reset the allocations to begin a new period (suggested quarterly). 

## Features

- Send kudos to colleagues
- View kudos received
- Check remaining kudos allocations
- Reset kudos allocations
- Start and manage Gold Star polls

## Commands

### `/kudos`
**Description:** Send kudos to a colleague.

**Usage:** 
/kudos <user> <amount> <message>

- `<user>`: The user to whom you are sending kudos.
- `<amount>`: The amount of kudos (must be between $5 and $100).
- `<message>`: An optional message to accompany the kudos.

### `/view_kudos`
**Description:** View the total kudos, as well as a summary received by all users.

**Usage:** 
/view_kudos

- Displays an embed with users and the total amount of kudos received along with any accompanying messages.

### `/my_allocations`
**Description:** Check your remaining kudos allocations.

**Usage:** 
/my_allocations

- Displays how much "Kudo Dollars" you have left to give. If you haven't given any kudos yet, it initializes your allocation at $100.

### `/reset_kudos`
**Description:** Reset kudos allocations for everyone.

**Usage:** 
/reset_kudos

- Deletes all kudos records and resets each user’s allocations to $100. This command can only be executd by one of the user IDs identified in the ALLOWED_USERS variable.

### `/start_poll`
**Description:** Manually start an anonymous Gold Star poll. Note, this is also configured to automatically start every Monday morning at 6AM EST.

**Usage:** 
/start_poll

- Initiates a poll for the current week, allowing users to vote for their colleagues. The embed includes instructions on how to vote.

### `/vote`
**Description:** Vote for a candidate in the Gold Star poll.

**Usage:** 
/vote <candidate> <comment>

- `<candidate>`: The user you are voting for.
- `<comment>`: An optional comment explaining your vote.

**Note:** You can only vote once per poll.

### `/vote_count`
**Description:** Display the total number of votes received thus for for an open poll.

**Usage:**
/vote_count

-Displays the current vote count of the open poll.

### `/close_poll`
**Description:** Close the Gold Star poll and announce the results.

**Usage:** 
/close_poll

- Closes the current poll, counts the votes, and announces the winner(s) along with any comments submitted.

## How It Works

1. **Database Setup:**
   - The bot uses SQLite databases (`kudos.db` and `polls.db`) to store kudos records, user allocations, and poll statuses.

2. **Kudos Management:**
   - Users can send kudos to colleagues and check their remaining allocations. Each user starts with a $100 allocation which can be spent on kudos.

3. **Poll Management:**
   - A Gold Star poll can be initiated and closed by any user. Votes are collected anonymously, and each user can only vote once per poll.

4. **Comments:**
   - When sending kudos or voting, users add comments that will be stored and displayed in results.

## Getting Started

1. Clone the repository to your local machine.
2. Install the required packages:
```
pip install discord.py sqlite3 apscheduler py-cord
```
4. Create an environmental file (.env) with your Discord bot API, such as:
```
# .env
DISCORD_TOKEN=
```
4. Replace the two variables inside of bot.py with your channel ID and your admin member ID.
5. Create a system service that starts/restarts the bot automatically (modify directory paths or user as necessary):
```
[Unit]
Description=Discord Appreciation Bot
After=network.target

[Service]
User=admin
WorkingDirectory=/home/admin/git/discord-bot-appreciation
ExecStart=/usr/bin/python3 /home/admin/git/discord-bot-appreciation/bot.py
Restart=always
EnvironmentFile=/home/admin/git/discord-bot-appreciation/.env

[Install]
WantedBy=multi-user.target
```
5. Enable and start the bot:
```
systemctl enable discord-appreciation-bot.service
systemctl start discord-appreciation-bot.service
```

## Contributing

Contributions are welcome! Feel free to submit a pull request or open an issue for any enhancements or bug fixes.

## License

This project is licensed under the MIT License.
