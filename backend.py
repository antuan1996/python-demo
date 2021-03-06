import json
import time
import datetime
import signal

from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner
from autobahn.wamp.exception import ApplicationError
from xkcdpass import xkcd_password as xp
import asyncio
import aiopg

from typing import Dict

class Dbase(ApplicationSession):

    class Game:
        def __init__(self, sub, game_id):
            self.participants_list = []
            self._sub = sub
            self.game_id = game_id
            self.cur_question_id = None
            self.prev_question_id = None

        async def leave(self):
            await self._sub.unsubscribe()

    #TODO add game_id in answers table
    async def add_answer(self, answer):
        con = await self.pool.acquire()
        cur = await con.cursor()
        game_name = answer["game_name"]
        print("answer for " + game_name)
        finish = time.time()
        delt = finish - self.games[game_name].question_start_time
        answ_tuple = (answer["question_id"], answer["user_id"], delt, answer["body"])
        if( answer["question_id"] == self.games[game_name].cur_question_id
            or answer["question_id"] == self.games[game_name].prev_question_id):
            await cur.execute("INSERT INTO answers(quest_id, user_id, seconds, body) VALUES(%s, %s, %s, %s)", answ_tuple)
            print("saved")
            print(self.pool.freesize)
            await self.pool.release(con)
            return True
        else:
            print("Wrond question id", answer["question_id"], " vs",  self.cur_question_id)
            return False

    async def on_question_posted(self, game_name: str, quest_json: str):
        print("Got question for", game_name)
        con = await self.pool.acquire()
        cur = await con.cursor()
        print(json.loads(quest_json))
        self.games[game_name].prev_question_id = self.games[game_name].cur_question_id
        self.games[game_name].cur_question_id = json.loads(quest_json)["id"]
        self.games[game_name].question_start_time = time.time()
        if self.games[game_name].cur_question_id == -1:
            print(game_name, "finished")
            print("disabling participants")
            for user_id in self.games[game_name].participants_list:
                print("disabling user with id=", user_id)
                await cur.execute("UPDATE users SET role_id=NULL WHERE id=%s", (user_id,))
            await self.games[game_name].leave()
        print("Amount of enabled connections", self.pool.freesize)
        await self.pool.release(con)

    async def start_quiz(self, data: Dict):
        print("Quiz registration was called")
        game_name = data["game_name"]
        participants = data["players"]
        participants_list = []
        con = await self.pool.acquire()
        cur = await con.cursor()

        await cur.execute("SELECT id from roles WHERE name=%s", ("mobile-client",))
        user_role_id = await cur.fetchone()
        user_role_id = user_role_id[0]
        game_id = await self.get_tag_id(game_name)
        time_stmp = datetime.datetime.now()
        try:
            await cur.execute("INSERT INTO games VALUES(%s, %s)", (game_id, time_stmp))
        except Exception:
            print("Warning! Game was initiated before")
        finally:
            full_game_name = "com." + game_name
            wordfile = xp.locate_wordfile()
            mywords = xp.generate_wordlist(wordfile=wordfile, min_length=5, max_length=5)
            for user_name in participants:
                secret = xp.generate_xkcdpassword(mywords, acrostic="hi", delimiter=":")
                # secret = string.capwords(secret)
                await cur.execute("INSERT INTO users(name, secret, role_id) VALUES(%s, %s, %s) RETURNING id",
                                       (user_name, secret, user_role_id))
                # self.cur.execute("SELECT last_insert_rowid()")
                cur_user_id = await cur.fetchone()
                cur_user_id = cur_user_id[0]
                participants_list.append(cur_user_id)
                await cur.execute("INSERT INTO user_game VALUES(%s, %s)", (cur_user_id, game_id))
            cur_game = await self.subscribe(lambda question: self.on_question_posted(game_name, question),
                                            full_game_name + ".questions")
            self.games[game_name] = Dbase.Game(cur_game, game_id)
            self.games[game_name].participants_list = participants_list
            print("subscribed")
            print(self.pool.freesize)
            await self.pool.release(con)
            return True

    async def create_tables(self):
        print("creating tables")
        con = await self.pool.acquire()
        cur = await con.cursor()
        await cur.execute('CREATE TABLE ad_types(id SERIAL PRIMARY KEY, type TEXT)')
        await cur.execute('CREATE TABLE addons(id SERIAL PRIMARY KEY, type INT REFERENCES ad_types(id), url TEXT)')
        await cur.execute("""CREATE TABLE questions(
                            id SERIAL PRIMARY KEY,
                            title TEXT,
                            description TEXT,
                            difficulty INTEGER CHECK(difficulty >=0 AND difficulty <=100),
                            addon_id INTEGER REFERENCES addons(id))""")
        await cur.execute('CREATE TABLE tags(id SERIAL PRIMARY KEY, name TEXT UNIQUE)')
        await cur.execute("""CREATE TABLE tags_quests(
                            tag_id INTEGER REFERENCES tags(id) ON UPDATE CASCADE ON DELETE RESTRICT,
                            quest_id INTEGER REFERENCES questions(id) ON UPDATE CASCADE ON DELETE RESTRICT,
                            PRIMARY KEY(quest_id, tag_id))""")
        await cur.execute("""CREATE TABLE rules(
                            id SERIAL PRIMARY KEY,
                            uri TEXT,
                            caller boolean,
                            callee boolean,
                            public boolean,
                            subscribe boolean)""")
        await cur.execute("""CREATE TABLE games(
                            tag_id SERIAL PRIMARY KEY,
                            beginning_time TIMESTAMP)""")
        await cur.execute("""CREATE TABLE roles(
                            id SERIAL PRIMARY KEY,
                            name TEXT UNIQUE)""")
        await cur.execute("""CREATE TABLE users(
                            id SERIAL PRIMARY KEY,
                            name TEXT UNIQUE,
                            secret TEXT,
                            role_id INT REFERENCES roles(id) ON UPDATE CASCADE ON DELETE RESTRICT)""")
        await cur.execute("""CREATE TABLE user_game(
                            user_id INT UNIQUE REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT,
                            game_id INT REFERENCES games(tag_id) ON UPDATE CASCADE ON DELETE RESTRICT,
                            PRIMARY KEY(user_id, game_id))""")
        await cur.execute("""CREATE TABLE roles_rules(
                            role_id INTEGER REFERENCES roles(id) ON UPDATE CASCADE ON DELETE RESTRICT,
                            rule_id INTEGER REFERENCES rules(id) ON UPDATE CASCADE ON DELETE RESTRICT)""")
        await cur.execute("""CREATE TABLE answers(
                            id SERIAL PRIMARY KEY,
                            game_id INTEGER REFERENCES games(tag_id) ON UPDATE CASCADE ON DELETE RESTRICT,
                            quest_id INTEGER REFERENCES questions(id) ON UPDATE CASCADE ON DELETE RESTRICT,
                            user_id INTEGER REFERENCES  users(id),
                            seconds FLOAT CHECK( seconds>0 AND seconds<=1000),
                            body TEXT)""")

        await cur.execute("""INSERT INTO roles VALUES(0, 'root' )""")
        await cur.execute("""INSERT INTO roles VALUES(1, 'backend' )""")
        await cur.execute("""INSERT INTO roles VALUES(2, 'web-client' )""")
        await cur.execute("""INSERT INTO roles VALUES(3, 'mobile-client' )""")

        await cur.execute("INSERT INTO ad_types(type) VALUES('PICTURE')")
        await cur.execute("INSERT INTO ad_types(type) VALUES('AUDIO')")
        await cur.execute("INSERT INTO ad_types(type) VALUES('VIDEO')")

        await cur.execute("INSERT INTO users(name, secret, role_id) VALUES('database', '55555', 1)")
        await cur.execute("INSERT INTO users(name, secret, role_id) VALUES('frontend', '971701', 2)")
        await cur.execute("INSERT INTO users(name, secret, role_id) VALUES('mobile', '933421', 3)")

        await cur.execute("INSERT INTO questions(title, description, difficulty, addon_id) VALUES('Тестовый вопрос 1', 'Просто введи любой ответ', 1, NULL)")

        await cur.execute("INSERT INTO rules(uri, caller, callee, public, subscribe) VALUES('com.quiz.model', TRUE, FALSE, FALSE, TRUE)")
        await cur.execute("INSERT INTO rules(uri, caller, callee, public, subscribe) VALUES('com.quiz.model', TRUE, FALSE, FALSE, FALSE)")
        print("Tables created!")
        print(self.pool.freesize)
        await self.pool.release(con)

    async def set_tag(self, question_number: int, tag: str):
        con = await self.pool.acquire()
        cur = await con.cursor()
        if tag is not None:
            tag_num = await self.get_tag_id(tag)
            try:
                await cur.execute("INSERT INTO tags_quests VALUES(%s, %s)", (tag_num, question_number,))
            except Exception as e:
                print(e)
                #raise e
            finally:
                print(self.pool.freesize)
                await self.pool.release(con)

    async def add_question(self, question_json: str):
        con = await self.pool.acquire()
        cur = await con.cursor()
        quest_dict = json.loads(question_json)
        tag = quest_dict["tag"]
        question_tuple = (quest_dict["title"], quest_dict["description"], quest_dict["difficulty"], quest_dict["addon_id"])
        await cur.execute("""INSERT INTO questions(title, description, difficulty,
                            addon_id) VALUES(%s, %s, %s, %s) RETURNING id""", question_tuple)
        #await cur.execute("SELECT last_insert_rowid()")
        question_num = await cur.fetchone()[0]
        print(self.pool.freesize)
        await self.pool.release(con)
        self.set_tag(question_num, tag)

    async def get_tag_id(self, tag: str):
        con = await self.pool.acquire()
        cur = await con.cursor()
        tnum = None
        await cur.execute("SELECT COUNT(id) FROM tags WHERE name=%s", (tag,))
        rc = await cur.fetchone()
        rc = rc[0]
        if rc > 1:
            raise ValueError('more than one row with the tag')
        if rc == 0:
            await cur.execute("INSERT INTO tags(name) VALUES(%s) RETURNING id", (tag,))
            #cur.execute("SELECT last_insert_rowid()")
            tnum = await cur.fetchone()
            tnum = tnum[0]
        else:
            await cur.execute("SELECT id FROM tags WHERE name=%s", (tag,))
            tnum = await cur.fetchone()
            tnum = tnum[0]
        print(self.pool.freesize)
        await self.pool.release(con)
        return tnum

    async def get_group(self, tag_name: str):
        con = await self.pool.acquire()
        cur = await con.cursor()
        await cur.execute("""SELECT questions.id, questions.title, questions.description,
                            questions.difficulty, questions.addon_id, addons.url
                            FROM questions JOIN tags_quests ON tags_quests.quest_id=questions.id
                            JOIN tags ON tags_quests.tag_id=tags.id
                            LEFT JOIN addons ON questions.addon_id=addons.id WHERE tags.name = %s""", (tag_name,))
        fetch_res = await cur.fetchall()
        ret_res = []
        questions_array = []
        addon_dict = {}
        for row in fetch_res:
            qdict = {"id": row[0], "title": row[1], "description": row[2], "difficulty": row[3], "addon_id": row[4]}
            if row[4] is not None and row[4] not in addon_dict:
                addon_dict[row[4]] = row[5]
            questions_array.append(qdict)
        ret_res.append(questions_array)
        ret_res.append(addon_dict)
        print(self.pool.freesize)
        await self.pool.release(con)
        return json.dumps(ret_res)
        #self.con.commit()

    async def get_user_id(self, user_name: str):
        con = await self.pool.acquire()
        cur = await con.cursor()
        print("gettind id", user_name)
        await cur.execute("SELECT id FROM users WHERE name=%s", (user_name,))
        res = await cur.fetchone()
        print(self.pool.freesize)
        await self.pool.release(con)
        if res is not None:
            return res[0]
        else:
            raise ApplicationError("com.wrong_user_id", "wrong user name")

            #TODO database cleaning

    def signal_handler(self, signum, frame):
        print('Signal handler called with signal', signum)
        self.leave()

    def onConnect(self):
        self.start = None
        self.cur_question_id = None
        self.prev_question_id = None
        self.cur_game = None
        self.name = "database"
        self.secret = "55555"
        self.games = {}
        print("Client session connected. Starting WAMP-Ticket authentication on realm '{}' as principal '{}' ..".format(
            "realm1", self.name))
        self.join("realm1", ["ticket"], self.name)

    async def onDisconnect(self):
        print("Disconnecting")
        self.pool.close()
        asyncio.get_event_loop().stop()

    def onChallenge(self, challenge):
        if challenge.method == "ticket":
            print("WAMP-Ticket challenge received: {}".format(challenge))
            return self.secret
        else:
            raise Exception("Invalid authmethod {}".format(challenge.method))

    async def onJoin(self, details):
        signal.signal(signal.SIGINT, self.signal_handler)
        self.pool = await aiopg.create_pool(database="postgres", user="postgres", password="postgres")
        #self.con.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        #await self.cur.execute("PRAGMA foreign_keys = ON")
        if "create_table" in self.config.extra:
            await self.create_tables()

        async def get_rules(self):
            con = await self.pool.acquire()
            cur = await con.cursor()
            await cur.execute("SELECT * FROM rules")
            print(self.pool.freesize)
            await self.pool.release(con)

        print("session attached")
        try:
            await self.register(self.get_user_id, "com.assistant.get_user_id")
            await self.register(self.add_answer, "com.assistant.add_answer")
            await self.register(self.add_question, "com.admin.add_question")
            await self.register(self.get_group, "com.admin.get_group")
            await self.register(self.create_tables, "com.admin.create_tables")
            await self.register(self.start_quiz, "com.assistant.start_quiz")
        except Exception as e:
            print(e)
        else:
            print("procedures registered")


def main():
    import  sys
    if len(sys.argv) >= 2:
        dbase_name = sys.argv[1]
    #runner = ApplicationRunner(u"ws://127.0.0.1:8080/ws", u"realm1", {"database_name": dbase_name, "create_table": None})
    runner = ApplicationRunner(u"ws://127.0.0.1:8080/ws", u"realm1", {"database_name": "database"})
    runner.run(Dbase)
    #runner.run(Dbase(name='quiz.db', create_table=False))
    #base.create_tables()
    #base.set_tag(3,"my")
    #q_json = json.dumps({"title": "test", "description": "json_question", "difficulty": 55, "addon_id": None})
    #base.add_question(q_json, "my")
    #base.add_question(("test2", "hi2", 20, None), "my")
    #base.get_group("my")

if __name__ == "__main__":
    main()