import json
import sqlite3
import time
import functools
from os import environ
from twisted.internet.defer import inlineCallbacks
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner


class Dbase(ApplicationSession):

    def add_answer(self, game_name, answer_json):
        answer = json.loads(answer_json)
        finish = time.time()
        delt = finish - self.start
        answ_tuple = (answer["question_id"], answer["user_id"], delt, answer["body"])
        if answer["question_id"] == self.cur_question_id:
            self.cur.execute("INSERT INTO answers VALUES(NULL, ?, ?, ?, ?)", answ_tuple)
            print("saved")
            self.con.commit()
            return True
        else:
            print(answer["question_id"], " vs",  self.cur_question_id)
            return False

    def add_user(self, user, rule_ids):
        self.con.commit("INSERT INTO users VALUES(NULL, ?, ?)", user)
        self.cur.execute("SELECT last_insert_rowid()")
        uid = self.cur.fetchone()[0]
        for rid in rule_ids:
            self.cur.execute("INSERT INTO user_rules VALUES(?)", (uid, rid))
        self.con.commit()

    @inlineCallbacks
    def onJoin(self, details):
        self.con = sqlite3.connect(environ["database_name"])
        self.cur = self.con.cursor()
        self.cur.execute("PRAGMA foreign_keys = ON")
        self.start = None
        self.cur_question_id = None
        self.cur_game = None
        #if create_table:
        #   self.create_tables()
            # self.init_assistant()
            # self.con.close()

        def get_rules(self):
            self.cur.execute("SELECT * FROM rules")

        print("session attached")
        try:
            yield self.register(self.add_user, "com.admin.add_user")
            yield self.register(self.add_question, "com.admin.add_question")
            yield self.register(self.get_group, "com.admin.get_group")
            yield self.register(self.create_tables, "com.admin.create_tables")
            yield self.register(self.start_quiz, "com.assistant.start_quiz")
        except Exception as e:
            print(e)
        else:
            print("procedures registered")


    def create_tables(self):
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
        self.cur.execute("""CREATE TABLE users(
                            id INTEGER PRIMARY KEY,
                            name TEXT UNIQUE,
                            secret TEXT)""")
        self.cur.execute("""CREATE TABLE user_rules(
                            user_id INTEGER REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT,
                            rule_id INTEGER REFERENCES rules(id) ON UPDATE CASCADE ON DELETE RESTRICT)""")
        self.cur.execute("""CREATE TABLE answers(
                            id INTEGER PRIMARY KEY,
                            quest_id INTEGER REFERENCES questions(id) ON UPDATE CASCADE ON DELETE RESTRICT,
                            user_id INTEGER REFERENCES  users(id),
                            seconds INT CHECK( seconds>0 AND seconds<=1000),
                            body TEXT)""")
        self.con.commit()

        self.cur.execute("INSERT INTO ad_types VALUES(NULL, 'PICTURE')")
        self.cur.execute("INSERT INTO ad_types VALUES(NULL, 'AUDIO')")
        self.cur.execute("INSERT INTO ad_types VALUES(NULL, 'VIDEO')")
        self.con.commit()

        self.cur.execute("INSERT INTO questions VALUES(NULL, 'Тестовый вопрос 1', 'Просто введи любой ответ', 1, NULL)")
        self.con.commit()

        self.cur.execute("INSERT INTO rules VALUES(NULL, 'com.quiz.model', 1, 0, 0, 1)")
        self.cur.execute("INSERT INTO rules VALUES(NULL, 'com.quiz.model', 1, 0, 0, 0)")
        self.con.commit()

    def set_tag(self, qnum, tag):
        if tag is not None:
            self.cur.execute("SELECT COUNT(id) FROM tags WHERE name=?",(tag,))
            rc = self.cur.fetchone()[0]
            tnum = None
            if rc > 1:
                raise ValueError('more than on row with the tag')
            if rc == 0:
                self.cur.execute("INSERT INTO tags VALUES(NULL, ?)", (tag,))
                self.cur.execute("SELECT last_insert_rowid()")
                tnum = self.cur.fetchone()[0]
            else:
                self.cur.execute("SELECT id FROM tags WHERE name=?", (tag,))
                tnum = self.cur.fetchone()[0]
            print(tnum, qnum)
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
        self.cur.execute("SELECT questions.title, tags.name FROM questions JOIN tags_quests ON tags_quests.quest_id=questions.id JOIN tags ON tags_quests.tag_id=tags.id WHERE tags.name = ?",(tag_name,))
        fetch_res = self.cur.fetchall()
        ret_res = []
        for row in fetch_res:
            qdict = {"title": row[0], "tag": row[1]}
            ret_res.append(qdict)
        return json.dumps(ret_res)
        #self.con.commit()

    @inlineCallbacks
    def start_quiz(self, game_name):
        full_game_name = "com."+game_name

        def on_question_posted(quest_json):
            self.cur_question_id = json.loads(quest_json)["id"]
            self.start = time.time()
            if self.cur_question_id == -1:
                self.cur_game.unsubscribe()

        yield self.register(functools.partial(self.add_answer, game_name=game_name), full_game_name+".add_answer")
        self.cur_game = yield self.subscribe(on_question_posted, full_game_name+".questions")
        print("subscribed")

def main():
    import  sys
    if len(sys.argv) < 2:
        raise ValueError("Irregular argument number, at least 2 expexcted")
    else:
        environ["database_name"] = sys.argv[1]
    runner = ApplicationRunner(u"ws://127.0.0.1:8080/ws", u"realm1")
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