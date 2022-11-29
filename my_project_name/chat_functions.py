import logging
import asyncio
from typing import Optional, Union
from my_project_name.storage import Storage
from aiohttp import ClientResponse
from markdown import markdown
from nio import (
    AsyncClient,
    ErrorResponse,
    LocalProtocolError,
    MatrixRoom,
    MegolmEvent,
    Response,
    RoomCreateError,
    RoomCreateResponse,
    RoomGetStateEventError,
    RoomGetStateEventResponse,
    RoomPreset,
    RoomPutStateError,
    RoomPutStateResponse,
    RoomSendResponse,
    RoomVisibility,
    SendRetryError,
    UploadResponse,
)
from nio.http import TransportResponse

# File sending prerequisites
import aiofiles
import aiofiles.os
import os
import magic
import traceback

logger = logging.getLogger(__name__)

class ChatFunctions:

    def __init__(
        self,
        client: AsyncClient,
        store: Storage
    ):
        """ Chat commands used for communicating with a room.

        Args:
            client: The client to communicate to matrix with.

            store: Bot storage.
        """
        self.client = client
        self.store = store

    async def send_text_to_room(
        self,
        room_id: str,
        message: str,
        notice: bool = True,
        markdown_convert: bool = True,
        reply_to_event_id: Optional[str] = None,
    ) -> Union[RoomSendResponse, ErrorResponse]:
        """Send text to a matrix room.

        Args:
            room_id: The ID of the room to send the message to.

            message: The message content.

            notice: Whether the message should be sent with an "m.notice" message type
                (will not ping users).

            markdown_convert: Whether to convert the message content to markdown.
                Defaults to true.

            reply_to_event_id: Whether this message is a reply to another event. The event
                ID this is message is a reply to.

        Returns:
            A RoomSendResponse if the request was successful, else an ErrorResponse.
        """
        # Determine whether to ping room members or not
        msgtype = "m.notice" if notice else "m.text"

        content = {
            "msgtype": msgtype,
            "format": "org.matrix.custom.html",
            "body": message,
        }

        if markdown_convert:
            content["formatted_body"] = markdown(message)

        if reply_to_event_id:
            content["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to_event_id}}

        try:
            return await self.client.room_send(
                room_id,
                "m.room.message",
                content,
                ignore_unverified_devices=True,
            )
        except (SendRetryError, LocalProtocolError):
            logger.exception(f"Unable to send message response to {room_id}")


    async def send_image_to_room(
        self,
        room_id: str,
        file: str,
    ) -> Union[RoomSendResponse, ErrorResponse]:
        """Process file.
        Upload file to server and then send link to rooms.
        Works and tested for .pdf, .txt, .ogg, .wav.
        All these file types are treated the same.
        Arguments:
        ---------
        rooms : list
            list of room_id-s
        file : str
            file name of file from --file argument
        This is a working example for a PDF file.
        It can be viewed or downloaded from:
        https://matrix.example.com/_matrix/media/r0/download/
            example.com/SomeStrangeUriKey # noqa
        {
            "type": "m.room.message",
            "sender": "@someuser:example.com",
            "content": {
                "body": "example.pdf",
                "info": {
                    "size": 6301234,
                    "mimetype": "application/pdf"
                    },
                "msgtype": "m.file",
                "url": "mxc://example.com/SomeStrangeUriKey"
            },
            "origin_server_ts": 1595100000000,
            "unsigned": {
                "age": 1000,
                "transaction_id": "SomeTxId01234567"
            },
            "event_id": "$SomeEventId01234567789Abcdef012345678",
            "room_id": "!SomeRoomId:example.com"
        }
        """
        if not os.path.isfile(file):
            logger.debug(f"File {file} is not a file. Doesn't exist or "
                         "is a directory."
                         "This file is being droppend and NOT sent.")
            return

        # # restrict to "txt", "pdf", "mp3", "ogg", "wav", ...
        # if not re.match("^.pdf$|^.txt$|^.doc$|^.xls$|^.mobi$|^.mp3$",
        #                os.path.splitext(file)[1].lower()):
        #    logger.debug(f"File {file} is not a permitted file type. Should be "
        #                 ".pdf, .txt, .doc, .xls, .mobi or .mp3 ... "
        #                 f"[{os.path.splitext(file)[1].lower()}]"
        #                 "This file is being droppend and NOT sent.")
        #    return

        # 'application/pdf' "plain/text" "audio/ogg"
        mime_type = magic.from_file(file, mime=True)
        # if ((not mime_type.startswith("application/")) and
        #        (not mime_type.startswith("plain/")) and
        #        (not mime_type.startswith("audio/"))):
        #    logger.debug(f"File {file} does not have an accepted mime type. "
        #                 "Should be something like application/pdf. "
        #                 f"Found mime type {mime_type}. "
        #                 "This file is being droppend and NOT sent.")
        #    return

        # first do an upload of file if it hasn't already been uploaded
        # see https://matrix-nio.readthedocs.io/en/latest/nio.html#nio.AsyncClient.upload # noqa
        # then send URI of upload to room
        file_stat = await aiofiles.os.stat(file)

        content_uri = self.store.get_uri(file)

        if content_uri is None:
            async with aiofiles.open(file, "r+b") as f:
                resp, maybe_keys = await self.client.upload(
                    f,
                    content_type=mime_type,  # application/pdf
                    filename=os.path.basename(file),
                    filesize=file_stat.st_size)
            if (isinstance(resp, UploadResponse)):
                logger.debug("File was uploaded successfully to server. "
                            f"Response is: {resp.content_uri}")
                content_uri = resp.content_uri

                # Store the content uri in our database for later reuse
                logger.debug(f"Storing file {file} uri {content_uri} to the DB.")
                self.store.set_uri(file, content_uri)
            else:
                logger.info(f"Failed to upload file to server. "
                            "Please retry. This could be temporary issue on "
                            "your server. "
                            "Sorry.")
                logger.info(f"file=\"{file}\"; mime_type=\"{mime_type}\"; "
                            f"filessize=\"{file_stat.st_size}\""
                            f"Failed to upload: {resp}")
                return
        else:
            logger.debug(f"Found URI of {file} in the DB, using: {content_uri}")

        content = {
            "body": os.path.basename(file),  # descriptive title
            "info": {
                "size": file_stat.st_size,
                "mimetype": mime_type,
            },
            "msgtype": "m.image",
            "url": content_uri,
        }

        try:
            await self.client.room_send(
                room_id,
                message_type="m.room.message",
                content=content
            )
            logger.debug(f"This file was sent: \"{file}\" "
                         f"to room \"{room_id}\".")
        except Exception:
            logger.debug(f"File send of file {file} failed. "
                         "Sorry. Here is the traceback.")
            logger.debug(traceback.format_exc())
        return content_uri


    def make_pill(self, user_id: str, displayname: str = None) -> str:
        """Convert a user ID (and optionally a display name) to a formatted user 'pill'

        Args:
            user_id: The MXID of the user.

            displayname: An optional displayname. Clients like Element will figure out the
                correct display name no matter what, but other clients may not. If not
                provided, the MXID will be used instead.

        Returns:
            The formatted user pill.
        """
        if not displayname:
            # Use the user ID as the displayname if not provided
            displayname = user_id

        return f'<a href="https://matrix.to/#/{user_id}">{displayname}</a>'


    async def react_to_event(
        self,
        room_id: str,
        event_id: str,
        reaction_text: str,
    ) -> Union[Response, ErrorResponse]:
        """Reacts to a given event in a room with the given reaction text

        Args:
            room_id: The ID of the room to send the message to.

            event_id: The ID of the event to react to.

            reaction_text: The string to react with. Can also be (one or more) emoji characters.

        Returns:
            A nio.Response or nio.ErrorResponse if an error occurred.

        Raises:
            SendRetryError: If the reaction was unable to be sent.
        """
        content = {
            "m.relates_to": {
                "rel_type": "m.annotation",
                "event_id": event_id,
                "key": reaction_text,
            }
        }

        return await self.client.room_send(
            room_id,
            "m.reaction",
            content,
            ignore_unverified_devices=True,
        )


    async def decryption_failure(self, room: MatrixRoom, event: MegolmEvent) -> None:
        """Callback for when an event fails to decrypt. Inform the user"""
        logger.error(
            f"Failed to decrypt event '{event.event_id}' in room '{room.room_id}'!"
            f"\n\n"
            f"Tip: try using a different device ID in your config file and restart."
            f"\n\n"
            f"If all else fails, delete your store directory and let the bot recreate "
            f"it (your reminders will NOT be deleted, but the bot may respond to existing "
            f"commands a second time)."
        )

        user_msg = (
            "Unable to decrypt this message. "
            "Check whether you've chosen to only encrypt to trusted devices."
        )

        await self.send_text_to_room(
            room.room_id,
            user_msg,
            reply_to_event_id=event.event_id,
        )


    async def _send_task(self, room_id: str, send_method: staticmethod, content: str):
        """
        : Wait for new sync, until we receive the new room information
        : Send the message to the room
        """
        while self.client.rooms.get(room_id) is None:
            await self.client.synced.wait()
        await send_method(room_id, content)


    async def send_msg(self, mxid: str, content: str, is_image: bool = False, room_id: str = None, roomname: str = ""):
        """
        :Code from - https://github.com/vranki/hemppa/blob/dcd69da85f10a60a8eb51670009e7d6829639a2a/bot.py
        :param mxid: A Matrix user id to send the message to
        :param roomname: A Matrix room id to send the message to
        :param message: Text to be sent as message
        :return bool: Returns room id upon sending the message
        """
        # Sends private message to user. Returns true on success.
        if room_id is None:
            msg_room = await self.find_or_create_private_msg(mxid, roomname)
            if not msg_room or (type(msg_room) is RoomCreateError):
                logger.error(f"Unable to create room when trying to message {mxid}")
                return None
            room_id = msg_room.room_id
        logger.debug(f"Found room id: {room_id}")
        """
        : A concurrency problem: creating a new room does not sync the local data about rooms.
        : In order to perform the sync, we must exit the callback.
        : Solution: use an asyncio task, that performs the sync.wait() and sends the message afterwards concurently with sync_forever().
        """
        task = None
        if is_image:
            task = asyncio.get_event_loop().create_task(
                self._send_task(room_id, self.send_image_to_room, content)
            )
        else:
            task = asyncio.get_event_loop().create_task(
                self._send_task(room_id, self.send_text_to_room, content)
            )
        return [room_id, task]


    async def find_or_create_private_msg(
        self, mxid: str, roomname: str
    ) -> Union[RoomCreateResponse, RoomCreateError]:
        """
        :param mxid: user id to create a DM for
        :param roomname: The DM room name
        :return: the Room Response from room_create()
        """
        # Find if we already have a common room with user:
        msg_room = None
        for croomid in self.client.rooms:
            roomobj = self.client.rooms[croomid]
            if roomobj.member_count == 2:
                for user in roomobj.users:
                    if user == mxid:
                        msg_room = roomobj
                for user in roomobj.invited_users:
                    if user == mxid:
                        msg_room = roomobj
        # Nope, let's create one
        if not msg_room:
            msg_room = await self.client.room_create(
                visibility=RoomVisibility.private,
                name=roomname,
                is_direct=True,
                preset=RoomPreset.private_chat,
                invite={mxid},
            )
            logger.debug(f"Created new room with id: {msg_room.room_id}")
        return msg_room


    # Code for changing user power was taken from https://github.com/elokapina/bubo/commit/d2a69117e52bb15090f993f79eeed8dbc3b3e4ae
    async def with_ratelimit(self, method: str, *args, **kwargs):
        func = getattr(self.client, method)
        response = await func(*args, **kwargs)
        if getattr(response, "status_code", None) == "M_LIMIT_EXCEEDED":
            return await self.with_ratelimit(method, *args, **kwargs)
        return response


    async def set_user_power(
        self,
        room_id: str,
        user_id: str,
        power: int,
    ) -> Union[
        int,
        RoomGetStateEventError,
        RoomGetStateEventResponse,
        RoomPutStateError,
        RoomPutStateResponse,
    ]:
        """
        Set user power in a room.
        """
        logger.debug(f"Setting user power: {room_id}, user: {user_id}, level: {power}")
        state_response = await self.client.room_get_state_event(room_id, "m.room.power_levels")
        if isinstance(state_response, RoomGetStateEventError):
            logger.error(f"Failed to fetch room {room_id} state: {state_response.message}")
            return state_response
        if isinstance(state_response.transport_response, TransportResponse):
            status_code = state_response.transport_response.status_code
        elif isinstance(state_response.transport_response, ClientResponse):
            status_code = state_response.transport_response.status
        else:
            logger.error(
                f"Failed to determine status code from state response: {state_response}"
            )
            return state_response
        if status_code >= 400:
            logger.warning(
                f"Failed to set user {user_id} power in {room_id}, response {status_code}"
            )
            return status_code
        state_response.content["users"][user_id] = power
        response = await self.with_ratelimit(
            "room_put_state",
            room_id=room_id,
            event_type="m.room.power_levels",
            content=state_response.content,
        )
        return response
