import json, jsonpickle

import requests
import umsgpack
from PIL import Image
from requests.auth import HTTPBasicAuth

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
        #TODO password via arguments
        self.name = "frontend"
        self.secret = "971701"

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
        #qdict = {"id": 1, "title": "RPC test", "description": "Первый вопрос, добавленный удалённо", "difficulty":10, "addon_id":None, "tag":"my"}
        self.game_name = input("Enter game name:")
        n = int(input("Enter participants ammount:"))
        participants = []
        for i in range(n):
            user_name = input("Enter user name")
            participants.append(user_name)
        self.register(self.join_to_quiz, "com."+self.game_name+".join")
        self.register(self.open_image, "com.image")

        await self.call("com.assistant.start_quiz", game_name=self.game_name, participants=participants)
        print("quiz started")

    async def quiz_body(self):
        data = await self.call("com.admin.get_group", "my")
        data = json.loads(data)
        questions = data[0]
        addons = data[1]
        print(addons)
        for question in questions:
            print(question)
            curr_addon_id = str(question.pop("addon_id", None))
            if curr_addon_id is not None:
                addon_name = addons[curr_addon_id]
                request = requests.get("http://localhost:8801/"+addon_name,
                                       auth=HTTPBasicAuth('admin', 'aaa'))
                f = open(addon_name, "wb")
                f.write(request.content)
                f.close()
                print("downloaded", addon_name)
            self.publish("com." + self.game_name + ".questions", json.dumps(question))
            await asyncio.sleep(0.1)
        print("questions published")
        await asyncio.sleep(10)
        print("Closing quiz")
        qdict = {"id": -1}
        self.publish("com." + self.game_name + ".questions", json.dumps(qdict))

    async def join_to_quiz(self, request_json):
        reguest = json.loads(request_json)
        #TODO business logic
        if reguest["event"] == "login":
            self.counter += 1
        if self.counter >= 1:
            await self.quiz_body()
            self.leave()
        #self.publish("com." + quiz_name + ".user_migration")

    def open_image(self, data):
        ofile = open("python-mycopy.png","wb")
        ofile.write(data)
        ofile.close()
        #im = jsonpickle.decode(msg)
        #im.show()
    def onDisconnect(self):
        asyncio.get_event_loop().stop()


if __name__ == '__main__':
    runner = ApplicationRunner(
        environ.get("AUTOBAHN_DEMO_ROUTER", u"ws://127.0.0.1:8080/ws"),
        u"realm1",
    )
    runner.run(Component)
