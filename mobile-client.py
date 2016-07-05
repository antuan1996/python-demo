import json

import requests
from requests.auth import HTTPBasicAuth
from PIL import Image

try:
    import asyncio
except ImportError:
    # Trollius >= 0.3 was renamed
    import trollius as asyncio

from os import environ
from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner


class Component(ApplicationSession):
    def __init__(self, config):
        super().__init__(config)
        self.counter = 0
        # TODO password via arguments
        self.name = input("enter name:")
        self.secret = input("enter secret:")

    async def on_question_posted(self, question_json):
        qdict = json.loads(question_json)
        if qdict["id"] == -1:
            print("closing connection")
            await self.game.unsubscribe()
            self.leave()
            return
        adict = {"question_id": qdict["id"], "user_id": self.id, "body": "hello", "game_name": self.game_name}
        print("Sending normal question id:")
        answ = await self.call("com.assistant.add_answer", adict)
        answ = await self.call("com.assistant.add_answer", adict)
        answ = await self.call("com.assistant.add_answer", adict)
        answ = await self.call("com.assistant.add_answer", adict)
        answ = await self.call("com.assistant.add_answer", adict)
        answ = await self.call("com.assistant.add_answer", adict)

        if answ:
            print("right answer published")
        else:
            print("publishing  right answer error!")
        print("Sending wrong question id:")
        adict = {"question_id": 33, "user_id": self.id, "body": "hello", "game_name": self.game_name}
        answ = await self.call("com.assistant.add_answer", adict)
        if answ:
            print("wrong answer published!!!")
        else:
            print("publishing wrong answer error!")

    def onConnect(self):
        print("Client session connected. Starting WAMP-Ticket authentication on realm '{}' as principal '{}' ..".format(
            "realm1", self.name))
        self.join("realm1", ["ticket"], self.name)

    def onChallenge(self, challenge):
        if challenge.method == "ticket":
            print("WAMP-Ticket challenge received: {}".format(challenge))
            return self.secret
        else:
            raise Exception("Invalid authmethod {}".format(challenge.method))

    async def onJoin(self, details):
        print("joined")
        print(details)
        self.id = await self.call("com.assistant.get_user_id", self.name)
        self.game_name = details.authextra["game_name"]
        self.game = await self.subscribe(self.on_question_posted, u"com."+self.game_name+u".questions")
        self.publish("com."+self.game_name+".join", json.dumps({"user_id": self.id, "event": "login"}))
        #self.leave()

    def join_to_quiz(self, request_json):
        request = json.loads(request_json)
        #TODO business logic
        #self.publish("com." + quiz_name + ".user_migration")


    def onDisconnect(self):
        asyncio.get_event_loop().stop()


if __name__ == '__main__':
    from io import BytesIO
    runner = ApplicationRunner(
       environ.get("AUTOBAHN_DEMO_ROUTER", u"ws://127.0.0.1:8080/ws"),
        u"realm1")
    runner.run(Component)
