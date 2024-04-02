import asyncio
import logging

from nio import AsyncClient, MatrixRoom, RoomMessageText, RoomRedactResponse, RoomRedactError, RoomCreateError, RoomPutStateResponse

from nio_channel_bot.chat_functions import ChatFunctions, with_ratelimit
from nio_channel_bot.config import Config
from nio_channel_bot.storage import Storage

logger = logging.getLogger(__name__)


class Command:
    def __init__(
        self,
        client: AsyncClient,
        store: Storage,
        config: Config,
        command: str,
        room: MatrixRoom,
        event: RoomMessageText,
        chat: ChatFunctions
    ):
        """A command made by a user.

        Args:
            client: The client to communicate to matrix with.

            store: Bot storage.

            config: Bot configuration parameters.

            command: The command and arguments.

            room: The room the command was sent in.

            event: The event describing the command.
        """
        self.client = client
        self.store = store
        self.config = config
        self.command = command
        self.room = room
        self.event = event
        self.chat = chat
        self.args = self.command.split()[1:]

    async def process(self):
        """Process the command"""
        if self.command.startswith("echo"):
            await self._echo()
        elif self.command.startswith("react"):
            await self._react()
        elif self.command.startswith("help"):
            await self._show_help()
        else:
            await self._unknown_command()

    async def _echo(self):
        """Echo back the command's arguments"""
        response = " ".join(self.args)
        await self.chat.send_text_to_room(self.room.room_id, response)

    async def _react(self):
        """Make the bot react to the command message"""
        # React with a start emoji
        reaction = "⭐"
        await self.chat.react_to_event(
            self.room.room_id, self.event.event_id, reaction
        )

        # React with some generic text
        reaction = "Some text"
        await self.chat.react_to_event(
            self.room.room_id, self.event.event_id, reaction
        )

    async def _show_help(self):
        """Show the help text"""
        if not self.args:
            text = (
                "Hello, I am a bot made with matrix-nio! Use `help commands` to view "
                "available commands."
            )
            await self.chat.send_text_to_room(self.room.room_id, text)
            return

        topic = self.args[0]
        if topic == "rules":
            text = "These are the rules!"
        elif topic == "commands":
            text = "Available commands: ..."
        else:
            text = "Unknown help topic!"
        await self.chat.send_text_to_room(self.room.room_id, text)

    async def _unknown_command(self):
        await self.chat.send_text_to_room(
            self.room.room_id,
            f"Unknown command '{self.command}'. Try the 'help' command for more information.",
        )
    @with_ratelimit
    async def send_room_redact(self):
        return await self.client.room_redact(
                self.room.room_id,
                self.event.event_id,
                "You are not a moderator of this channel.",
            )

    #

    async def filter_channel(self):
        # First check the power level of the sender. 0 - default, 50 - moderator, 100 - admin, others - custom.
        logger.debug(
            f"{self.room.user_name(self.event.sender)} has power level: {self.room.power_levels.get_user_level(self.event.sender)}"
        )
        if self.room.power_levels.get_user_level(self.event.sender) < 50:
            if self.room.power_levels.can_user_redact(self.client.user_id):

                # Redact the message
                redact_response = await self.send_room_redact()
                if isinstance(redact_response, RoomRedactError):
                    logger.error(f"Failed to redact message in room {self.room.room_id} with id {self.event.event_id} with error: {redact_response.status_code}")
                    return

                fails = None
                is_banned = False
                if self.room.power_levels.get_user_level(self.event.sender) == -1:
                    is_banned = True
                    fails = 3
                else:
                    # Get user attempts from database
                    fails = self.store.get_fail(self.event.sender, self.room.room_id)

                # Ban if over 3 fails or issue warning:
                if fails < 3:
                    self.store.update_or_create_fail(
                        self.event.sender, self.room.room_id
                    )
                elif not is_banned:
                    # Delete the user attempt entry
                    self.store.delete_fail(self.event.sender, self.room.room_id)

                    # Mute user
                    resp = await self.chat.set_user_power(
                        self.room.room_id, self.event.sender, -1
                    )
                    if isinstance(resp, RoomPutStateResponse):
                        logger.info(
                            f"{self.room.user_name(self.event.sender)} has been banned from room {self.room.name}"
                        )
                    else:
                        logger.error(f"Error: Power level response: {resp}")
                        return

                # Add the room id get/create task to be performed after next sync
                notification_room_id_future = await self.chat.roomManager.get_private_room_id(self.event.sender)
                if isinstance(notification_room_id_future, RoomCreateError):
                    return

                # Inform user about ban/issue warning
                if fails < 3:
                    print("Sending warning message")
                    await self.chat.roomManager.send_msg_on_creation(
                        ("""Your comment has been deleted {} times in {} discussion due to being improperly sent. Please reply in threads. \n
How to enable threads: \n
1. Hover on a message and click 'Reply in Thread' button. \n
2. Press 'Join the beta' button. \n
3. Reply to a message using the 'Reply in Thread' button.""").format(fails+1, self.room.name),
                        notification_room_id_future,
                    )

                    await self.chat.roomManager.send_msg_on_creation(
                        "media/info_threads.gif",
                        notification_room_id_future,
                        is_image = True,
                    )
                else:
                    #Find admin users in room
                    admins = []
                    for user in self.room.users:
                        powerlevel = self.room.power_levels.get_user_level(user)
                        if user != self.client.user and powerlevel == 100:
                            admins.append(user)
                    admin_string = ", ".join(admins)
                    logger.debug(f"Room admins: {admin_string}")

                    # Inform user about the ban
                    await self.chat.roomManager.send_msg_on_creation(
                        f"# You have made >3 improper comments in {self.room.name} discussion. Please seek help from the group admins: {admin_string}",
                        notification_room_id_future
                    )
            else:
                logger.error(
                    f"Bot does not have sufficient power to redact others in group: {self.room.name}"
                )
