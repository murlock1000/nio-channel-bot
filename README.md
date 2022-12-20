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

# Setup


* Follow the setup guide using native mode (Docker instance not set up yet): [nio-template-setup](https://github.com/anoadragon453/nio-template/blob/master/SETUP.md)
* Install libolm: `apt install libolm-dev`
* Create a bot user.

## Disable message throttling
In order to allow the bot to respond to messages quickly,
we must overwrite the user message throttling settings,
We will be using the [Synapse Admin API](https://matrix-org.github.io/synapse/latest/usage/administration/admin_api/) to make a POST request to the server

### Getting the admin api key
1. Create a matrix user with admin privileges
2. Log in with the user
3. Go to 'All settings' -> 'Help & About' -> 'Advanced' -> 'Access Token' (at the bottom)
4. Copy the Access Token.
# This token is only valid for the duration you are logged in with the user
 
### Making the API call
The call for overwriting the @test:synapse.local throttle settings is:
`curl --header "Authorization: Bearer ENTERADMINAPIKEYHERE" -H "Content-Type: application/json" --request POST -k http://localhost:8008/_synapse/admin/v1/users/@test:synapse.local/override_ratelimit`
Should return result of `{"messages_per_second":0, "burst_count":0}`


## Step by step instructions

### Installing Prerequisites

Install libolm:
`sudo apt install libolm-dev`

Install postgres development headers:
`sudo apt install libpq-dev libpq5`

Create a python3 virtual environment in the project location (creates folder 'env'):
`virtualenv -p python3 env`
Activate the venv
`source env/bin/activate`

Install python dependencies:
`pip install -e.`

(Optional) install postgres python dependencies:
`pip install -e ".[postgres]"`


## Config file

Copy sample config file to new 'config.yaml' file
`cp sample.config.yaml config.yaml`

## config.yaml file edits:

user_id: "@test:synapse.local"
user_password: "pass"

homeserver_url: http://localhost:8080

## Create a unique device for the bot
device_id: UNIQUEDEVICEID
device_name: test_matrix_bot_xxx

## End of file edit
Run the bot:
`my-project-name`

Invite the bot to a group channel
Give the bot moderator power level (50)

In order to allow the bot to mute people:
Change Roles&Permissions: allow 'Change permissions' to Moderator 

In order to allow the bot to remove messages:
allow 'Remove messages sent by others' to Moderator
