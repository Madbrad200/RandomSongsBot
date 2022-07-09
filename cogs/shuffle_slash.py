import disnake
from disnake.ext import commands
import asyncio
import random
import inspect
# note: spotify client is defined in uncat_data
from .uncat_data import UncatDataCog
random_genres_list = UncatDataCog.random_genres_list
from thefuzz import fuzz  # so we can fuzzy search spotify genres and let ppl know what they might be after
from decouple import config
#buttin imports
from .buttons import ButtonsCog
DonationButton = ButtonsCog.DonationButton  # button that displays link to donate
DefaultButtons = ButtonsCog.DefaultButtons  # default buttons: donate, invite, support, etc


class RandomSongCogSlash(commands.Cog, name="Shuffle (slash)", description="*(Slash) Shuffle through streaming services for random music:*"):

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session
        self.mongo_client = bot.mongo_client
        self.dbsettings = bot.dbsettings

    # for dynamic choice creation, it generates a list of choices to pick from as the user types
    async def autocomp_genres(inter: disnake.ApplicationCommandInteraction, user_input: str):
        send_to_autocomp = []  # decks to send to autocompletion

        user_input = user_input.split()
        # replace hiphop with hip hop, so it matches with what's in the genre list
        # same with other options
        for word in range(len(user_input)):
            if user_input[word] == "hiphop":
                user_input[word] = "hip hop"
            if user_input[word] == "lofi":
                user_input[word] = "lo-fi"
        user_input = " ".join(user_input)
        # need to do this manually since there's a space
        if user_input == "lo fi":
            user_input = "lo-fi"

        # loop through all the keys in deck_aliases
        # this method will not autocomplete aliases unless the user types out the full alias name
        for genre in random_genres_list:
            if user_input.lower() in genre:
                send_to_autocomp.append(genre)
        return send_to_autocomp[:25]

    # for dynamic choice creation, it generates a list of choices to pick from as the user types
    # for the add fave genre cmd
    async def fave_autocomp_genres(inter: disnake.ApplicationCommandInteraction, user_input: str):
        send_to_autocomp = []  # decks to send to autocompletion

        user_input = user_input.split()
        # replace hiphop with hip hop, so it matches with what's in the genre list
        # same with other options
        for word in range(len(user_input)):
            if user_input[word] == "hiphop":
                user_input[word] = "hip hop"
            if user_input[word] == "lofi":
                user_input[word] = "lo-fi"
        user_input = " ".join(user_input)
        # need to do this manually since there's a space
        if user_input == "lo fi":
            user_input = "lo-fi"

        # loop through all the keys in deck_aliases
        # this method will not autocomplete aliases unless the user types out the full alias name
        for genre in random_genres_list:
            if genre == "favourites" or genre == "random genre":
                pass
            elif user_input.lower() in genre:
                send_to_autocomp.append(genre)
        return send_to_autocomp[:25]

    @commands.slash_command(name="randommusic", description="Random Music search commands!")  # invoke allows the sub command to run if it is specified, else runes will run instead.
    @commands.cooldown(3, 6, commands.BucketType.user)  # x command use, per x seconds
    async def randommusic_slash(self, inter):
        pass

    @randommusic_slash.sub_command(name="find", description="Grab a random song from Spotify!")
    @commands.cooldown(1, 6, commands.BucketType.user)  # x command use, per x seconds
    async def randommusic_find_slash(self, inter, 
                               genre: str = commands.Param(
                                    default=None, 
                                    description="Filter by Spotify music genres! Type, and options appear. Note: I show 25 options max - be specific", 
                                    autocomplete=autocomp_genres), 
                               year: str = commands.Param(
                                    default=None, 
                                    description="Enter a year to filter by (e.g 1999) or a range (e.g 1990-1999)"), 
                               album: str = commands.Param(
                                    default=None,
                                    description="Grab a random song from a specific album!"),
                               artist: str = commands.Param(
                                    default=None,
                                    description="Grab a random song from a specific artist!")
        ):

        await inter.response.defer()
        # extends timeout from 3 to 15 seconds, so the bot doesn't error if the API requesting takes too long
        # also adds a 'asteriebot is thinking... '
        # means you have to use inter.edit_original_message later

        view_def = DefaultButtons()

        # inter.channel errors in DM, so we need to grab the DM channel directly
        try:
            # isinstance(discord, DMChannel doesn't work in slash)
            reply_channel = self.bot.get_channel(inter.channel.id)  # for replying
            print(inter.guild.id)  # weird inconsistant erroring, sometimes theres an attr error, sometimes not. This print is guareenteed to cause one in a DM since ID will not exist. get_channel is not reliable in that regard
        except AttributeError as e:
            reply_channel = inter.author

        searching_msg = await reply_channel.send("*shuffling through Spotify....*")

        if genre == "random genre":
            genre = random.choice(random_genres_list)
        elif genre == "favourites":
            # test to see if a fave list already exists, and if it does, if the genres are already in it
            embed_collection = self.dbsettings["usersettings"]
            pipeline = await embed_collection.find_one({"userid": inter.author.id})
            try:
                grab_faves = pipeline["favourite_genres"]  # grab the actual list from the db
                genre = random.choice(grab_faves)
            except Exception as e:
                #  if no fave deck is found, none is chosen
                view_def.message = await reply_channel.send("It doesn't appear you've added any 'favourite genres'! I'll default to `random` instead :)\n\nThe `fave_genres` command (type `/randommusic fave_genres`) is used to add music genres to your personal favourites list! You can then optionally select to only grab a random song from one of your favourite genres, e.g `/randommusic find genre:favourites`. If, for example, you wanted to add the `pop` music genre to your faves, you'd type `/randommusic fave_genres genres:pop`\n\nYou can view your personal favourites list by typing `/randommusic favelist`", view=view_def)
                genre = random.choice(random_genres_list)

        # we need to define the random query by selecting a random letter/num/char
        random_query_options = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '!', '#', "'", '(', ')', '?', '@', '[', ']', '^', '$', '%', '&', '.', ';', '=', '_', '~', '’', '“']
        # removed ¢
        query = random.choice(random_query_options)

        if genre is not None:
            genre = genre.strip().replace(" ", "_")  # remove whitespace at the end with strip, need to add _ for it to properly find the genre in the spotify api
            # add the genre to the spotify query
            query += f" genre:{genre}"
        if year is not None:
            query += f" year:{year}"
        if artist is not None:
            query += f" artist:{artist}"
        if album is not None:
            query += f" album:{album}"

        # this returns a dict of various values, such as:
        #{'album': {'album_type': 'album', 'artists': [{'external_urls': {'spotify': 'https://open.spotify.com/artist/49VtaZvoqBgZHQxSqlCUyp'}, 'name': 'SMTOWN', 'type': 'artist', 'uri': 'spotify:artist:49VtaZvoqBgZHQxSqlCUyp'}], 'external_urls': {'spotify': 'https://open.spotify.com/album/3dn2in6doTc6zfA0G2UFDZ'}, 'images': [{'url': 'https://i.scdn.co/image/ab67616d0000b27326b7dce0a74da7f7f6c7f193'}, {url': 'https://i.scdn.co/image/ab67616d00001e0226b7dce0a74da7f7f6c7f193'}, {'url': 'https://i.scdn.co/image/ab67616d0000485126b7dce0a74da7f7f6c7f193'}], 'name': '2021 Winter SMTOWN : SMCU EXPRESS', 'release_date': '2021-12-27', 'release_date_precision': 'day', 'total_tracks': 10, 'type': 'album', 'uri': 'spotify:album:3dn2in6doTc6zfA0G2UFDZ'}, 'duration_ms': 177413, 'explicit': False, 'popularity': 82, 'preview_url': 'https://p.scdn.co/mp3-preview/4b913662bc7fb486752b2e4bbead6b8513b2c09d?cid=581f1e9c782c4b37b89d3f09e105022d', 'track_number': 2, 'type': 'track', 'uri': 'spotify:track:7eVu7FI02cTicLEgVtUvwF'}

        # docs: https://github.com/michimalek/spotipy-random/blob/master/src/spotipy_random/spotipy_random.py
        # https://developer.spotify.com/documentation/web-api/reference/#/operations/search
        # possible kwargs below:
        # (spotify: Spotify, limit: int = 10, offset_min: int = 0, offset_max: int = 20, type: str = "track", market: Any = None, album: str = None, artist: str = None, track: str = None, year: str = None, upc: str = None, tag_hipster: bool = None, tag_new: bool = None, isrc: str = None, genre: str = None, ) -> dict:
        # limit=num of songs it searches through (max 50), type=type of object it's returns, limit=the amount of objects it returns
        #try:
            #grab_data = get_random(spotify_client, limit=50, type="track", year=year, genre=genre, offset_min=0, offset_max=1000)

        # .start(self, query, query_type, auth_token=None, **kwargs)
        # https://developer.spotify.com/documentation/web-api/reference/#/operations/search
        # first param is the q field, filters also go in there, e.g "boy in da corner genre:grime"
        offset = random.randint(0, 1000)  # grab a random offset from 0 to 1000, the offset is where we start counting from the results (e.g start from the 50th result if the offset = 50)
        note = None

        # grab spotify client
        spotify_client = UncatDataCog.spotify_client
        # start search
        search_result = await spotify_client.search.start(query, "track", limit=1, offset=offset)
        try:
            grab_data = search_result["tracks"]["items"][0]  # grabs the first result.
        except IndexError as e:
            # indexerror is caused when the offset is higher than the total amount of songs returned
            # so first we check if the offset was simply too high, yet results were still returned
            total_tracks_returned = search_result["tracks"]["total"] 
            if total_tracks_returned < offset and total_tracks_returned != 0:
                # if the offset was simply too high, set it the same as the amount of tracks returned and re-run with the same query
                offset = random.randint(0, total_tracks_returned-1)
                search_result = await spotify_client.search.start(query, "track", limit=1, offset=offset)
                grab_data = search_result["tracks"]["items"][0]  # grabs the first result.
            elif total_tracks_returned == 0:
                # if no tracks were returned at all, replace the query
                # in this case, the offset isn't the problem, the query was (e.g the character returned nothing)
                # we're going to loop through every character in random_query_options
                random.shuffle(random_query_options)  # shuffle it around so it's not the same result every time
                for character in random_query_options:
                    query = list(query)  # turn the original query into a list
                    query[0] = character  # replace the first character in query with a character from random_query_options
                    query = "".join(query)  # turn it back into a string
                    search_result = await spotify_client.search.start(query, "track", limit=1, offset=offset)
                    try:
                        grab_data = search_result["tracks"]["items"][0]  # grabs the first result.
                        break  # if we successfully grabbed an item, break out of the loop
                    except IndexError as e:
                        # once again, we check if the offset was the cause of the problem. If it was, we can simple fix the offset
                        # if not, we will loop back with another character from random_query_options
                        total_tracks_returned = search_result["tracks"]["total"] 
                        if total_tracks_returned < offset and total_tracks_returned != 0:
                            # if the offset was simply too high, set it the same as the amount of tracks returned and re-run with the same query
                            offset = random.randint(0, total_tracks_returned-1)
                            search_result = await spotify_client.search.start(query, "track", limit=1, offset=offset)
                            try:
                                grab_data = search_result["tracks"]["items"][0]  # grabs the first result.
                                break  # if we find something, break out of the loop -we're done!
                            except IndexError as e:
                                pass  # if it errors here, go back to the start of the loop
                else:
                    # if the loop was unable to find any results, it indicates the inputted filters don't match/return nothing
                    # eg., mismatching artist and year filters
                    # so just go for a default query with a single character
                    note = "\n\nnote: I did not find a result from your inputted request! Instead, I went back to default settings (all of Spotify). A list of Spotify genres can be found here: https://everynoise.com/everynoise1d.cgi?scope=all (note: it's easier to find genres if you use the slash command `/randommusic`)\n\n"
                    if genre is not None and genre not in random_genres_list:
                        did_you_mean_this = []
                        # check if we can find what genre the user might've been looking for, and suggest it
                        for genre_in_list in random_genres_list:
                            # directly compare the genres in the list and see how similar they are
                            # this returns a num between 0-100, higher=closer comparable
                            fuzz_ratio = fuzz.ratio(genre, genre_in_list)
                            # note: lower than 50 can result in too long messages
                            if fuzz_ratio >= 70:
                                did_you_mean_this.append(f"`{genre_in_list}`")
                        if len(did_you_mean_this) > 0:
                            note += "I've found some genres that're named similarly to what you entered, perhaps you meant one of these?\n"+", ".join(did_you_mean_this)

                    query = random.choice(random_query_options)
                    offset = random.randint(0, 1000)
                    search_result = await spotify_client.search.start(query, "track", limit=1, offset=offset)
                    genre = None   # reset this back to none so it isn't printed onto the text_content
                    try:
                        grab_data = search_result["tracks"]["items"][0]  # grabs the first result.
                    except IndexError as e:
                        # indexerror is caused when the offset is higher than the total amount of songs returned
                        # so first we check if the offset was simply too high, yet results were still returned
                        total_tracks_returned = search_result["tracks"]["total"] 
                        if total_tracks_returned < offset and total_tracks_returned != 0:
                            # if the offset was simply too high, set it the same as the amount of tracks returned and re-run with the same query
                            offset = random.randint(0, total_tracks_returned-1)
                            search_result = await spotify_client.search.start(query, "track", limit=1, offset=offset)
                            grab_data = search_result["tracks"]["items"][0]  # grabs the first result.
                        elif total_tracks_returned == 0:
                            # if no tracks were returned at all, replace the query
                            # in this case, the offset isn't the problem, the query was (e.g the character returned nothing)
                            # this shouldn't be happening in this case, since the query is just a single character, so send a warning to the exceptions channel to look into it
                            channel = self.bot.get_channel(846716807326990366)  # exceptions channel
                            await channel.send(f"`{query}` has failed to return anything\nOffset: {offset}\nConsider removing it from the query list?")
        except Exception as y:
            channel = self.bot.get_channel(846716807326990366)  # exceptions channel
            await channel.send(f"Error: {y}\nOffset: {offset}\nQuery: {query}")

        try:
            await searching_msg.delete()
        except disnake.errors.NotFound as e:
            pass

        # grab song, then convert from spotify url spotify:track: to clickable link
        try:
            grab_song_link = grab_data["uri"]
        except UnboundLocalError as e:
            channel = self.bot.get_channel(846716807326990366)  # exceptions channel
            await channel.send(f"UnBoundLocalError randommusic cmd: {e}\nOffset: {offset}\nQuery: {query}")
            
        song_link = f"http://open.spotify.com/track/{grab_song_link[14:]}"
        song_name = grab_data["name"]
        song_artist = grab_data["artists"][0]["name"]

        # add the genre name if it has been chosen
        if genre is not None:
            genre = genre.replace("_", " ")
        else:
            genre = "not specified"

        text_content = inspect.cleandoc(
            f"""
            I randomly grabbed: "{song_name}" by {song_artist} (genre: {genre})
            {song_link}
            (Sources used: Spotify)""")

        if note is not None:
            text_content = text_content+note

        class PageButtons(disnake.ui.View):
            message: disnake.Message

            def __init__(self, author, page_sesh):
                super().__init__(timeout=120)
                self.author = author
                self.page_sesh = page_sesh
                self.value = None  # so we can make button clickable only once

            # clears buttons on timeout
            async def on_timeout(self) -> None:
                try:
                    self.stop()
                    await self.message.edit(view=None)
                except Exception as e:
                    pass

            # checks if the user clicking the button is the same one who used the command
            # if not, it'll return a hidden message and ignore their button click
            async def interaction_check(self, response) -> bool:
                if response.author != self.author:
                    await response.send(f'{response.author.mention}, sorry, only the user who drew these cards can click this :(', ephemeral=True)
                    return False
                return True

            @disnake.ui.button(label="Deezer Link", style=disnake.ButtonStyle.grey)
            async def page_1(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):

                async with self.page_sesh.get(f"https://api.deezer.com/search?q={song_artist} - {song_name}") as r:
                    if r.status == 200:
                        json_data = await r.json()  # grabs the joke json data
                        try:
                            grab_deezer_link = json_data["data"][0]["link"]

                            await inter.response.send_message(content=grab_deezer_link, ephemeral=True)
                        except IndexError as e:
                            await inter.response.send_message(content="I can't find this song on Deezer :(", ephemeral=True) 
                    else:
                        await inter.response.send_message(content="Deezer API appears to be down :(", ephemeral=True)
                # clears page_1 if pressed once
                # this loops through the list of objects, checks if the object label matches, then removes it from the list.
                for i, o in enumerate(self.children):
                    if o.label == "Deezer Link":
                        del self.children[i]
                        break
                await self.message.edit(view=self)

            @disnake.ui.button(label="YouTube Link", style=disnake.ButtonStyle.red)
            async def page_2(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
                # remove api key on next restart and use env
                async with self.page_sesh.get(f"https://youtube.googleapis.com/youtube/v3/search?part=snippet&order=relevance&q={song_artist} - {song_name}&safeSearch=moderate&type=video&videoDefinition=any&key={config(youtube_token)}") as r:
                    if r.status == 200:
                        json_data = await r.json()  # grabs the joke json data
                        try:
                            grab_youtube_link = json_data["items"][0]["id"]["videoId"]  # gets the video id

                            await inter.response.send_message(content=f"https://www.youtube.com/watch?v={grab_youtube_link}", ephemeral=True)
                        except IndexError as e:
                            await inter.response.send_message(content="I can't find this song on YouTube :(", ephemeral=True) 
                    else:
                        await inter.response.send_message(content="YouTube's API appears to be down :(", ephemeral=True)
                # clears page_2 if pressed once
                for i, o in enumerate(self.children):
                    if o.label == "YouTube Link":
                        del self.children[i]
                        break
                await self.message.edit(view=self)

            @disnake.ui.button(label="Napster Link", style=disnake.ButtonStyle.green)
            async def page_3(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
                # remove api key on next restart and use env
                async with self.page_sesh.get(f"https://api.napster.com/v2.2/search/verbose?apikey={config('napster_token')}&query={song_artist}+-+{song_name}&per_type_limit=1") as r:
                    if r.status == 200:
                        json_data = await r.json()  # grabs the joke json data
                        try:
                            grab_napster_link = json_data["search"]["data"]["tracks"][0]["shortcut"]  # gets the video id

                            await inter.response.send_message(content=f"https://us.napster.com/{grab_napster_link}", ephemeral=True)
                        except IndexError as e:
                            await inter.response.send_message(content="I can't find this song on Napster :(", ephemeral=True) 
                    else:
                        await inter.response.send_message(content="Napster's API appears to be down :(", ephemeral=True)
                # clears page_3 if pressed once
                for i, o in enumerate(self.children):
                    if o.label == "Napster Link":
                        del self.children[i]
                        break
                await self.message.edit(view=self)

        # pass session since we can't access it directly from within pagebuttons class
        view = PageButtons(inter.author, self.session)

        view.message = await inter.edit_original_message(content=text_content, view=view)

    @randommusic_slash.sub_command(name="fave_genres", description="Curate a list of 'favourite' genres!")
    @commands.cooldown(3, 6, commands.BucketType.user)  # x command use, per x seconds
    async def faves_slash(self, inter, 
                          genres: str = commands.Param(
                            description="Enter a genre to add to your fave list (if they're already in your faves, they're removed instead).", 
                            autocomplete=fave_autocomp_genres)):

        # we can only reply once to an interaction, so let's grab the chan ID/user ID and send there instead
        # inter.channel errors in DM, so we need to grab the DM channel directly
        try:
            # isinstance(discord, DMChannel doesn't work in slash)
            reply_channel = self.bot.get_channel(inter.channel.id)  # for replying
        except AttributeError as e:
            reply_channel = inter.author

        list_of_genres = []
        not_valid_genres = []

        args = tuple(genres.split("|"))

        fave_random_genres_list = random_genres_list.copy()
        fave_random_genres_list.remove("favourites")
        fave_random_genres_list.remove("random genre")

        for x in args:  # loop through args, if one of the args is false then it'll error
            if x.lower() in fave_random_genres_list:
                list_of_genres.append(x.lower())
                # if deck exists, add to list
            else:
                # if deck isn't valid
                not_valid_genres.append(x.lower())   

        # if a valid deck has been chosen
        if len(list_of_genres) > 0:

            # check if any incorrect decks were chosen as well as correct ones
            if len(not_valid_genres) > 0:
                await asyncio.sleep(1)
                text_content = f"The following genres are invalid and therefore cannot be added to your favourite's list: {', '.join(not_valid_genres)}\n\nCheck https://everynoise.com/everynoise1d.cgi?scope=all for a list of valid genre names.\n\nIf you wish to add multiple genre sat the same time, make sure to seperate them with a comma (`,`)!"

                did_you_mean_this = []
                # check if we can find what genre the user might've been looking for, and suggest it
                for genre_in_list in random_genres_list:
                    for invalid_genre in not_valid_genres:
                        # directly compare the genres in the list and see how similar they are
                        # this returns a num between 0-100, higher=closer comparable
                        fuzz_ratio = fuzz.ratio(invalid_genre.replace("`", ""), genre_in_list)
                        # note: lower than 50 can result in too long messages
                        if fuzz_ratio >= 70:
                            # if statement to ensure no duplicates are added in the loop
                            if genre_in_list not in did_you_mean_this:
                                did_you_mean_this.append(f"`{genre_in_list}`")
                if len(did_you_mean_this) > 0:
                    text_content += "\nI've found some genres that're named similarly to what you entered, perhaps you meant one of these?\n"+", ".join(did_you_mean_this)

                await reply_channel.send(text_content, mention_author=False, view=DefaultButtons())

            collection = self.dbsettings["usersettings"]

            # test to see if fave list already exists and if it does, if the decks are already in it
            try:
                get_data = await collection.find_one({"userid": inter.author.id})  # grab the users data

                grab_faves = get_data["favourite_genres"]  # grab the list

                already_sent = []  # so we can let the user know they're favourting a genre already favourited

                # if genre in db, we don't need to refave it

                for genre_name in list_of_genres:
                    if genre_name in grab_faves:
                        already_sent.append(genre_name)
                list_of_genres = [x for x in list_of_genres if x not in already_sent]
                # create a new list with the already-favourited genres redacted
                list_of_genres = list(dict.fromkeys(list_of_genres))
                # remove any duplicates by creating a dictionary, then reconvert to list

                # if user is trying to fave a genre already favourited, remove instead
                if len(already_sent) > 0:
                    collection.find_one_and_update({"userid": inter.author.id}, {"$pull": {"favourite_genres": {"$in": [x for x in already_sent]}}}, upsert=True)
                    await asyncio.sleep(1)

                    text_content = f"You had previously favorited the following genres: {', '.join(already_sent)}\n\nI have now removed these from your favourites."
                    await reply_channel.send(text_content, view=DefaultButtons())
            except Exception as e:
                pass

            if len(list_of_genres) > 0:
                # if we're favorting a new genre
                # receck the data (this may be diff if an item was removed)
                get_data = await collection.find_one({"userid": inter.author.id})

                # check if a fave list exists
                try:
                    if "favourite_genres" in get_data.keys():
                        get_faves = get_data["favourite_genres"]
                    else:
                        get_faves = []
                        # if not it's an empty list
                    # query if the author is a donator or not (max 15 faves)
                    if "donator" in get_data.keys():
                        is_donator = get_data["donator"]
                    else:
                        is_donator = False
                except AttributeError as e:
                    get_faves = []

                # create array if it doesn't exist or append to it with push
                # $each adds each element to the array (e.g list of [1, 2, 3] - each item is added to array)
                collection.find_one_and_update({"userid": inter.author.id}, {'$push': {'favourite_genres': {"$each": [x for x in list_of_genres]}}}, upsert=True)

                await asyncio.sleep(1)
                text_content = f"The following music genres have been successfully added to your favourite genres list: {', '.join(list_of_genres)}\n\nYou can now grab a random song from one of your favourite genres by using the `genre:favourites` tag, e.g `/randommusic find genre:favourites`.\nTo see your current favourites list, type `/randommusic favelist`"
                await inter.send(text_content, view=DefaultButtons(), ephemeral=True)
        else:
            # if no valid genres were found
            text_content = f"The following genres are invalid and therefore cannot be added to your favourite's list: {', '.join(not_valid_genres)}\n\nCheck https://everynoise.com/everynoise1d.cgi?scope=all for a list of valid genre names. If you wish to add multiple genre sat the same time, make sure to seperate them with a comma (`,`)!"

            did_you_mean_this = []
            # check if we can find what genre the user might've been looking for, and suggest it
            for genre_in_list in random_genres_list:
                for invalid_genre in not_valid_genres:
                    # directly compare the genres in the list and see how similar they are
                    # this returns a num between 0-100, higher=closer comparable
                    fuzz_ratio = fuzz.ratio(invalid_genre.replace("`", ""), genre_in_list)
                    # note: lower than 50 can result in too long messages
                    if fuzz_ratio >= 70:
                        # if statement to ensure no duplicates are added in the loop
                        if genre_in_list not in did_you_mean_this:
                            did_you_mean_this.append(f"`{genre_in_list}`")
            if len(did_you_mean_this) > 0:
                text_content += "\nI've found some genres that're named similarly to what you entered, perhaps you meant one of these?\n"+", ".join(did_you_mean_this)
            await inter.send(text_content, view=DefaultButtons(), ephemeral=True)

    @randommusic_slash.sub_command(name="favelist", description="See your list of favourite genres")
    @commands.cooldown(3, 6, commands.BucketType.user)  # x command use, per x seconds
    async def favelist_slash(self, inter):

        await inter.response.defer()
        # extends timeout from 3 to 15 seconds, so the bot doesn't error if the API requesting takes too long
        # also adds a 'asteriebot is thinking... '
        # means you have to use inter.edit_original_message later

        collection = self.dbsettings["usersettings"]  # db open user settings
        # test to see if a fave list already exists, and if it does, if the decks are already in it
        view = DefaultButtons()
        try:
            grab_faves = await collection.find_one({"userid": inter.author.id})  # grab the entry associated with the users's id
            grab_faves = grab_faves["favourite_genres"]  # grab the actual list from the db
            grab_faves.sort()
            await asyncio.sleep(1)
            if len(grab_faves) > 0:
                view.message = await inter.edit_original_message(f"The following genres are in your personal favourites list ({len(grab_faves)} genres total):\n`{', '.join(grab_faves)}`\n\nIf you wish to remove a genre from your favourites list - it's the same way as how you added it, `/randommusic fave_genres genres:pop` will remove the in-putted genre from your faves list if the genre is already in your faves list.", view=view)
            else:
                # if list exists but it's empty
                view.message = await inter.edit_original_message("`/randomusic fave_genres genres:[genre_name]` is used to add genres to your personal favourites list. You can now grab a random song from one of your favourite genres by using the `genre:favourites` tag, e.g `/randommusic find genre:favourites`. It appears you haven't yet added any favourite genres to your list - if you had in the past, you've since removed them!\nYou can view your personal favourites list via `/randommusic favelist`", view=view)
        except Exception as e:
            # if list doesn't exist
            view.message = await inter.edit_original_message("`/randommusic fave_genres genres:pop` is used to add genres to your personal favourites list. You can then grab a random song from one of your favourite genres by using the `genre:favourites` tag, e.g `/randommusic find genre:favourites`. It appears you haven't yet added any favourite decks to your list!\nYou can view your personal favourites list via `/randommusic favelist`", view=view)


def setup(bot):
    bot.add_cog(RandomSongCogSlash(bot))
