import json

try:
    import asyncio
except ImportError:
    # Trollius >= 0.3 was renamed
    import trollius as asyncio

from os import environ
from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner


class Component(ApplicationSession):
    """
    An application component that subscribes and receives events, and
    stop after having received 5 events.
    """

    async def onJoin(self, details):
        self.id = await self.call("com.assistant.get_user_id", "user")
        qdict = {"id": 1, "title": "RPC test", "description":"Первый вопрос, добавленный удалённо", "difficulty":10, "addon_id":None, "tag":"my"}
        answ = await self.call("com.assistant.start_quiz", "first_game")
        print("quiz started")
        self.publish("com.first_game.questions", json.dumps(qdict))
        print("question published")

        await asyncio.sleep(3)
        adict = {"question_id": 1, "user_id": self.id, "body": "hello"}

        answ = await self.call("com.first_game.add_answer", answer_json=json.dumps(adict))
        if answ:
            print("answer published")
        else:
            print("publishing answer error!")
        print("Sending wrong question id:")
        adict = {"question_id": 3, "user_id": self.id, "body": "hello"}
        answ = await self.call("com.first_game.add_answer", answer_json=json.dumps(adict))
        if answ:
            print("answer published")
        else:
            print("publishing answer error!")
        print("Closing quiz")
        qdict = {"id": -1}
        self.publish("com.first_game.questions", json.dumps(qdict))
        answ = await self.call("com.admin.get_group", "my")
        print("my id", self.id)
        answ = json.loads(answ)
        for q in answ:
            print(q)
            #answ = await self.call("com.assistant.create_tables")
            #print(answ)

            #yield from self.subscribe(on_event, u'com.myapp.topic1')

    def onDisconnect(self):
        asyncio.get_event_loop().stop()


if __name__ == '__main__':
    runner = ApplicationRunner(
        environ.get("AUTOBAHN_DEMO_ROUTER", u"ws://127.0.0.1:8080/ws"),
        u"realm1",
    )
    runner.run(Component)
