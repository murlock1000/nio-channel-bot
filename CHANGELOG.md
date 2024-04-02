# Changelog

## v1.0.0 - 2024-04-01
Initial version with the following features

* Messages to the room the bot is in are filtered by criteria:
  * If the sender has power level < 50
  * The message is not a thread reply.
* Warning message is sent to a DM room.
* If an existing DM room is not found - a new one is created.
* Messages to a newly created DM room are buffered, until client state receives the room data.
* After 3 attempts the user is muted.
* User is informed about the ban and is provided with the usernames of the room admins.
