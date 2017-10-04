#!/usr/bin/env python
#

import sleekxmpp


class ChatBot(sleekxmpp.ClientXMPP):
    def __init__(self, settings, resource, callback=None):
        super(ChatBot, self).__init__(settings['jid'] + '/' + resource, settings['password'])

        self.add_event_handler("session_start", self.start)

        if callback:
            self.add_event_handler("groupchat_message", callback)

        self.register_plugin('xep_0030')  # Service Discovery
        self.register_plugin('xep_0045')  # Multi-User Chat
        self.register_plugin('xep_0199')  # XMPP Ping

        #self.register_plugin('xep_0012')  # Last Activity
        self.register_plugin('xep_0186')  # Invisible Command
        self.register_plugin('xep_0198')  # Stream Management
        #self.register_plugin('xep_0352')  # Client State Indication

        self.resource = resource
        self.room = settings['room']
        self.character_state = "available"

    def loop(self):
        if self.connect(reattempt=True):
            self.process(block=True)

    def send_state(self, new_state=None):
        if not new_state:
            new_state = self.character_state

        try:
            if new_state == "available":
                #self.plugin['xep_0352'].send_active()
                #self.plugin['xep_0186'].set_visible()
                self.send_presence()
            else:
                self.send_presence(pshow="unavailable")
                #self.plugin['xep_0186'].set_invisible()
                #self.plugin['xep_0352'].send_inactive()
        except sleekxmpp.IqError:
            pass

        # set new state
        self.character_state = new_state

        # touch last activity indicator
        #self.plugin['xep_0012'].set_last_activity()

    def start(self, event):
        self.send_state()
        self.get_roster()
        self.plugin['xep_0045'].joinMUC(self.room, self.resource)

    def join(self):
        self.send_state("available")
        self.plugin['xep_0045'].joinMUC(self.room, self.resource)

    def leave(self):
        self.plugin['xep_0045'].leaveMUC(self.room, self.resource)
        self.send_state("unavailable")

    def talk(self, message):
        #self.plugin['xep_0012'].set_last_activity()
        self.send_message(mto=self.room, mbody=message, mtype='groupchat')

