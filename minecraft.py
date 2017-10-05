#!/usr/bin/env python
#

import logging
import re
import mcrcon
import threading
import xmpp
import socket
import time
import os


class MinecraftUser(threading.Thread):
    def __init__(self, nickname, settings):
        threading.Thread.__init__(self)
        self.nickname = nickname
        self.bot = xmpp.ChatBot(settings, self.nickname)

    def run(self):
        self.bot.loop()

    def join(self):
        self.bot.join()

    def leave(self):
        self.bot.leave()

    def talk(self, message):
        self.bot.talk(message)


class MinecraftMonitor:
    def __init__(self, filename, xmpp_settings):
        self.logger = logging.getLogger('bot')
        self.xmpp_settings = xmpp_settings

        # create parser
        self.logger.info("Attach to %s" % filename)
        self.parser = LogParser(filename, self.parse)

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
        try:
            self.rcon.connect(settings['server'], settings['port'], settings['password'])
        except socket.gaierror:
            self.logger.error("RCON connection failed")

        self.parser.start()

    def disconnect(self):
        self.parser.stop()

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


class LogParser(threading.Thread):
    line_terminators = ('\r\n', '\n', '\r')

    def __init__(self, filename, callback):
        threading.Thread.__init__(self)
        self.filename = filename
        self.file = None
        self.callback = callback
        self.running = True

    def open(self, end = False):
        if self.file:
            self.file.close()
        self.file = open(self.filename)
        self.inode = os.stat(self.filename).st_ino
        if end:
            self.file.seek(0, 2)

    def has_rotated(self):
        inode = os.stat(self.filename).st_ino
        return self.inode != inode

    def run(self):
        self.open(True)
        while self.running:
            where = self.file.tell()
            line = self.file.readline()
            if line:
                if trailing and line in self.line_terminators:
                    # This is just the line terminator added to the end of the file
                    # before a new line, ignore.
                    trailing = False
                    continue

                if line[-1] in self.line_terminators:
                    line = line[:-1]
                    if line[-1:] == '\r\n' and '\r\n' in self.line_terminators:
                        # found crlf
                        line = line[:-1]

                trailing = False
                self.callback(line)
            else:
                if self.has_rotated():
                    self.open()
                else:
                    trailing = True
                    self.file.seek(where, 0)
                time.sleep(1.0)

    def stop(self):
        self.running = False
        self.join()


def test_logparser_callback(data):
    print(data)


def test_logparser():
    logfile = open("test.log", 'w')
    p = LogParser("test.log", test_logparser_callback)
    p.start()

    time.sleep(1)
    logfile.write("hello\n")
    logfile.flush()
    time.sleep(2)
    logfile.write("world\n")
    logfile.flush()
    time.sleep(2)
    logfile.write("summer\n")
    logfile.flush()
    time.sleep(2)
    logfile.close()

    os.rename("test.log", "test.1.log")
    logfile = open("test.log", 'w')

    time.sleep(1)
    logfile.write("hallo\n")
    logfile.flush()
    time.sleep(2)
    logfile.write("welt\n")
    logfile.flush()
    time.sleep(2)
    logfile.write("sommer\n")
    logfile.flush()
    time.sleep(2)
    logfile.close()

    p.stop()
    os.remove("test.log")
    os.remove("test.1.log")

if __name__ == "__main__":
    test_logparser()
