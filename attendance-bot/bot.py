from slackclient import SlackClient
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apiclient import discovery
from oauth2client import service_account
import httplib2
import json
import dbutils

def schedule(day, hour, mins, func, args):
    sched = BackgroundScheduler()

    @sched.scheduled_job('cron', day_of_week=day, hour=hour, minute=mins)
    def scheduled_job():
        func(*args)

    sched.start()
    print("Post scheduled for {day} at {hour}:{mins}!".format(day=day, hour=hour, mins=mins))


class AttendanceBot(object):

    def __init__(self, settings):
        token = os.environ["BOT_TOKEN"]

        self.bot_name = settings.get("bot-name")
        self.bot_emoji = ":{emoji}:".format(emoji=settings.get("bot-emoji"))  # wrap emoji name in colons
        self.client = SlackClient(token)
        self.channel = settings.get("channel")
        self.emoji_present = settings.get("emoji-present")
        self.emoji_absent = settings.get("emoji-absent")

        self.sheet_id = settings.get("spreadsheet-id")

        self.db = dbutils.connect_to_db()


        # # schedule the rehearsal message post
        # schedule(
        #     settings.get("rehearsal-day"),
        #     settings.get("post-hour"),
        #     settings.get("post-minute"),
        #     self.post_message_with_reactions,
        #     [settings.get("rehearsal-message")]
        # )

    # post a message and return the timestamp of the message


    def post_message(self, message):
        res = self.client.api_call(
            "chat.postMessage", channel=self.channel, text=message,
            username=self.bot_name, icon_emoji=self.bot_emoji
        )
        ts = res.get("ts")
        channelID = res.get("channel")
        return [ts, channelID]

    # post a message, react to it, and return the timestamp of the message
    def post_message_with_reactions(self, message):
        post_data = self.post_message(message)
        ts = post_data[0]
        channel = post_data[1]

        print(self.client.api_call(
            "reactions.add", channel=channel, timestamp=ts, name=self.emoji_present
        ))

        self.client.api_call(
            "reactions.add", channel=channel, timestamp=ts, name=self.emoji_absent
        )
        return ts

    def get_reactions(self, ts, channel):
        res = self.client.api_call(
            "reactions.get", channel=channel, timestamp=ts
        )
        return res.get("message").get("reactions")

    def get_real_name(self, user_id):
        cur = self.db.cursor()
        cur.execute("SELECT RealName FROM Members WHERE SlackID=(%s)", (user_id,))
        result = cur.fetchone()
        name = ""
        if (result == None): # if the name isn't in the db, find it through an api call and store it for next time
             result = self.client.api_call(
            "users.info", user=user_id
            )
             name = result.get("user").get("profile").get("real_name")
             cur.execute("INSERT INTO members VALUES (%s, %s)", (user_id, name))
             try:
                self.db.commit()
             except:
                self.db.rollback()
             finally:
                 pass

        else:
            name = result[0]
        return name

    def get_google_credentials(self):
        scopes = "https://www.googleapis.com/auth/spreadsheets"
        config = json.load(os.environ['GOOGLE_CONFIG'])
        return service_account.ServiceAccountCredentials.from_json_keyfile_dict(config)

#    def get_range_for_name(self, name, date):


    def update_spreadsheet(self, names, date):
        http = httplib2.Http()
        http = self.get_google_credentials().authorize(http)
        discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?'
                        'version=v4')
        service = discovery.build('sheets', 'v4', http=http,
                                  discoveryServiceUrl=discoveryUrl)