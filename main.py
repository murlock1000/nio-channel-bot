#!/usr/bin/env python3
import asyncio

try:
    from nio_channel_bot import main

    # Run the main function of the bot
    asyncio.get_event_loop().run_until_complete(main.main())
except ImportError as e:
    print("Unable to import nio_channel_bot.main:", e)
