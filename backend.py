import functools
import json, jsonpickle
import sqlite3
import time
from os import environ
import string
import msgpack
from PIL import Image
from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner
from autobahn.wamp.exception import ApplicationError
from xkcdpass import xkcd_password as xp


class Dbase(ApplicationSession):

    def add_answer(self, game_name, answer_json):
        print("answer for " + game_name)
        answer = json.loads(answer_json)
        finish = time.time()
        delt = finish - self.start
        answ_tuple = (answer["question_id"], answer["user_id"], delt, answer["body"])
        if answer["question_id"] == self.cur_question_id or answer["question_id"] == self.prev_question_id:
            self.cur.execute("INSERT INTO answers VALUES(NULL, ?, ?, ?, ?)", answ_tuple)
            print("saved")
            self.con.commit()
            return True
        else:
            print("Wrond question id", answer["question_id"], " vs",  self.cur_question_id)
            return False

    def create_tables(self):
        print("creating tables")
        self.cur.execute('CREATE TABLE ad_types(id INTEGER PRIMARY KEY, type TEXT)')
        self.cur.execute('CREATE TABLE addons(id INTEGER PRIMARY KEY, type INT REFERENCES ad_types(id), url TEXT)')
        self.cur.execute("""CREATE TABLE questions(
                            id INTEGER PRIMARY KEY,
                            title TEXT,
                            description TEXT,
                            difficulty INTEGER CHECK(difficulty >=0 AND difficulty <=100),
                            addon_id INTEGER REFERENCES addons(id))""")
        self.cur.execute('CREATE TABLE tags(id INTEGER PRIMARY KEY, name TEXT UNIQUE)')
        self.cur.execute("""CREATE TABLE tags_quests(
                            tag_id INTEGER REFERENCES tags(id) ON UPDATE CASCADE ON DELETE RESTRICT,
                            quest_id INTEGER REFERENCES questions(id) ON UPDATE CASCADE ON DELETE RESTRICT,
                            PRIMARY KEY(quest_id, tag_id))""")
        self.cur.execute("""CREATE TABLE rules(
                            id INTEGER PRIMARY KEY,
                            uri TEXT,
                            caller BIT,
                            callee BIT,
                            public BIT,
                            subscribe BIT)""")
        self.cur.execute("""CREATE TABLE games(
                            id INTEGER PRIMARY KEY,
                            name TEXT UNIQUE,
                            beginning_time TIMESTAMP)""")
        self.cur.execute("""CREATE TABLE roles(
                            id INTEGER PRIMARY KEY,
                            name TEXT UNIQUE)""")
        self.cur.execute("""CREATE TABLE users(
                            id INTEGER PRIMARY KEY,
                            name TEXT UNIQUE,
                            secret TEXT,
                            role_id INT REFERENCES roles(id) ON UPDATE CASCADE ON DELETE RESTRICT)""")
        self.cur.execute("""CREATE TABLE user_game(
                            user_id INT UNIQUE REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT,
                            game_id INT REFERENCES games(id) ON UPDATE CASCADE ON DELETE RESTRICT,
                            PRIMARY KEY(user_id, game_id))""")
        self.cur.execute("""CREATE TABLE roles_rules(
                            role_id INTEGER REFERENCES roles(id) ON UPDATE CASCADE ON DELETE RESTRICT,
                            rule_id INTEGER REFERENCES rules(id) ON UPDATE CASCADE ON DELETE RESTRICT)""")
        self.cur.execute("""CREATE TABLE answers(
                            id INTEGER PRIMARY KEY,
                            quest_id INTEGER REFERENCES questions(id) ON UPDATE CASCADE ON DELETE RESTRICT,
                            user_id INTEGER REFERENCES  users(id),
                            seconds FLOAT CHECK( seconds>0 AND seconds<=1000),
                            body TEXT)""")
        self.con.commit()

        self.cur.execute("""INSERT INTO roles VALUES(0, "root" )""")
        self.cur.execute("""INSERT INTO roles VALUES(1, "backend" )""")
        self.cur.execute("""INSERT INTO roles VALUES(2, "web-client" )""")
        self.cur.execute("""INSERT INTO roles VALUES(3, "mobile-client" )""")
        self.con.commit()

        self.cur.execute("INSERT INTO ad_types VALUES(NULL, 'PICTURE')")
        self.cur.execute("INSERT INTO ad_types VALUES(NULL, 'AUDIO')")
        self.cur.execute("INSERT INTO ad_types VALUES(NULL, 'VIDEO')")
        self.con.commit()

        self.cur.execute("INSERT INTO users VALUES(NULL, 'database', '55555', 1)")
        self.cur.execute("INSERT INTO users VALUES(NULL, 'frontend', '971701', 2)")
        self.cur.execute("INSERT INTO users VALUES(NULL, 'mobile', '933421', 3)")
        self.con.commit()

        self.cur.execute("INSERT INTO questions VALUES(NULL, 'Тестовый вопрос 1', 'Просто введи любой ответ', 1, NULL)")
        self.con.commit()

        self.cur.execute("INSERT INTO rules VALUES(NULL, 'com.quiz.model', 1, 0, 0, 1)")
        self.cur.execute("INSERT INTO rules VALUES(NULL, 'com.quiz.model', 1, 0, 0, 0)")
        self.con.commit()

    def set_tag(self, qnum, tag):
        if tag is not None:
            self.cur.execute("SELECT COUNT(id) FROM tags WHERE name=?", (tag,))
            rc = self.cur.fetchone()[0]
            tnum = None
            if rc > 1:
                raise ValueError('more than one row with the tag')
            if rc == 0:
                self.cur.execute("INSERT INTO tags VALUES(NULL, ?)", (tag,))
                self.cur.execute("SELECT last_insert_rowid()")
                tnum = self.cur.fetchone()[0]
            else:
                self.cur.execute("SELECT id FROM tags WHERE name=?", (tag,))
                tnum = self.cur.fetchone()[0]
            #print(tnum, qnum)
            try:
                self.cur.execute("INSERT INTO tags_quests VALUES(?, ?)", (tnum, qnum,))
            except Exception as e:
                print(e)
                #raise e
            finally:
                self.con.commit()

    def add_question(self, question_json):
        quest_dict = json.loads(question_json)
        tag = quest_dict["tag"]
        question_tuple = (quest_dict["title"], quest_dict["description"], quest_dict["difficulty"], quest_dict["addon_id"])
        self.cur.execute("PRAGMA foreign_keys = ON")
        self.cur.execute("INSERT INTO questions VALUES(NULL, ?, ?, ?, ?)", question_tuple)
        self.cur.execute("SELECT last_insert_rowid()")
        qnum = self.cur.fetchone()[0]
        self.con.commit()
        self.set_tag(qnum, tag)

    def get_group(self, tag_name: str):
        self.cur.execute("""SELECT questions.id, questions.title, questions.description,
                            questions.difficulty, questions.addon_id, addons.url
                            FROM questions JOIN tags_quests ON tags_quests.quest_id=questions.id
                            JOIN tags ON tags_quests.tag_id=tags.id
                            LEFT JOIN addons ON questions.addon_id=addons.id WHERE tags.name = ?""", (tag_name,))
        fetch_res = self.cur.fetchall()
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
        return json.dumps(ret_res)
        #self.con.commit()

    def get_user_id(self, user_name):
        print("gettind id", user_name)
        self.cur.execute("SELECT id FROM users WHERE name=?", (user_name,))
        res = self.cur.fetchone()
        if res is not None:
            return res[0]
        else:
            raise ApplicationError("com.wrong_user_id", "wrong user name")

    #TODO database cleaning

    async def start_quiz(self, game_name, participants):
        participants_list = []

        async def on_question_posted(quest_json):
            print("Got question")
            print(json.loads(quest_json))
            self.prev_question_id = self.cur_question_id
            self.cur_question_id = json.loads(quest_json)["id"]
            self.start = time.time()
            if self.cur_question_id == -1:
                print(game_name, "finished")
                await self.register(None, full_game_name + ".add_answer")
                print("disabling participants")
                for user_id in participants_list:
                    self.cur.execute("UPDATE users SET role_id=NULL WHERE id=?", (user_id, ))
                self.con.commit()
                self.cur_game.unsubscribe()

        self.cur.execute("SELECT id from roles WHERE name=?", ("mobile-client",))
        user_role_id = self.cur.fetchone()[0]
        self.cur.execute("INSERT INTO games VALUES(NULL, ?, NULL)", (game_name, ))
        self.cur.execute("SELECT last_insert_rowid()")
        self.cur_game_id = self.cur.fetchone()[0]
        full_game_name = "com."+game_name

        wordfile = xp.locate_wordfile()
        mywords = xp.generate_wordlist(wordfile=wordfile, min_length=5, max_length=5)

        for user_name in participants:
            secret = xp.generate_xkcdpassword(mywords, acrostic="hi", delimiter=":")
            #secret = string.capwords(secret)
            self.cur.execute("INSERT INTO users VALUES(NULL, ?, ?, ?)", (user_name, secret, user_role_id))
            self.cur.execute("SELECT last_insert_rowid()")
            cur_user_id = self.cur.fetchone()[0]
            participants_list.append(cur_user_id)
            self.cur.execute("INSERT INTO user_game VALUES(?, ?)", (cur_user_id, self.cur_game_id))
        self.con.commit()
        self.cur_game = await self.subscribe(on_question_posted, full_game_name+".questions")

        await self.register(functools.partial(self.add_answer, game_name=game_name), full_game_name+".add_answer")
        print("subscribed")

    def onConnect(self):
        self.con = sqlite3.connect("quiz.db")
        #TODO dbase name from arguments
        self.cur = self.con.cursor()
        self.cur.execute("PRAGMA foreign_keys = ON")
        if "create_table" in self.config.extra:
            self.create_tables()
        self.start = None
        self.cur_question_id = None
        self.prev_question_id = None
        self.cur_game = None
        self.name = "database"
        self.secret = "55555"
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
        #if create_table:
        #   self.create_tables()
        # self.init_assistant()
        # self.con.close()

        def get_rules(self):
            self.cur.execute("SELECT * FROM rules")

        print("session attached")
        try:
            await self.register(self.get_user_id, "com.assistant.get_user_id")
            #yield self.register(self.add_user, "com.admin.add_user")
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
    if len(sys.argv) < 2:
        raise ValueError("Irregular argument number, at least 2 expected")
    else:
        environ["database_name"] = sys.argv[1]
    #runner = ApplicationRunner(u"ws://127.0.0.1:8080/ws", u"realm1", {"database_name": "quiz.db", "create_table": None})
    runner = ApplicationRunner(u"ws://127.0.0.1:8080/ws", u"realm1", {"database_name": "quiz.db"})
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