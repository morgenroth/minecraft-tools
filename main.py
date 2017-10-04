#!/usr/bin/env python
#

import logging
import sys
import json
import xmpp
import minecraft
import socket


def main():
    # enable logging
    logging.basicConfig(level=logging.DEBUG,
                        format='%(levelname)-8s %(message)s')

    # load settings
    settings = json.load(open("bot.json"))

    try:
        mm = minecraft.MinecraftMonitor(settings["logfile"], settings["xmpp"])
        bot = xmpp.ChatBot(settings["xmpp"], "Rcon", mm.message_received)

        mm.connect(settings["rcon"])

        bot.loop()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()

