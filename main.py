import disnake
from disnake.ext import commands
from disnake.utils import find
import logging
from datetime import datetime
import motor.motor_asyncio
import asyncio
import aiohttp
from decouple import config
import os
# import re # clean prefix
#import discordspy
import inspect  
# slash commands notes: desc must be <=100 chars, only 25 options max, can't send files with inter - must get channel ID then send via channel
from cogs.buttons import ButtonsCog  # need to enter the cogs folder to grab uncat_data (folder also contains an __init__.py, this allows it to be included as a package.)
DefaultButtons = ButtonsCog.DefaultButtons  # , view=DefaultButtons()
from cogs.uncat_data import UncatDataCog  # import the join guild msg


# create logging, see https://docs.python.org/3/howto/logging.html
now = datetime.now()  # grabs date
current_date = now.strftime("%Y_%m_%d")  # formats date, year, month, day
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)  # info informs on rate limit hits
# creates folder with current date name, or writes to it if it exists
handler = logging.FileHandler(filename='./Logs/discord-logs.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))  # formats logging message
logger.addHandler(handler)
# ###########################

# used in help cmd
description = "Ever wanted to 'shuffle' through Spotify's library and see what music you discover? I'll do that for you! You can filter to specific genres (over 5000+), years, artists, or albums - whatever the case, I'll grab a random song and send it your way!"

# main.py contains various important congifs, such as loading into cogs, on_ready, the prefix commands, and database

intents = disnake.Intents.default()
# intents.members = True #I don't have members intent, need to request it

# begin database session, for prefixes and such
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(config('mongo_db'))
db = mongo_client["discord_data"]  # this should be discord_data
collection = db["settings"]  # this should be settings (ALSO CHECK BELOW THIS)

# cache of prefixes in dict to reduce strain on db, added as servers use commands for the first time each restart
base = {}


async def get_prefix(client, message):
    if not message.guild:
        return commands.when_mentioned_or("?")(client, message)
        # if not in guild (i.e dm), default to ?
    else:
        if message.guild.id in base:
            pass
            # if prefix is already cached, we don't need to open database
        else:
            # if prefix isn't cached, grab it from database and add it to base
            try:
                # searches database for server id
                data = await collection.find_one({"guildid": message.guild.id})
                base[message.guild.id] = data["prefix"]  # guild.id is the key, prefix is the value
            except TypeError:
                # if server not in database, create database entry
                base[message.guild.id] = "?"  # default is ?
                collection.find_one_and_update({'guildid': message.guild.id},
                                               {'$set': {'guildid': message.guild.id, 'prefix': '?', 'name': message.guild.name}},
                                               upsert=True)
        return commands.when_mentioned_or(base[message.guild.id])(client, message)

# help_command=help_command - this is not needed, as it is defined in the help.py cog instead as:  bot.help_command = help_command
# prefix is defined by above function (it defaults to ?, this can be changed per server). All commands are case insensitive.
bot = commands.AutoShardedBot(command_prefix=get_prefix, description=description, intents=intents, case_insensitive=True, status=disnake.Status.online, activity=disnake.Game("RandomSongsBot - I shuffle through Spotify to find you music!"), allowed_mentions=disnake.AllowedMentions(roles=False, everyone=False))
bot._BotBase__cogs = commands.core._CaseInsensitiveDict()  # makes cog names case insensitive, useful for help command
# allowed_mentions - replaces mentions of roles or everyone into non-mention text versions

# bot variable to use across cogs, should avoid using multiple sessions,
bot.session = aiohttp.ClientSession()  # note this is deprecated and will probably be disabled at some point, needs to be put in some sort of async loop
bot.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(config('mongo_db'))

firstrun = True  # default value for the on_ready, this is to prevent multiple runs of it


@bot.event
async def on_ready():
    # on_ready gets can run more than just when the bot is started
    # so we don't need to do all the checks everytime
    global firstrun
    # DON'T RUN DISCORD API CALLS INSIDE ON_READY AS IT CAN BE ABUSIVE
    if firstrun is True:
        # console prints
        print('Logged in as')
        print(bot.user.name)
        print(bot.user.id)
        print('------')
        print(f"Startup Time: {str(datetime.utcnow())}")
        print(f"Guilds Added: {str(len(bot.guilds))}")

        dbq = collection.find()
        # grabs all server id's in the database, and all servers the bot is in
        dbguilds = [doc['guildid'] async for doc in dbq]
        botguilds = [guild.id for guild in bot.guilds]

        # If when we start the bot there are more guilds in the db then the bot see's as joined
        # we remove those guilds from the db
        if len(dbguilds) > len(botguilds):
            for guildid in dbguilds:
                if guildid not in botguilds:
                    dbq = await collection.find_one({"guildid": guildid})  # need to await find_one
                    logging.info(f"Guild {dbq['name']} ({guildid}) was removed while the bot was offline. Removing from db.")
                    collection.delete_one({'guildid': guildid})

        # Else if the bot see's more guilds than what is present in the db we add the missing guilds with default settings
        elif len(dbguilds) < len(botguilds):
            for guildid in botguilds:
                if guildid not in dbguilds:
                    guild2add = bot.get_guild(guildid)
                    logging.info(f"Guild {guild2add.name} ({guild2add.id}) was added while the bot was offline.  Adding to db.")
                    collection.find_one_and_update({'guildid': guild2add.id},
                                                   {'$set': {'guildid': guild2add.id, 'prefix': '?', 'name': guild2add.name}},
                                                   upsert=True)
                    base[guild2add.id] = "?"  # default is ?, add the new guild to the cache
        firstrun = False
    else:
        logging.info('Re-running on_ready, but not first run so doing nothing.')


# sends message on server join
# adds server info to db
# adds default prefix+serverid to the bot cache to reduce db usage.
@bot.event
async def on_guild_join(guild):
    collection.find_one_and_update({'guildid': guild.id},
                                   {'$set': {'guildid': guild.id, 'prefix': '?', 'name': guild.name}},
                                   upsert=True)
    # when we join a guild, add guild.id and default prefix to cache
    base_update = {guild.id: "?"}
    base.update(base_update)

    #  the content sent on guild join
    join_msg = UncatDataCog.join_msg
    # replace guild.name with the actual attribute
    join_msg = join_msg.replace("guild.name!", f"{guild.name}!")

    embed = disnake.Embed(title="Support", description="If you have any questions, suggestions, or wish to know more - please [join my support server](https://discord.gg/WchY5gSGyh)\nIf you wish to invite me to another server, [use this link](https://discord.com/api/oauth2/authorize?client_id=962994568637321226&permissions=2147601472&scope=bot%20applications.commands).", color=disnake.Colour.from_rgb(198, 146, 148))

    # first try to find the top channel I can send to, else look for a general channel if I hit an error
    await asyncio.sleep(1)
    try:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                if channel.permissions_for(guild.me).embed_links:
                    await channel.send(embed=embed, content=join_msg, view=DefaultButtons())
                else:
                    await channel.send(join_msg, view=DefaultButtons())
            break
    except Exception as e:
        # accounts for servers that may block new joins from chatting until they have a role or somethin - wait 5 mins
        print(f"Failed to send join msg: {e}")
        await asyncio.sleep(300)
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                if channel.permissions_for(guild.me).embed_links:
                    await channel.send(embed=embed, content=join_msg, view=DefaultButtons())
                else:
                    await channel.send(join_msg, view=DefaultButtons())
            break
    channel = bot.get_channel(978760898594361355)  # joins chan
    await channel.send(f"I have joined {guild.name} ({guild.id}) which contains {guild.member_count} members. I am now in {str(len(bot.guilds))} servers.")


# if bot leaves server, deletes server database entry
@bot.event
async def on_guild_remove(guild):
    if guild.name is not None:
        # sometimes runs even if guild is None?
        collection.delete_one({'guildid': guild.id})
        logging.info(f"Guild: {str(guild.name)} has been removed from the database.")
        await asyncio.sleep(6)
        channel = bot.get_channel(978760898594361355)  # joins chan
        await channel.send(f"I have left {guild.name} ({guild.id}) which contains {guild.member_count} members. I am now in {str(len(bot.guilds))} guilds!")
        try:
            del base[guild.id]  # delete guild from cache
        except Exception as e:
            await channel.send(f"{guild.name} prefix wasn't cached.\n{e}")


@bot.command(aliases=["changeprefix"], description="By default, the bots prefix is my mention (e.g `@RandomSongsBot#3234 randomsong`) or `?` - however you can change that with this command. A 'bot prefix' is a symbol or set of symbols used to initiate bot commands.\n\nThe only disallowed prefixes are: `/` ,`#`, and `@`\n\nImportant note: at the end of August 2022, Discord is forcing most bots to migrate to /slash commands only. 'Prefixes' will no longer work (you will still be able to use my mention (e.g `@RandomSongsBot#3234 randomsong`) as a prefix however)", usage="[prefix]", brief="Change prefix (note: this won't work at the end of August. Only slash cmds, or using my mention, going forward will work)")
@commands.cooldown(3, 6, commands.BucketType.user)  # x command use, per x seconds
@commands.has_guild_permissions(manage_guild=True)  # ensures you need the manage server perm to edit the prefix
async def changeprefix(ctx, prefix):
    if "/" in prefix:
        await ctx.send("I'm truly sorry, but in order to stop RandomSongsBot from conflicting with bots that use Discord 'slash commands' feature (including my own Slash commands!), I don't allow `/` to be used as a prefix. Discord prioritises bots with 'slash commands'. If, for example, a bot has a 'slash command' titled 'randomsong', it'll make it impossible to use RandomSongsBot's '?randomsong' feature.\nI also don't allow `@` or `#`.\n\nImportant note: at the end of August 2022, Discord is forcing most bots to migrate to /slash commands only. 'Prefixes' will no longer work (you will still be able to use my mention (e.g `@RandomSongsBot#3234 randomsong`) as a prefix however)", mention_author=False)
    elif "@" in prefix:
        await ctx.send("Sorry, but in order to not clash with discord user mentions - I don't allow `@` to be used as a prefix.\nI also don't allow `#` or `/`.\n\nImportant note: at the end of August 2022, Discord is forcing most bots to migrate to /slash commands only. 'Prefixes' will no longer work (you will still be able to use my mention (e.g `@RandomSongsBot#3234 tarot rand`) as a prefix however)", mention_author=False)
    elif "#" in prefix:
        await ctx.send("Sorry, but in order to not clash with discord channel mentions - I don't allow `#` to be used as a prefix.\nI also don't allow `/` and `@`.\n\nImportant note: at the end of August 2022, Discord is forcing most bots to migrate to /slash commands only. 'Prefixes' will no longer work (you will still be able to use my mention (e.g `@RandomSongsBot#3234 tarot rand`) as a prefix however)", mention_author=False)
    else:
        if not isinstance(ctx.channel, disnake.DMChannel):
            collection.find_one_and_update({'guildid': ctx.guild.id},
                                           {'$set': {'guildid': ctx.guild.id, 'prefix': prefix, 'name': ctx.guild.name}},
                                           upsert=True)
            # When a prefix is changed, update the cache value
            base_update = {ctx.guild.id: prefix}
            base.update(base_update)
            await ctx.send(f"Your server prefix was changed to: `{prefix}`\nUse this to activate bot commands, e.g `{prefix}help`\n\nImportant note: at the end of August 2022, Discord is forcing most bots to migrate to /slash commands only. 'Prefixes' will no longer work (you will still be able to use my mention (e.g `@RandomSongsBot#3234 tarot rand`) as a prefix however)", mention_author=False)
        else:
            await ctx.send("You can't change my prefix in DM's! In DM's, I use my mention as my prefix (@AsterieBot#7609).\n\nImportant note: at the end of August 2022, Discord is forcing most bots to migrate to /slash commands only. 'Prefixes' will no longer work (you will still be able to use my mention (e.g `@RandomSongsBot#3234 tarot rand`) as a prefix however)", mention_author=False)


# runs before command is done
@bot.before_invoke
async def bot_before_invoke(ctx):
    # try to add typing indicator
    try:
        async with ctx.typing():
            await asyncio.sleep(0.1)
    except disnake.HTTPException:
        pass


@changeprefix.error
async def changeprefix_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("This command is used to change the bot's prefix - i.e, `changeprefix .` will change the prefix to `.`. Then, people will use `.` to use bot commands.\n\nImportant note: at the end of August 2022, Discord is forcing most bots to migrate to /slash commands only. 'Prefixes' will no longer work (you will still be able to use my mention as a prefix however)", mention_author=False)
    if isinstance(error, commands.CheckFailure):
        await ctx.send("If you're trying to change the bots prefix, you need 'manage server' permissions. This only works in servers - my prefix cannot be change in DM (in DM's, my prefix is simply the default - mention me).\n\nImportant note: at the end of August 2022, Discord is forcing most bots to migrate to /slash commands only. 'Prefixes' will no longer work (you will still be able to use my mention, @RandomSongsBot#3234, as a prefix however)", mention_author=False)


@bot.command(hidden=True)
@commands.is_owner()
@commands.cooldown(1, 6, commands.BucketType.user)  # 1 command use, every 5 seconds, per user
async def basetest(ctx, guildid=None):
    if guildid is None:
        await ctx.reply(base, mention_author=False)
    else:
        await ctx.reply(f"{base[int(guildid)]}", mention_author=False)

###
# DO NOT REMOVE THESE
# TOKEN IS NECESSERY FOR IT TO WORK
# FOR LOOP LOADS IN COMMANDS FROM COGS
### 


for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        try:
            bot.load_extension(f'cogs.{filename[:-3]}')  # don't need to include .py, so we cut it off
        except Exception as e:
            channel = bot.get_channel(978761287641223168)  # exceptions channel
            print(f"Failed to load {filename}\n{e}")

bot.run(config('TOKEN'))
