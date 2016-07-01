#!/usr/bin/env python

from zope.interface import implements
from twisted.cred import portal, checkers, credentials, error as credError
from twisted.internet import defer, reactor
from twisted.web import static, resource
from twisted.web.resource import IResource
from twisted.web.http import HTTPChannel
from twisted.web import server
from twisted.web.guard import HTTPAuthSessionWrapper
from twisted.web.guard import DigestCredentialFactory
from twisted.web.guard import BasicCredentialFactory

class PasswordDictChecker:
    implements(checkers.ICredentialsChecker)
    credentialInterfaces = (credentials.IUsernamePassword,)

    def __init__(self):
        "passwords: a dict-like object mapping usernames to passwords"
        self.passwords = {
            'admin': 'aaa',
            'user1': 'bbb',
            'user2': 'ccc'
        }

    def requestAvatarId(self, credentials):
        username = credentials.username
        if username in self.passwords:
            if credentials.password == self.passwords[username]:
                return defer.succeed(username)
            else:
                return defer.fail(
                    credError.UnauthorizedLogin("Bad password"))
        else:
            return defer.fail(
                credError.UnauthorizedLogin("No such user"))


class HttpPasswordRealm(object):
    implements()

    def requestAvatar(self, user, mind, *interfaces):
        if IResource in interfaces:
            # myresource is passed on regardless of user
            return (IResource, static.File('./addons'), lambda: None)
        raise NotImplementedError()


if __name__ == "__main__":
    checker = PasswordDictChecker()
    realm = HttpPasswordRealm()
    p = portal.Portal(realm, [checker])

    credentialFactory = BasicCredentialFactory(b"McLaren Labs")
    protected_resource = HTTPAuthSessionWrapper(p, [credentialFactory])

    site = server.Site(protected_resource)
    site.protocol = HTTPChannel

    reactor.listenTCP(8801, site)
    reactor.run()
