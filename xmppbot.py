#!/usr/bin/env python
#

import logging
import tailer
import sys
import re
import mcrcon
import sleekxmpp
import threading
import json

def main():
    # enable logging
    logging.basicConfig(level=logging.INFO,
                        format='%(levelname)-8s %(message)s')

    # load settings
    settings = json.load(open("bot.json"))

    try:
        mm = MinecraftMonitor(settings["logfile"], settings["xmpp"])
        bot = ChatBot(settings["xmpp"], "Rcon", mm.message_received)
        mm.connect(settings["rcon"])
        mm.start()
        bot.loop()
    except KeyboardInterrupt:
        sys.exit(0)


class MinecraftUser(threading.Thread):
    def __init__(self, nickname, settings):
        threading.Thread.__init__(self)
        self.nickname = nickname
        self.bot = ChatBot(settings, self.nickname)

    def run(self):
        self.bot.loop()

    def join(self):
        self.bot.join()

    def leave(self):
        self.bot.leave()

    def talk(self, message):
        self.bot.talk(message)


class ChatBot(sleekxmpp.ClientXMPP):
    def __init__(self, settings, resource, callback=None):
        super(ChatBot, self).__init__(settings['jid'] + '/' + resource, settings['password'])

        self.add_event_handler("session_start", self.start)

        if callback:
            self.add_event_handler("groupchat_message", callback)

        self.register_plugin('xep_0030')  # Service Discovery
        self.register_plugin('xep_0045')  # Multi-User Chat
        self.register_plugin('xep_0199')  # XMPP Ping

        self.resource = resource
        self.room = settings['room']

    def loop(self):
        if self.connect(reattempt=True):
            self.process(block=True)

    def start(self, event):
        self.send_presence()
        self.get_roster()
        self.plugin['xep_0045'].joinMUC(self.room, self.resource)

    def join(self):
        self.plugin['xep_0045'].joinMUC(self.room, self.resource)

    def leave(self):
        self.plugin['xep_0045'].leaveMUC(self.room, self.resource)

    def talk(self, message):
        self.send_message(mto=self.room, mbody=message, mtype='groupchat')


class MinecraftMonitor(threading.Thread):
    def __init__(self, filename, xmpp_settings):
        threading.Thread.__init__(self)
        self.logger = logging.getLogger('bot')

        self.xmpp_settings = xmpp_settings
        self.filename = filename
        self.users = {}
        self.patterns = [
            (re.compile("^(.*) joined the game"), self.event_join),
            (re.compile("^(.*) left the game"), self.event_leave),
            (re.compile("^<(.*)> (.*)$"), self.event_chat)
        ]
        self.rcon = mcrcon.MCRcon()

    def parse(self, line):
        m = re.match("^\[(.*)\] \[(.*)/(.*)\]: (.*)$", line)
        if m:
            (time, instance, tag, msg) = m.groups()

            for p in self.patterns:
                m = p[0].match(msg)
                if m:
                    p[1](time, instance, tag, m.groups())
                    return

            self.logger.debug("time: %s, instance: %s, tag: %s, msg: %s" % (time, instance, tag, msg))

    def connect(self, settings):
        self.logger.info("Connect to %s:%s" % (settings['server'], settings['port']))
        self.rcon.connect(settings['server'], settings['port'], settings['password'])

    def run(self):
        self.logger.info("Attach to %s" % self.filename)
        for line in tailer.follow(open(self.filename)):
            self.parse(line)

    def event_join(self, time, instance, tag, data):
        try:
            if data[0] in self.users:
                user = self.users[data[0]]
                user.join()
            else:
                user = MinecraftUser(data[0], self.xmpp_settings)
                user.start()
                self.users[data[0]] = user
            self.logger.info("%s has joined" % data[0])
        except KeyError:
            pass

    def event_leave(self, time, instance, tag, data):
        try:
            if data[0] in self.users:
                user = self.users[data[0]]
                user.leave()
            self.logger.info("%s has left" % data[0])
        except KeyError:
            pass

    def event_chat(self, time, instance, tag, data):
        self.logger.info("<%s> %s" % (data[0], data[1]))
        if data[0] in self.users:
            user = self.users[data[0]]
            user.talk(data[1])

    def say(self, msg):
        self.logger.info("[Rcon] %s" % msg)
        response = self.rcon.command("say %s" % msg)

    def message_received(self, msg):
        if msg['from'].resource in self.xmpp_settings['admins']:
            self.say("%s: %s" % (msg['from'].resource, msg['body']))

        self.logger.debug("MUC message received from %s: %s" % (msg['from'], msg['body']))
        self.logger.debug("%s" % msg)


if __name__ == "__main__":
    main()

