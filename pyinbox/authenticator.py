###############################################################################
##
##  Copyright (C) Tavendo GmbH and/or collaborators. All rights reserved.
##
##  Redistribution and use in source and binary forms, with or without
##  modification, are permitted provided that the following conditions are met:
##
##  1. Redistributions of source code must retain the above copyright notice,
##     this list of conditions and the following disclaimer.
##
##  2. Redistributions in binary form must reproduce the above copyright notice,
##     this list of conditions and the following disclaimer in the documentation
##     and/or other materials provided with the distribution.
##
##  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
##  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
##  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
##  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
##  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
##  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
##  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
##  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
##  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
##  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
##  POSSIBILITY OF SUCH DAMAGE.
##
###############################################################################

import os
from pprint import pprint
#import sqlite3
import psycopg2
import six

from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp.exception import ApplicationError


class AuthenticatorSession(ApplicationSession):
    
    @inlineCallbacks
    def onJoin(self, details):
        self.con = psycopg2.connect(database="postgres", user="postgres", password="postgres")
        self.cur = self.con.cursor()
        self.cur.execute("SELECT id from roles WHERE name=%s", ("mobile-client",))
        self.user_role_id = self.cur.fetchone()[0]

        def authenticate(realm, authid, details):
            given_ticket = details['ticket']
            print("WAMP-Ticket dynamic authenticator invoked: realm='{}', authid='{}', ticket='{}'".format(
                realm, authid, given_ticket))
            #pprint(details)
            self.cur.execute("SELECT secret, role_id, id FROM users WHERE name=%s", (authid, ))
            dbase_ticket = self.cur.fetchone()
            if dbase_ticket is None:
                raise ApplicationError("com.errors.no_such_user", """could not authenticate session- no such principal {}""".format(authid))
            if dbase_ticket[1] is None:
                raise ApplicationError("com.errors.disabled_account", "account {} is disabled, please enter other name".format(authid))
            if given_ticket != dbase_ticket[0]:
                raise ApplicationError("com.errors.wrong_secret", "Incorrect password")

            if dbase_ticket[1] == self.user_role_id:
                self.cur.execute("SELECT game_id FROM user_game WHERE user_id=%s", (dbase_ticket[2], ))
                game_id = self.cur.fetchone()[0]
                self.cur.execute("SELECT name FROM tags WHERE id=%s", (game_id, ))
                game_name = self.cur.fetchone()[0]
                return {u"role": u"root", u"extra": {u"game_name": game_name}}
            else:
                return {u"role": u"root"}

        try:
            yield self.register(authenticate, 'com.authenticate')
            print("WAMP-Ticket dynamic authenticator registered!")
        except Exception as e:
            print("Failed to register dynamic authenticator: {0}".format(e))
