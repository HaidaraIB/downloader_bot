import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

from telethon import (
    TelegramClient,
    events,
    errors,
)

from telethon.tl.patched import (
    Message, 
)

import os
import pickle
import math
from dotenv import load_dotenv

load_dotenv()

if not os.path.exists("documents"):
    os.makedirs(name="documents")

client = TelegramClient(session='session_name',
                        api_id=int(os.getenv("API_ID")),
                        api_hash=os.getenv('API_HASH')).start(bot_token=os.getenv('BOT_TOKEN'))

data_list = {}
downloading = []

if os.path.exists('data_list.pickle'):
    with open('data_list.pickle', 'rb') as f:
        data_list = pickle.load(f)


async def download(doc:dict, message:Message):

    try:
        offset = os.path.getsize(doc['file_path'])
    except OSError:
        offset = 0
    curr = prev_curr = (offset/doc['size'])*100

    prog:Message = await message.reply(f"__{curr:.2f} of 100%__")

    with open(doc['file_path'], 'ab') as fd:

        downloading.append(doc['access_hash'])

        async for chunk in client.iter_download(file=doc['document'], offset=offset):

            if doc['access_hash'] in downloading:
                fd.write(chunk)
                offset += len(chunk)
                curr = (offset/doc['size'])*100

                try:
                    if math.floor(curr) == math.floor(prev_curr + 1):
                        bar_width = int(offset/doc['size'] * 10)
                        filled_bar = '▓' * bar_width
                        empty_bar = '░' * (10 - bar_width)
                        updated_text = f"""`{doc['access_hash']}`:

__{curr:.2f} of 100__%
```[{filled_bar}{empty_bar}]```"""
                        await prog.edit(text=updated_text)
                        prev_curr = math.floor(curr)

                except errors.rpcerrorlist.MessageNotModifiedError:
                    pass
    doc['finished'] = True




@client.on(events.NewMessage(pattern="^pause$|^pause$"))
async def pause_download(event: events.NewMessage.Event):
    msg: Message = event.message
    if event.is_private and msg.is_reply and event.sender_id == int(os.getenv("OWNER_ID")):

        reply_msg: Message = await msg.get_reply_message()

        if not reply_msg.raw_text.split('\n')[0][:-1].isnumeric():
            return
        
        acc_hash = int(reply_msg.raw_text.split('\n')[0][:-1])

        if data_list.get(acc_hash, None):

            if acc_hash in downloading:
                downloading.remove(acc_hash)
                await msg.respond(f"`{acc_hash}` paused.")

            else:
                await msg.respond(f"`{acc_hash}` not downloading.")

        else:
            await msg.respond(f"`{acc_hash}` not found")



@client.on(events.NewMessage(pattern="^/shownotcompleted$", forwards=False))
async def show_not_completed(event: events.NewMessage.Event):
    if event.is_private and event.sender_id == int(os.getenv("OWNER_ID")):

        for doc in data_list.values():

            if not doc['finished']:
                await client.send_message(entity=int(os.getenv("OWNER_ID")),
                                          message=f"`{doc['access_hash']}`",
                                          reply_to=doc['message_document_id'])




@client.on(events.NewMessage(pattern="^\d+$|^-\d+$", forwards=False))
async def resume_by_hash(event: events.NewMessage.Event):
    if event.is_private and event.sender_id == int(os.getenv("OWNER_ID")):
        msg: Message = event.message
        doc = None
        if data_list.get(int(msg.text), None):

            doc = data_list[int(msg.text)]

            if int(msg.text) in downloading:
                await msg.respond(f"`{msg.text}` already downloading")

                return
            
        else:
            await msg.respond(f"`{msg.text}` not found")

            return
        
        await download(doc=doc, message=msg)





@client.on(events.NewMessage(forwards=True))
async def handle_new_message(event: events.NewMessage.Event):
    if event.is_private and event.sender_id == int(os.getenv("OWNER_ID")):

        msg: Message = event.message
        acc_hash = msg.document.access_hash

        if data_list.get(acc_hash, None):

            if acc_hash in downloading:
                await msg.respond(f"`{acc_hash}` already downloading")

            else:
                await download(doc=data_list[acc_hash], message=msg)

            return

        doc = {
            'access_hash':acc_hash,
            'size': msg.document.size,
            'file_path': f'documents/{acc_hash}.{msg.media.document.mime_type.split('/')[-1]}',
            'document': msg.document,
            'message_document_id': msg.id,
            'finished':False,
        }
        data_list[acc_hash] = doc
        with open('data_list.pickle', mode='wb') as f:
            pickle.dump(data_list, f)

        await download(doc=doc, message=msg)


with client:
    client.run_until_disconnected()
