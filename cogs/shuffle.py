import disnake
from disnake.ext import commands
import asyncio
import random
import inspect
# note: spotify client is defined in uncat_data
from thefuzz import fuzz  # so we can fuzzy search spotify genres and let ppl know what they might be after
from decouple import config
# buttons
from .buttons import ButtonsCog
from .uncat_data import UncatDataCog
random_genres_list = UncatDataCog.random_genres_list
DonationButton = ButtonsCog.DonationButton  # button that displays link to donate
DefaultButtons = ButtonsCog.DefaultButtons  # default buttons: donate, invite, support, etc


class RandomSongCog(commands.Cog, name="Shuffle", description="*Shuffle through streaming services for random music:*"):

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session
        self.mongo_client = bot.mongo_client
        self.dbsettings = bot.dbsettings

    @commands.group(aliases=["shuffle", "randomsong", "randomsongs", "randmusic", "randsong", "randsongs"], brief="Shuffle through Spotify's library to find some music!", usage="<-year [enter year or year-range]> <-genre [enter genre]> <-album [enter album name] <-artist [enter artist name]>", invoke_without_command=True)
    @commands.cooldown(1, 6, commands.BucketType.user)  # x command use, per x seconds
    @commands.max_concurrency(1, commands.BucketType.user, wait=True)  # int=amount of active commands, wait=queue commands.
    async def randommusic(self, ctx, *, args: str = None):

        # command description
        """
        This command allows you to shuffle through Spotify's diverse library to find random music! A great way to explore and find new sounds :)

        __COMMAND FILTERS__
        You may optionally filter by year, artist, album, or genre. For example:

        `@RandomSongsBot#3234 randommusic -genre grime -year 2015` (will grab a random song from the 'grime' genre, released in 2015)
        `@RandomSongsBot#3234 randommusic -year 1980-1982` (will grab a random song from between 1980-1982)

        Use the `-artist` and `-album` tags to filter by those respectively. Only want to see Spotify links & none of the supplementary text about Shufflemancy? Add the `-s` tag!

        Note: This data relies on Spotify, which can be faulty. Not all genres are well categorised, or well named. A list can be found [here](https://everynoise.com/everynoise1d.cgi?scope=all). Currently, 5911 Spotify genres are supported.

        """

        # endpoints: 
        # format: spotify_client.ENDPOINT_NAME.METHOD_NAME
        # e.g, spotify_client.albums.get_multiple()

        view_def = DefaultButtons()

        searching_msg = await ctx.send("*shuffling through Spotify....*")

        # this returns a dict of various values, such as:
        #{'album': {'album_type': 'album', 'artists': [{'external_urls': {'spotify': 'https://open.spotify.com/artist/49VtaZvoqBgZHQxSqlCUyp'}, 'name': 'SMTOWN', 'type': 'artist', 'uri': 'spotify:artist:49VtaZvoqBgZHQxSqlCUyp'}], 'external_urls': {'spotify': 'https://open.spotify.com/album/3dn2in6doTc6zfA0G2UFDZ'}, 'images': [{'url': 'https://i.scdn.co/image/ab67616d0000b27326b7dce0a74da7f7f6c7f193'}, {url': 'https://i.scdn.co/image/ab67616d00001e0226b7dce0a74da7f7f6c7f193'}, {'url': 'https://i.scdn.co/image/ab67616d0000485126b7dce0a74da7f7f6c7f193'}], 'name': '2021 Winter SMTOWN : SMCU EXPRESS', 'release_date': '2021-12-27', 'release_date_precision': 'day', 'total_tracks': 10, 'type': 'album', 'uri': 'spotify:album:3dn2in6doTc6zfA0G2UFDZ'}, 'duration_ms': 177413, 'explicit': False, 'popularity': 82, 'preview_url': 'https://p.scdn.co/mp3-preview/4b913662bc7fb486752b2e4bbead6b8513b2c09d?cid=581f1e9c782c4b37b89d3f09e105022d', 'track_number': 2, 'type': 'track', 'uri': 'spotify:track:7eVu7FI02cTicLEgVtUvwF'}

        album = None
        artist = None
        year = None
        genre = None

        # we need to define the random query by selecting a random letter/num/char
        random_query_options = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0', '!', '#', "'", '(', ')', '?', '@', '[', ']', '^', '$', '%', '&', '.', ';', '=', '_', '~', '’', '“']
        # removed ¢
        query = random.choice(random_query_options)

        if args is not None:
            # to try to avoid false positives (with dashes in artist/genre names) by using 'asteriebot' has the part to split
            # if "-artist" in args:
            #     args = args.replace("-artist", "asterirandomsongsbotebot-artist")
            if "-year" in args:
                args = args.replace("-year", "randomsongsbot-year")
            if "-genre" in args:
                args = args.replace("-genre", "randomsongsbot-genre")
            if "-artist" in args:
                args = args.replace("-artist", "randomsongsbot-artist")
            if "-album" in args:
                args = args.replace("-album", "randomsongsbot-album")
            args = args.split("randomsongsbot")  # create a list, splitting by the dash, e.g ["", "genre grime", "artist ariana grande"]
            # album not working atm
            # if "-album" in args:
            #     album = args.replace("-album ", "")
            for item in args:
                if "-genre" in item:
                    genre = item.replace("-genre ", "").strip().replace(" ", "_")  # remove whitespace at the end with strip, need to add _ for it to properly find the genre in the spotify api

                    # check if the user wants a random genre
                    if genre.lower() in ("random_genre", "rand", "random"):
                        # grab a random genre if user requests one
                        # replace white space in genre name with _
                        genre = random.choice(random_genres_list).replace(" ", "_")
                    elif genre.lower() in ("fav", "fave", "favs", "faves", "favourite", "favourites", "favorite", "favorites"):
                        # test to see if a fave list already exists, and if it does, if the genres are already in it
                        embed_collection = self.dbsettings["usersettings"]
                        pipeline = await embed_collection.find_one({"userid": ctx.author.id})
                        try:
                            grab_faves = pipeline["favourite_genres"]  # grab the actual list from the db
                            genre = random.choice(grab_faves)
                        except Exception as e:
                            #  if no fave deck is found, none is chosen
                            text_content = "The `addfave` command (type `@RandomSongsBot#3234 randommusic addfave [genre_name]`) is used to add music genres to your personal `randommusic` favourites list, which can then be used in your shufflemancy! They'll be randomly selected if you type `@RandomSongsBot#3234 randommusic -genre fave`. E.g, to add the `pop` music genre to your faves, you'd type `@RandomSongsBot#3234 randommusic addfave pop`\n\nYou can view your personal favourites list by typing `@RandomSongsBot#3234 randommusic favelist`"


                            try:
                                view_def.message = await ctx.reply(f"{text_content}\n{e}", mention_author=False, view=view_def)
                            except disnake.HTTPException as y:
                                # if original message is deleted before bot has sent msg, this prevents error
                                view_def.message = await ctx.send(text_content, view=view_def)
                    elif genre.lower() == "hiphop":
                        genre = "hip hop"
                    elif genre.lower() == "lofi":
                        genre = "lo-fi"
                    elif genre.lower() == "uk hiphop":
                        genre = "uk hip hop"

                    # add the genre to the spotify query
                    query += f" genre:{genre}"
                if "-year" in item:
                    year = item.replace("-year ", "").strip()
                    query += f" year:{year}"
                if "-artist" in item:
                    artist = item.replace("-artist ", "").strip()
                    query += f" artist:{artist}"
                if "-album" in item:
                    album = item.replace("-album ", "").strip()
                    query += f" album:{album}"

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
            print(e)
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
                        print(e)
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
                                print(e)
                                pass  # if it errors here, go back to the start of the loop
                else:
                    # if the loop was unable to find any results, it indicates the inputted filters don't match/return nothing
                    # eg., mismatching artist and year filters
                    # so just go for a default query with a single character
                    note = "\n\nnote: I did not find a result from your inputted request! Instead, I went back to default settings (all of Spotify). A list of Spotify genres can be found here: https://everynoise.com/everynoise1d.cgi?scope=all (note: it's easier to find genres if you use the slash command `/shufflemancy`)\n\n"
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
                        print(e)
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
            await channel.send(f"UnBoundLocalError Shuffle cmd: {e}\nOffset: {offset}\nQuery: {query}")
        song_link = f"http://open.spotify.com/track/{grab_song_link[14:]}"
        song_name = grab_data["name"]
        song_artist = grab_data["artists"][0]["name"]

        # add the genre name if it has been chosen so we can add it to the string that gets posted
        # remove the _ since it's not needed in this
        if genre is not None:
            genre = genre.replace("_", " ")
        else:
            genre = "not specified"

        text_content = inspect.cleandoc(
            f"""
            I randomly grabbed: "{song_name}" by {song_artist} (genre: {genre})
            {song_link}

            (Sources used: Spotify | Did you know you can filter by artist, genre, album, and years? Check `@RandomSongsBot#3234 help shuffle` for examples.)""")
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
                async with self.page_sesh.get(f"https://youtube.googleapis.com/youtube/v3/search?part=snippet&order=relevance&q={song_artist} - {song_name}&safeSearch=moderate&type=video&videoDefinition=any&key={config('youtube_token')}") as r:
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

            @disnake.ui.button(label="Bot Support Server", style=disnake.ButtonStyle.green)
            async def page_4(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
                await inter.response.send_message(content="Join my support server if you need help or have any ideas!\nhttps://discord.gg/WchY5gSGyh", ephemeral=True)

        # pass session since we can't access it directly from within pagebuttons class
        view = PageButtons(ctx.author, self.session)

        try:
            view.message = await ctx.reply(text_content, mention_author=False, view=view)
        except disnake.HTTPException as y:
            # if original message is deleted before bot has sent msg, this prevents error
            view.message = await ctx.send(text_content, view=view)

    @randommusic.command(aliases=["addfav", "addfavourite", "addfavorite", "addfavorites", "addfavourites", "addfavs", "addfaves", "faveadd", "favesadd", "favadd", "favsadd", "favegenres", "fave_genres"], usage="[genre_name]")
    @commands.cooldown(3, 6, commands.BucketType.user)  # x command use, per x seconds
    @commands.max_concurrency(1, commands.BucketType.user, wait=True)
    async def addfave(self, ctx, *, list_of_genres):

        # command description
        """
        Add a selection of music genres to your favourites list! You can then use these genres for the 'randommusic' command. Note: genres should be seperated by commas (`,`) if you're entering more than one.

        For example, typing `@RandomSongsBot#3234 randommusic addfav pop, hip hop` would add both the `pop` and `hip hop` genres to my favourites list. Then I can do `@RandomSongsBot#3234 randommusic -genre fave`, and I'll search Spotify for a song matching one of your favourite genres!
        
        """

        view = DefaultButtons()

        # turn args into a list and split by commas
        # this will allow users to add multiple genres to their fave list
        list_of_genres = list_of_genres.split(",")
        #remove any white-space and lower
        list_of_genres = [f"{s.strip().lower()}" for s in list_of_genres]
        not_valid_genres = []

        # check if the genres are valid
        for genre in list_of_genres:
            if genre not in random_genres_list:
                not_valid_genres.append(genre)
                list_of_genres.remove(genre)

        # if any valid genres have been chosen
        if len(list_of_genres) > 0:

            # check if any incorrect decks were chosen as well
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

                try:
                    view.message = await ctx.reply(text_content, mention_author=False, view=view)
                except disnake.HTTPException as y:
                    # if original message is deleted before bot has sent msg, this prevents error
                    view.message = await ctx.send(text_content, view=view)

            collection = self.dbsettings["usersettings"]

            # test to see if fave list already exists and if it does, if the decks are already in it
            try:
                get_data = await collection.find_one({"userid": ctx.author.id})  # grab the users data

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
                    collection.find_one_and_update({"userid": ctx.author.id}, {"$pull": {"favourite_genres": {"$in": [x for x in already_sent]}}}, upsert=True)
                    await asyncio.sleep(1)

                    text_content = f"You had previously favorited the following genres: {', '.join(already_sent)}\n\nI have now removed these from your favourites."
                    try:
                        view.message = await ctx.reply(text_content, mention_author=False, view=view)
                    except disnake.HTTPException as y:
                        # if original message is deleted before bot has sent msg, this prevents error
                        view.message = await ctx.send(text_content, view=view)
            except Exception as e:
                pass

            if len(list_of_genres) > 0:
                # if we're favorting a new genre
                # receck the data (this may be diff if an item was removed)
                get_data = await collection.find_one({"userid": ctx.author.id})

                # check if a fave list exists
                try:
                    if "favourite_genres" in get_data.keys():
                        get_faves = get_data["favourite_genres"]
                    else:
                        get_faves = []
                        # if not it's an empty list
                except AttributeError as e:
                    get_faves = []

                # create array if it doesn't exist or append to it with push
                # $each adds each element to the array (e.g list of [1, 2, 3] - each item is added to array)
                collection.find_one_and_update({"userid": ctx.author.id}, {'$push': {'favourite_genres': {"$each": [x for x in list_of_genres]}}}, upsert=True)

                await asyncio.sleep(1)
                text_content = f"The following music genres have been successfully added to your `randomusic` favourite genres list: {', '.join(list_of_genres)}\n\nIn the `randommusic` command, you can add the `-genre fave` tag and I'll grab a random song from one of your favourite genres, like so: `@RandomSongsBot#3234 randommusic -genre fave`\nTo see your current favourites list, type `@RandomSongsBot#3234 randommusic favelist`"
                try:
                    view.message = await ctx.reply(text_content, mention_author=False, view=view)
                except disnake.HTTPException as y:
                    # if original message is deleted before bot has sent msg, this prevents error
                    view.message = await ctx.send(text_content, view=view)
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
            try:
                await ctx.reply(text_content, mention_author=False, view=view)
            except disnake.HTTPException as y:
                # if original message is deleted before bot has sent msg, this prevents error
                await ctx.send(text_content, view=view)

    @addfave.error
    async def addfave_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            view = DefaultButtons()
            await asyncio.sleep(2)  # used to limit the potential spam
            text_content = "The `addfave` command, used by typing `@RandomSongsBot#3234 randommusic addfave [genre_name]`, is used to add music genres to your personal favourites list. In the `randommusic` command, you can add the `-genre fave` tag and I'll grab a random song from one of your favourite genres, like so: `@RandomSongsBot#3234 randommusic -genre fave`. It appears you haven't yet added any favourite music genres to your list!\n\nYou can view your personal favourites list by typing `@RandomSongsBot#3234 randommusic favelist`"
            try:
                view.message = await ctx.reply(text_content, mention_author=False, view=view)
            except disnake.HTTPException as y:
                # if original message is deleted before bot has sent msg, this prevents error
                view.message = await ctx.send(text_content, view=view)

    @randommusic.command(aliases=["favlist", "favouritelist", "favoritelist", "favouriteslist", "favoriteslist"], brief="Your list of favourite shufflemancy genres.")
    @commands.cooldown(3, 6, commands.BucketType.user)  # x command use, per x seconds
    @commands.max_concurrency(1, commands.BucketType.user, wait=True)
    async def favelist(self, ctx):

        # command description
        """
        See your list of favourite music genres, as added by typing `@RandomSongsBot#3234 randommusic addfave`. In the `randommusic` command, you can add the `-genre fave` tag and I'll grab a random song from one of your favourite genres, like so: `@RandomSongsBot#3234 randommusic -genre fave`.
        """

        collection = self.dbsettings["usersettings"]
        view = DefaultButtons()
        # test to see if a fave list already exists, and if it does, if the music genres are already in it
        try:
            grab_faves = await collection.find_one({"userid": ctx.author.id})  # grab the entry associated with the users's id
            grab_faves = grab_faves["favourite_genres"]  # grab the actual list from the db
            grab_faves.sort()
            await asyncio.sleep(1)
            if len(grab_faves) > 0:
                text_content = f"The following music genres are in your personal favourites list ({len(grab_faves)} music genres total):\n`{', '.join(grab_faves)}`\n\nIn the `randommusic` command, you can add the `-genre fave` tag and I'll grab a random song from one of your favourite genres, like so: `@RandomSongsBot#3234 randommusic -genre fave`. If you wish to remove a genre from your favourites list - it's the same way as how you added it, typing `@RandomSongsBot#3234 randommusic addfave [genre_name]` will remove the in-putted music genre from your faves list if the music genre is already in your faves list."
                try:
                    view.message = await ctx.reply(text_content, mention_author=False, view=view)
                except disnake.HTTPException as y:
                    # if original message is deleted before bot has sent msg, this prevents error
                    view.message = await ctx.send(text_content, view=view)
            else:
                # if list exists but it's empty
                text_content = "The `addfave` command, used by typing `@RandomSongsBot#3234 randommusic addfave [genre_name]`, is used to add music genres to your personal favourites list. In the `randommusic` command, you can add the `-genre fave` tag and I'll grab a random song from one of your favourite genres, like so: `@RandomSongsBot#3234 randommusic -genre fave`. It appears you haven't yet added any favourite music genres to your list - if you had in the past, you've since removed them!\n\nYou can view your personal favourites list by typing `@RandomSongsBot#3234 randommusic favelist`"
                try:
                    view.message = await ctx.reply(text_content, mention_author=False, view=view)
                except disnake.HTTPException as y:
                    # if original message is deleted before bot has sent msg, this prevents error
                    view.message = await ctx.send(text_content, view=view)
        except Exception as e:
            # if list doesn't exist
            text_content = "The `addfave` command, used by typing `@RandomSongsBot#3234 randommusic addfave [genre_name]`, is used to add music genres to your personal favourites list. In the `randommusic` command, you can add the `-genre fave` tag and I'll grab a random song from one of your favourite genres, like so: `@RandomSongsBot#3234 randommusic -genre fave`. It appears you haven't yet added any favourite music genres to your list!\n\nYou can view your personal favourites list by typing `@RandomSongsBot#3234 randommusic favelist`"
            try:
                view.message = await ctx.reply(text_content, mention_author=False, view=view)
            except disnake.HTTPException as y:
                # if original message is deleted before bot has sent msg, this prevents error
                view.message = await ctx.send(text_content, view=view)

def setup(bot):
    bot.add_cog(RandomSongCog(bot))
