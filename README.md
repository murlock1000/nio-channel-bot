# Nio-channel-bot for replicating a Telegram channel.
[![Built with nio-template](https://img.shields.io/badge/built%20with-nio--template-brightgreen)](https://github.com/anoadragon453/nio-template)

Matrix bot that replicates the functionality of a Telegram channel.

Features:

* Messages to the room the bot is in are filtered by criteria:
  * If the sender has power level < 50
  * The message is not a thread reply.
* Warning message is sent to a DM room.
* If an existing DM room is not found - a new one is created.
* Messages to a newly created DM room are buffered, until client state receives the room data.
* After 3 attempts the user is muted.
* User is informed about the ban and is provided with the usernames of the room admins.

## Getting started

See [SETUP.md](SETUP.md) for how to setup and run the project.

## Usage

This bot is designed to redact messages (remove them) if:
* the user that posted it is not an admin/moderator of the room and his message is not a thread reply.
* I.E. if it's a regular message/regular reply - gets deleted. Messages made in threads are allowed.
* When a user gets his message deleted - the bot creates/uses an existing DM room and informs the user about his attempt. Also increases the attempt count in the database.
 After 3 attempts (3 message deletions) - the bot mutes (changes power level to -1) the user and resets the attempt count.

To setup the bot you must:
* Invite the bot to a group channel
* Give the bot moderator power level (50)

In order to allow the bot to mute people:
* Change Roles&Permissions: allow 'Change permissions' to Moderator 

In order to allow the bot to remove messages:
* allow 'Remove messages sent by others' to Moderator

Invite the bot to your room and wait for it to join it. The bot will automatically start tracking newly opened matrix polls and display live votes as a separate message using message edits. Upon closing the poll, the bot will collect the results and display as a final message.

## License

Apache2