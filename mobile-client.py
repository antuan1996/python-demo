import json

try:
    import asyncio
except ImportError:
    # Trollius >= 0.3 was renamed
    import trollius as asyncio

from os import environ
from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner


class Component(ApplicationSession):

    async def on_question_posted(self, question_json):
        qdict = json.loads(question_json)
        if qdict["id"] == -1:
            self.leave()
        adict = {"question_id": qdict["id"], "user_id": self.id, "body": "hello"}
        print("Sending normal question id:")
        answ = await self.call("com."+self.game_name+".add_answer", answer_json=json.dumps(adict))
        if answ:
            print("right answer published")
        else:
            print("publishing  right answer error!")
        print("Sending wrong question id:")
        adict = {"question_id": 33, "user_id": self.id, "body": "hello"}
        answ = await self.call("com."+self.game_name+".add_answer", answer_json=json.dumps(adict))
        if answ:
            print("wrong answer published!!!")
        else:
            print("publishing wrong answer error!")

    async def onJoin(self, details):
        self.id = await self.call("com.assistant.get_user_id", "user")
        self.game_name = "first_game"
        self.subscribe(self.on_question_posted, "com."+self.game_name+".questions")
        self.call("com."+self.game_name+".join", json.dumps({"user_id": self.id, "event": "login"}))


    def join_to_quiz(self, request_json):
        reguest = json.loads(request_json)
        #TODO business logic
        #self.publish("com." + quiz_name + ".user_migration")

    def onDisconnect(self):
        asyncio.get_event_loop().stop()


if __name__ == '__main__':
    runner = ApplicationRunner(
        environ.get("AUTOBAHN_DEMO_ROUTER", u"ws://127.0.0.1:8080/ws"),
        u"realm1",
    )
    runner.run(Component)
