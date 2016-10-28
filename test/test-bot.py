import json
import unittest
from unittest.mock import patch
from bot import AttendanceBot
import yaml
import dbutils


class TestBot(unittest.TestCase):
    bot = None
    test_db = dbutils.connect_to_db()

    @classmethod
    def setUpClass(cls):
        settings = yaml.load(open("../settings.yaml"))
        cls.bot = AttendanceBot(settings)
        cur = cls.test_db.cursor()
        cur.execute("CREATE TABLE if not exists Members(slack_id varchar(255) not null primary key, real_name varchar(255) not null)")
        cur.execute("CREATE TABLE if not exists Posts(post_timestamp varchar(255) not null primary key, rehearsal_date varchar(255) unique not null)")
        cur.execute("CREATE TABLE if not exists Attendance(slack_id varchar(255) references Members(slack_id), rehearsal_date varchar(255) references Posts(rehearsal_date), Present boolean)")
        dbutils.commit_or_rollback(cls.test_db)

    def setUp(self):
        self.test_db.cursor().execute("INSERT INTO Members VALUES(%s, %s)", ("12345", "Bobby Tables"))
        self.test_db.cursor().execute("INSERT INTO Posts VALUES(%s, %s)", ("1477908000", "31/10/16"))
        self.test_db.cursor().execute("INSERT INTO Attendance(slack_id,rehearsal_date) VALUES(%s, %s)", ("12345", "31/10/16"))
        dbutils.commit_or_rollback(self.test_db)

    def test_init_func(self):
        self.assertEqual(self.bot.bot_name, "attendance-bot")
        self.assertEqual(self.bot.bot_emoji, ":memo:")

    @patch("bot.SlackClient.api_call")
    def test_post_message_posts_message(self, mock_api_call):
        expected_value = ['12345', 'abc123']
        mock_api_call.return_value = {"ts": "12345", "channel": "abc123"}
        result = self.bot.post_message("test_message")
        self.assertEqual(result, expected_value)

    @patch("bot.SlackClient.api_call")
    def test_post_message_persists_timestamp(self, mock_api_call):
        mock_api_call.return_value = {"ts": "543210", "channel": "abc123"}
        self.bot.post_message("test_message")
        cur = self.test_db.cursor()
        cur.execute("SELECT * FROM posts WHERE post_timestamp='543210'")
        result = cur.fetchone()
        self.assertIsNotNone(result)

    @patch("bot.SlackClient.api_call")
    def test_post_message_stores_post_date(self, mock_api_call):
        test_ts = "1477581478"
        expected_value = "27/10/16"
        mock_api_call.return_value = {"ts": "1477581478", "channel": "abc123"}
        self.bot.post_message("test_message")
        cur = self.test_db.cursor()
        cur.execute("select rehearsal_date from posts where post_timestamp=(%s)", (test_ts,))
        result = cur.fetchone()[0]
        self.assertEqual(result, expected_value)

    def test_get_latest_post_timestamp(self):
        cur = self.test_db.cursor()
        cur.execute("insert into posts values('1477908005', '30/10/16'), ('1477908006', '32/10/16'), ('1477908007', '33/10/16')")
        dbutils.commit_or_rollback(self.test_db)
        expected_value = "1477908007"
        result = self.bot.get_latest_post_timestamp()
        self.assertEqual(result, expected_value)

    @patch("bot.SlackClient.api_call")
    def test_get_reactions(self, mock_api_call):
        expected_value = [{"name": "foo", "users": ["user1", "user2"]}]
        mock_api_call.return_value = {"message": {"reactions": expected_value}}
        result = self.bot.get_reactions("test_timestamp", "test_channel")
        self.assertEqual(result, expected_value)

    @patch("bot.SlackClient.api_call")
    def test_get_real_name_not_present(self, mock_api_call):
        expected_value = "Michael Bluth"
        mock_api_call.return_value = {"ok": "true", "user": {"profile": {"real_name": "Michael Bluth"}}}

        result = self.bot.get_real_name("101010")
        self.assertEqual(result, expected_value)

    def test_get_real_name_is_present(self):
        expected_value = "Bobby Tables"
        result = self.bot.get_real_name("12345")
        self.assertEqual(result, expected_value)

    def test_record_presence(self):
        expected_value = True
        cur = self.test_db.cursor()
        self.bot.record_presence("12345", "31/10/16")
        cur.execute("select Present from Attendance where slack_id='12345' and rehearsal_date='31/10/16'")
        result = cur.fetchone()[0]
        self.assertEqual(result, expected_value)

    def test_record_absence(self):
        expected_value = False
        cur = self.test_db.cursor()
        self.bot.record_absence("12345", "31/10/16")
        cur.execute("select Present from Attendance where slack_id='12345' and rehearsal_date='31/10/16'")
        result = cur.fetchone()[0]
        self.assertEqual(result, expected_value)

    def tearDown(self):
        cur = self.test_db.cursor()
        cur.execute("delete from attendance; delete from posts; delete from members")
        dbutils.commit_or_rollback(self.test_db)

    @classmethod
    def tearDownClass(cls):
        cls.bot.db.close()
        cur = cls.test_db.cursor()
        cur.execute("DROP TABLE Members, Posts, Attendance")
        dbutils.commit_or_rollback(cls.test_db)
        cls.test_db.close()
