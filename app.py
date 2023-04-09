import telegram
import logging
from telegram.ext import CommandHandler, Updater, MessageHandler, Filters
from datetime import datetime, timedelta
import openai
import time
import redis
import random
from kafka import KafkaProducer, KafkaConsumer
import json
import threading
import sentry_sdk


sentry_sdk.init(
   XXX
)




bot = telegram.Bot(token='XXX')

last_message_time = {}

white_list = [ ]
black_list = []

openai.api_key = "XXX"
model_id = "gpt-3.5-turbo"

redis_client = redis.StrictRedis()
user_questions_queue = {}

producer = KafkaProducer(bootstrap_servers=['xxx'])


def check_message(question):
    full_list = set(['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z',
                '0', '1', '2', '3', '4', '5', '6', '7', '8', '9','the', 'an', 'and', 'or', 'but', 'so', 'of', 'in', 'on', 'at', 'to', 'for', 'with','hi',
                'hello', 'hey', 'bye', 'goodbye', 'ok', 'yes', 'no', 'thanks', 'please', 'excuse me', 'sorry', 'pardon','lol', 'omg', 'btw', 'tbh', 'imo',
                'fyi', 'wtf', 'idk', 'smh', 'rofl', 'brb', 'jk', '!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '-', '+', '=', '/', '\\', "'", "`", "~",
                "ﯽﮐ", "ﺩﻭ", "ﺲﻫ", "ﭻﻫﺍﺭ", "ﭗﻨﺟ", "ﺶﺷ", "ﻪﻔﺗ", "ﻪﺸﺗ", "ﻦﻫ", "ﺹﺩ", "ﻩﺯﺍﺭ",
                "ﻢﯿﻠﯾﻮﻧ", "ﻢﯿﻠﯾﺍﺭﺩ", "ﺕﻮﻣﺎﻧ", "ﺮﯾﺎﻟ", "ﺱﻼﻣ", "ﺩﺭﻭﺩ", "ﺲﭘﺎﺳ", "ﻢﻤﻧﻮﻧ", "ﺥﺩﺎﺣﺎﻔﻇ",
                "ﺐﻠﻫ", "ﻦﻫ", "ﻡﺮﺴﯾ", "ﻞﻄﻓﺍ", "ﺐﺒﺨﺸﯾﺩ", "ﻢﻋﺫﺮﺗ", "ﺏﺍ ﻉﺮﺿ ﭖﻭﺰﺷ", "ﮎﻮﭽﯿﮐ",
                "ﺦﯿﻠﯾ", "ﺐﺴﯾﺍﺭ", "ﺁﺮﻫ", "ﻦﻫ", "ﺐﻓﺮﻣﺎﯿﯾﺩ", "ﺥﻭﺪﺗﺎﻧ", "ﻪﻤﯿﻧ", "ﺎﮔﺭ", "ﻮﻠﯾ", "ﺎﻣﺍ",
                "ﺐﻫ", "ﺍﺯ", "ﺏﺭﺎﯾ", "ﺩﺭ", "ﺏﺍ", "ﺐﻬﺗﺮﯿﻧ", "ﺰﯿﺑﺍ", "ﺝﺫﺎﺑ", "ﻉﺎﻠﯾ", "ﺐﯿﺸﺗﺭ",
                "ﮏﻤﺗﺭ", "ﺏﺩ", "ﺥﻮﺑ", "ﻊﺠﺑ", "ﭻﻫ", "ﭻﻃﻭﺭ", "ﭺﺭﺍ", "ﻪﻧﻭﺯ", "ﻪﻤﯿﺸﻫ", "ﮒﺎﻬﯾ"
                ])
    if question in full_list or len(question) < 5:
        return False
    else:
        return True


def get_message_history(user_id):
    message_history = redis_client.get(f"message_history_{user_id}")
    if message_history:
        message_history = eval(message_history)[-3:]

    else:
        message_history = []

    return message_history

def update_message_history(user_id, message_history):
    redis_client.set(f"message_history_{user_id}", str(message_history),ex=7200)


def limit_user_questions(user_id):
    #global last_message_time
    last_message_time = {}

    now = datetime.now()

    # Check if the user has sent a message too quickly
    if user_id not in white_list:
        if user_id in last_message_time:
            last_time = last_message_time[user_id]
            time_since_last_message = now - last_time
            if time_since_last_message < timedelta(seconds=20):
                return False

    # Update the time when the user last sent a message
    last_message_time[user_id] = now
    return True

def kafka_consumer_loop():
    consumer = KafkaConsumer('xxx', bootstrap_servers=['xxx'])
    for message in consumer:
        time.sleep(2)
        input_data = json.loads(message.value.decode('utf-8'))
        user_id = input_data['user_id']
        first_name = input_data['first_name']
        last_name = input_data['last_name']
        question = input_data['question']
        username = input_data['username']
        bot.send_chat_action(chat_id=user_id, action=telegram.ChatAction.TYPING)
        response = predict(user_id, question)
        bot.send_chat_action(chat_id=user_id, action=telegram.ChatAction.TYPING)

        try:
            f_response = response.replace("```", "<pre>",1).replace("```", "</pre>")
            bot.send_message(chat_id=user_id, text=f_response,parse_mode="HTML")
        except telegram.error.BadRequest:
            bot.send_message(chat_id=user_id, text=response)


def predict(user_id, input):
    bot.send_chat_action(chat_id=user_id, action=telegram.ChatAction.TYPING)
    
    message_history = get_message_history(user_id)

    message_history.append({"role": "user", "content": f"{input}"})

    try:
        completion = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=message_history,
    )
    except openai.error.RateLimitError as aierrror:
        bot.send_message(chat_id=user_id, text="OpenAI: Our API servers are experiencing high traffic, this doesn't mean there are any problems with your application, Please retry your requests after a brief wait ")


    response = completion.choices[0].message.content
    message_history.append({"role": "assistant", "content": f"{response}"})

    # udate message history in Redis
    update_message_history(user_id, message_history)

    return response

def send_wait_message( user_id):
    bot.send_message(chat_id=user_id, text="Please wait for a response...")
   


def user_info(update):
    user = update.message.from_user if update.message.from_user is not None else "N/A"
    username = user.username #if user.username is not None else "N/A"
    first_name = user.first_name# if user.first_name is not None else "N/A"
    last_name = user.last_name #if user.last_name is not None else "N/A"
    user_id = user.id #if user.user_id is not None else "N/A"

    return username, first_name, last_name, user_id

def start_handler(update, context):
    username, first_name, last_name,user_id = user_info(update)
    context.bot.send_message(chat_id=user_id, text="سلام عرض شد ")
    context.bot.send_message(chat_id=user_id, text="سوالت رو بپرس تا chatgpt بهت جواب بده")


def message_handler(update, context):
    username, first_name, last_name,user_id = user_info(update)

    if user_id in black_list:
        return


    message_history = get_message_history(user_id)

    if not message_history:
        message_history = [{"role": "assistant", "content": f"Hi {user_id}, how can I assist you?"}]

    if not limit_user_questions(user_id):
        update.message.reply_text("Please wait 20 seconds between sending messages.")
        
        return
    
    question = update.message.text

    if check_message(question):
        send_wait_message(user_id)
        context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.ChatAction.TYPING)
        kaf_message = {"username": username,"user_id": user_id, "last_name": last_name, "first_name": first_name, "question": question}
        producer.send('xxx', json.dumps(kaf_message).encode('utf-8'))
    else:
        context.bot.send_message(chat_id=user_id, text="your message is too short")
        last_message_time.pop(user_id)
        


def help_handler(update,context):

    username, first_name, last_name,user_id = user_info(update)
    help_message = """
لطفا از پیام هایی مثل سلام , خداحافظ , نه , اره , اوکی و ... استفاده نکنید که تجربی بهتری در استفاده از این ربات داشته باشین

    /start برای شروع کار با ربات
    /image برای ایجاد عکس
    /help نمایش این پیام

این ربات از ورژن 3.5 جی پی تی استفاده میکنه و همینطور مفهوم مکالمه رو میفهمه و میتونه نسبت به اونها به شما جواب بده

    """
    context.bot.send_message(chat_id=user_id, text=help_message)
kafka_consumer_thread = threading.Thread(target=kafka_consumer_loop)
kafka_consumer_thread.start()

updater = Updater(token='XXX', use_context=True)
start_handler = CommandHandler('start', start_handler)
message_handler = MessageHandler(Filters.text & (~Filters.command), message_handler)

help_handler = CommandHandler('help', help_handler)

updater.dispatcher.add_handler(start_handler)
updater.dispatcher.add_handler(message_handler)

updater.dispatcher.add_handler(help_handler)


# Start the bot
updater.start_polling()
updater.idle()
