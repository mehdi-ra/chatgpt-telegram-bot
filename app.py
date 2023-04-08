import telegram
from telegram.ext import CommandHandler, Updater, MessageHandler, Filters
from datetime import datetime, timedelta
import openai
from telegram import ParseMode
import redis
import threading
from queue import Queue


white_list = []
black_list = []

bot = telegram.Bot(token='XXX')

last_message_time = {}

openai.api_key = "XXX"
model_id = "gpt-3.5-turbo"

redis_client = redis.Redis()

def check_message(question):
   single_letters = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']

   common_words = ['the', 'an', 'and', 'or', 'but', 'so', 'of', 'in', 'on', 'at', 'to', 'for', 'with']

   conversational_words = ['hi', 'hello', 'hey', 'bye', 'goodbye', 'ok', 'yes', 'no', 'thanks', 'please', 'excuse me', 'sorry', 'pardon']

   abbreviations = ['lol', 'omg', 'btw', 'tbh', 'imo', 'fyi', 'wtf', 'idk', 'smh', 'rofl', 'brb', 'jk']

   random_chars = ['!', '@', '#', '$', '%', '^', '&', '*', '(', ')', '-', '+', '=', '/', '\\', "'", "`", "~"]
   persian_stop_words = [
    "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه", "صد", "هزار",
    "میلیون", "میلیارد", "تومان", "ریال", "سلام", "درود", "سپاس", "ممنون", "خداحافظ",
    "بله", "نه", "مرسی", "لطفا", "ببخشید", "معذرت", "با عرض پوزش", "کوچیک",
    "خیلی", "بسیار", "آره", "نه", "بفرمایید", "خودتان", "همین", "اگر", "ولی", "اما",
    "به", "از", "برای", "در", "با", "بهترین", "زیبا", "جذاب", "عالی", "بیشتر",
    "کمتر", "بد", "خوب", "عجب", "چه", "چطور", "چرا", "هنوز", "همیشه", "گاهی"
]

   numbers= [1,2,3,4,5,6,7,8,9,0]

   full_list = random_chars + abbreviations + conversational_words + common_words + single_letters + numbers + persian_stop_words
   if question in full_list or len(question) < 5:
       return False
   else:
        return True

def get_message_history(user_id):
    message_history = redis_client.get(f"message_history_{user_id}")
    if message_history:
        message_history = eval(message_history)[-5:]

    else:
        message_history = []

    return message_history

def update_message_history(user_id, message_history):
    redis_client.set(f"message_history_{user_id}", str(message_history))


def limit_user_questions(user_id,update):
    global last_message_time
    user, username, first_name, last_name,user_id = user_info(update)
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

def predict(user_id, input):
    # get message history for the user
    message_history = get_message_history(user_id)

    # add new message to history
    message_history.append({"role": "user", "content": f"{input}"})
  
    # get completion from OpenAI API
    response_queue = Queue()
    def run_openai():
        completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=message_history,
        temperature=0.5,
        )

    # get response from completion
        response = completion.choices[0].message.content
        message_history.append({"role": "assistant", "content": f"{response}"})

    # update message history in Redis
        update_message_history(user_id, message_history)
        response_queue.put(response)
        
    threading.Thread(target=run_openai).start()
    response = response_queue.get()
    return response


def user_info(update):
    user = update.message.from_user if update.message.from_user is not None else "N/A"
    username = user.username #if user.username is not None else "N/A"
    first_name = user.first_name# if user.first_name is not None else "N/A"
    last_name = user.last_name #if user.last_name is not None else "N/A"
    user_id = user.id #if user.user_id is not None else "N/A"

    return user, username, first_name, last_name, user_id

def start_handler(update, context):
    user, username, first_name, last_name,user_id = user_info(update)
    context.bot.send_message(chat_id=user_id, text="سلام عرض شد ")
    context.bot.send_message(chat_id=user_id, text="سوالت رو بپرس تا chatgpt بهت جواب بده")


def message_handler(update, context):
    user, username, first_name, last_name,user_id = user_info(update)

    if user_id in black_list:
        return


    message_history = get_message_history(user_id)

    if not message_history:
        message_history = [{"role": "assistant", "content": f"Hi {user_id}, how can I assist you?"}]

    if not limit_user_questions(user_id,update):
        update.message.reply_text("Please wait 20 seconds between sending messages.")
        
        return

    question = update.message.text

    if check_message(question):
        context.bot.send_chat_action(chat_id=update.effective_chat.id, action=telegram.ChatAction.TYPING)

        response = predict(user_id, question)

        try:
            f_response = response.replace("```", "<pre>",1).replace("```", "</pre>")
            context.bot.send_message(chat_id=user_id, text=f_response,parse_mode="HTML")
        except telegram.error.BadRequest:
            context.bot.send_message(chat_id=user_id, text=response)

        
    else:
        context.bot.send_message(chat_id=user_id, text="your message is too short")
        last_message_time.pop(user_id)



def image_handler(update, context):
    user, username, first_name, last_name,user_id = user_info(update)
    search = context.args

    if search == []:
        context.bot.send_message(chat_id=user_id, text="use /image with a description\nexample: <pre>/image white cat</pre>",parse_mode="HTML")
    else:
        context.bot.send_chat_action(chat_id=user_id, action=telegram.ChatAction.UPLOAD_PHOTO)
        search = ' '.join(search)
        try:
            context.bot.send_chat_action(chat_id=user_id, action=telegram.ChatAction.UPLOAD_PHOTO)
            response = openai.Image.create(
            prompt=search,
            n=1,
            size="1024x1024"
            )
            image_url = response['data'][0]['url']



            context.bot.send_photo(chat_id=user_id, photo=image_url, caption=search)
            

        except openai.error.OpenAIError as e:
            pass

def help_handler(update,context):
    user, username, first_name, last_name,user_id = user_info(update)
    help_message = """
لطفا از پیام هایی مثل سلام , خداحافظ , نه , اره , اوکی و ... استفاده نکنید که تجربی بهتری در استفاده از این ربات داشته باشین

    /start برای شروع کار با ربات
    /image برای ایجاد عکس
    /help نمایش این پیام

این ربات از ورژن 3.5 جی پی تی استفاده میکنه و همینطور مفهوم مکالمه رو تا 5 پیام قبلی میفهمه و میتونه نسبت به اونها به شما جواب بده

    """
    context.bot.send_message(chat_id=user_id, text=help_message)


updater = Updater(token='XXX', use_context=True)
start_handler = CommandHandler('start', start_handler)
message_handler = MessageHandler(Filters.text & (~Filters.command), message_handler)
image_handler = CommandHandler('image', image_handler)
help_handler = CommandHandler('help', help_handler)

updater.dispatcher.add_handler(start_handler)
updater.dispatcher.add_handler(message_handler)
updater.dispatcher.add_handler(image_handler)
updater.dispatcher.add_handler(help_handler)


# Start the bot
updater.start_polling()
updater.idle()
