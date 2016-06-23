import json

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

    async def onJoin(self, details):
        #qdict = {"id": 1, "title": "RPC test", "description": "Первый вопрос, добавленный удалённо", "difficulty":10, "addon_id":None, "tag":"my"}
        self.game_name = "first_game"
        self.register(self.join_to_quiz, "com."+self.game_name+".join")
        await self.call("com.assistant.start_quiz", self.game_name)
        print("quiz started")

    async def quiz_body(self):
        answ = await self.call("com.admin.get_group", "my")
        answ = json.loads(answ)
        for question in answ:
            print(question)
            # answ = await self.call("com.assistant.create_tables")
            # print(answ)
            # yield from self.subscribe(on_event, u'com.myapp.topic1')
            # self.publish("test", json.dumps(question))
            self.publish("com." + self.game_name + ".questions", json.dumps(question))
            #await asyncio.sleep(2)
        print("questions published")
        await asyncio.sleep(10)
        print("Closing quiz")
        qdict = {"id": -1}
        self.publish("com.first_game.questions", json.dumps(qdict))
        self.leave()

    async def join_to_quiz(self, request_json):
        reguest = json.loads(request_json)
        #TODO business logic
        if reguest["event"] == "login":
            self.counter += 1
        if self.counter >= 1:
            await self.quiz_body()
        #self.publish("com." + quiz_name + ".user_migration")

    def onDisconnect(self):
        asyncio.get_event_loop().stop()


if __name__ == '__main__':
    runner = ApplicationRunner(
        environ.get("AUTOBAHN_DEMO_ROUTER", u"ws://127.0.0.1:8080/ws"),
        u"realm1",
    )
    runner.run(Component)
