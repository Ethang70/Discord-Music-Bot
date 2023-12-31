import wavelink # The library used for lavalink
import asyncio # For asyncio.sleep()
import datetime # Used to convert time from S to HH:MM:SS
import discord # Use discord components and embeds
import math # Used for create queue pages
import functions # Used for embed function
import random # Used for shuffle selection song index
import spotipy # Used to get meta data for spotify songs/playlists/albums
import json # Used to load config

from discord import app_commands # Used for slash commands
from discord.ext import commands # To use command tree structure
from spotipy.oauth2 import SpotifyClientCredentials # Used for logging into spotify
from sclib.asyncio import SoundcloudAPI, Track, Playlist # Used for soundcloud

# Load config 
with open('config.json', 'r') as file:
    config = json.load(file)

channel_id = int(config["music_channel_id"])
message_id = int(config["music_channel_msg_id"])
loop = 0
shuffle = 0
paused = True

# Colour to be used on embeds
botColour = config["bot_colour"]
botColourInt = int(botColour, 16)

class Music(commands.Cog):
    """Music cog to hold Wavelink related commands and listeners."""

    def __init__(self, bot):
        self.bot = bot
        self.setup = config["setup"]
        self.spotify = config["use_spotify"]
        self.soundcloud = config["use_soundcloud"]

        bot.loop.create_task(self.connect_nodes())

    #### CLASSES FOR BUTTONS ####

    class music_button_view(discord.ui.View):
        def __init__(self, paused: bool = True, loop: int = 0, shuffle: int = 0, playing: bool = True):
            super().__init__(timeout = None)
            self.paused = paused
            self.loop = loop
            self.shuffle = shuffle
            self.playing = playing
        
            if self.playing:
                if self.paused:
                    self.add_item(Music.PauseButton("<:play:1084708670664880158>", discord.ButtonStyle.green))
                else:
                    self.add_item(Music.PauseButton("<:pause:1084703479114780724>", discord.ButtonStyle.danger))
            else:
                self.add_item(Music.PauseButton("<:play:1084708670664880158>", discord.ButtonStyle.danger))
            
            self.add_item(Music.StopButton())
            self.add_item(Music.SkipButton())
            
            if self.loop == 0:
                self.add_item(Music.LoopButton(discord.ButtonStyle.danger))
            elif self.loop == 1:
                self.add_item(Music.LoopButton(discord.ButtonStyle.green))
            else:
                self.add_item(Music.LoopButton(discord.ButtonStyle.blurple))
            
            if self.shuffle == 0:
                self.add_item(Music.ShuffleButton(discord.ButtonStyle.danger))
            else:
                self.add_item(Music.ShuffleButton(discord.ButtonStyle.green))

    class PauseButton(discord.ui.Button['pause']):
        def __init__(self, emoji : str, style):
            super().__init__(style=style, emoji=emoji)

        async def callback(self, interaction: discord.Interaction):
            ctx = await interaction.client.get_context(interaction.message)
            check = await Music.check_cond(Music, ctx, interaction, ctx.voice_client)

            if check:
                await interaction.response.defer()
                vc: wavelink.Player = ctx.voice_client

                if vc.is_paused():
                    await vc.resume()
                else:
                    await vc.pause()
                
                await Music.update_embed(Music, vc)

    class StopButton(discord.ui.Button['stop']):
        def __init__(self):
            super().__init__(style=discord.ButtonStyle.danger, emoji="<:stop:1084708262169034792>")

        async def callback(self, interaction: discord.Interaction):
            ctx = await interaction.client.get_context(interaction.message)

            check = await Music.check_cond(self, ctx, interaction, ctx.voice_client)

            if check:
                await interaction.response.defer()
                vc: wavelink.Player = ctx.voice_client
                vc.queue.clear()
                await Music.reset_embed(self, vc)
                await vc.disconnect()


    class SkipButton(discord.ui.Button['skip']):
        def __init__(self):
            super().__init__(style=discord.ButtonStyle.danger, emoji="<:skip:1084707456975908908>")
            
        async def callback(self, interaction: discord.Interaction):
            ctx = await interaction.client.get_context(interaction.message)

            check = await Music.check_cond(self, ctx, interaction, ctx.voice_client)

            if check:
                await interaction.response.defer()
                vc: wavelink.Player = ctx.voice_client
                end = vc.track.duration
                await vc.seek(end*1000)

    
    class LoopButton(discord.ui.Button['loop']):
        def __init__(self, style):
            super().__init__(style=style, emoji="<:loopeat:1084703648724033546>")

        async def callback(self, interaction: discord.Interaction):
            ctx = await interaction.client.get_context(interaction.message)
            check = await Music.check_cond(self, ctx, interaction, ctx.voice_client)

            if check:
                await interaction.response.defer()
                vc: wavelink.Player = ctx.voice_client
                
                global loop

                loop = loop + 1

                if loop > 2:
                    loop = 0

                await Music.update_embed(self, vc)


    class ShuffleButton(discord.ui.Button['shuffle']):
        def __init__(self, style):
            super().__init__(style=style, emoji="<:shuffle:1084703804995403806>")

        async def callback(self, interaction: discord.Interaction):
            ctx = await interaction.client.get_context(interaction.message)
            check = await Music.check_cond(self, ctx, interaction, ctx.voice_client)

            if check:
                await interaction.response.defer()
                vc: wavelink.Player = ctx.voice_client

                global shuffle

                if shuffle == 0:
                    shuffle = 1
                else:
                    shuffle = 0

                await Music.update_embed(self, vc)

    #### GENERAL FUNCTIONS ####

    async def connect_nodes(self):
        """Connect to our Lavalink nodes."""
        await self.bot.wait_until_ready()

        await wavelink.NodePool.create_node(bot=self.bot,
                                            host=config["lavalink_ip"],
                                            port=config["lavalink_port"],
                                            password=config["lavalink_password"])
            
    # Checks thats conditions are right for interactions
    async def check_cond(self, ctx, interaction, player, author = None):
        if (not ctx.voice_client or not player.is_connected()) and interaction is not None:
            embed = functions.discordEmbed("Failed Check", "Im not connected", botColourInt)
            await interaction.response.send_message(embed=embed, ephemeral = True, delete_after = (5))
            return False
        
        if interaction is not None:
            if not (
            (interaction.client.user.id in ctx.author.voice.channel.voice_states) and
            (interaction.user.id in ctx.author.voice.channel.voice_states)
            ):
                embed = functions.discordEmbed("Failed Check", 'You\'re not in my voice channel', botColourInt)
                await interaction.response.send_message(embed=embed, ephemeral = True, delete_after = (5))
                return False
            elif not ctx.author.voice:
                embed = functions.discordEmbed("Failed Check", 'You\'re not in a voice channel', botColourInt)
                await interaction.response.send_message(embed=embed, ephemeral = True, delete_after = (5))
                return False
            elif interaction.channel_id != channel_id:
                embed = functions.discordEmbed("Failed Check", 'Please use this command in the music channel', botColourInt)
                await interaction.response.send_message(embed=embed, ephemeral = True, delete_after = (5))
                return False
            return True
        else:
            if (ctx.author.voice is None):
                embed = functions.discordEmbed("Failed Check", 'You\'re not in a voice channel', botColourInt)
                msg = await ctx.send(embed=embed)
                await asyncio.sleep(2)
                await msg.delete()
                return False
            elif (not (self.bot.user.id in ctx.author.voice.channel.voice_states)) and (player is not None):
                embed = functions.discordEmbed("Failed Check", 'You\'re not in my voice channel', botColourInt)
                msg = await ctx.send(embed=embed)
                await asyncio.sleep(2)
                await msg.delete()
                return False
            return True
        
    # Deletes message
    async def del_msg(self, message):
        await asyncio.sleep(0.5)
        await message.delete()

    # Converts HH:MM:SS to seconds
    def get_sec(self, time_str :str):
        """Get Seconds from time."""
        seconds= 0
        for part in time_str.split(':'):
            seconds= seconds*60 + int(part, 10)
        return seconds

    # Resets the music embed to default state
    async def reset_embed(self, player):
        channel = player.client.get_channel(channel_id)
        await channel.edit(topic = "Other commands: /mv, /rm, /dc, /q, /np, /seek, /vol")
        message = await channel.fetch_message(message_id)
        embed = discord.Embed(title = "No song currently playing ", color = int(config["bot_colour"], 16))
        embed.add_field(name="Queue: ", value="Empty")
        embed.set_image(url=config["background_image"])
        embed.set_footer(text="Status: Idle")
        Music.playing = False
        Music.paused = True
        await message.edit(content="To add a song join voice, and type song or url here",embed=embed, view=Music.music_button_view())

    # Updates the music embed to reflect whats in the player
    async def update_embed(self, player):
        channels = await player.guild.fetch_channels()

        for channeli in channels:
            if channeli.id == channel_id:
                channel = channeli
                break

        message = await channel.fetch_message(message_id)
        
        if not player.is_connected or not player.is_playing:
            self.reset_embed(self,player)
            return
        else:
            currentSong = player.track
            identifier = currentSong.identifier
            queue = player.queue
            embed = discord.Embed(title = "Playing: " + currentSong.title + " [" + str(datetime.timedelta(seconds=currentSong.length)) + "]", url=currentSong.uri, color = int(config["bot_colour"], 16))
            thumbnail = "https://i.ytimg.com/vi/" + identifier + "/hqdefault.jpg"

            if queue.is_empty:
                qDesc ='Empty'
            else:
                qDesc =''
                if queue.count > 8:
                    for i in range(0,7):
                        try: 
                            song = queue._queue[i]
                            qDesc += f'[{str(i + 1) + " - " + song.title + " [" + str(datetime.timedelta(seconds=song.length)) + "]"}]({song.uri})' + '\n'
                        except:
                            song = queue._queue[i]
                            qDesc += f'[{str(i + 1) + " - " + song.title}]' + '\n'
                    offset = queue.count - 7
                    qDesc += "and " + str(offset) + " more track(s)\n"
                else:
                    for i in range(0,queue.count):
                        try:
                            song = queue._queue[i]
                            qDesc += f'[{str(i + 1) + " - " + song.title + " [" + str(datetime.timedelta(seconds=song.length)) + "]"}]({song.uri})' + '\n'
                        except:
                            song = queue._queue[i]
                            qDesc += f'[{str(i + 1) + " - " + song.title}]' + '\n'
            
            if player.is_paused():
                status = "Paused"
                paused = True
            else:
                status = "Playing"
                paused = False

            if loop == 2:
                status += " 🔂"
            elif loop == 1:
                status += " 🔁"

            if shuffle == 1:
                status += "  🔀"
            
            embed.set_image(url=thumbnail)
            embed.add_field(name="Queue: ", value=qDesc, inline=True)
            embed.set_footer(text="Status: " + status)
            try:
                await message.edit(embed=embed, view=self.music_button_view(paused, loop, shuffle))
            except:
                await message.edit(embed=embed, view=Music.music_button_view(paused, loop, shuffle))

    # Will play next track in queue or dc if no tracks left
    async def next(self, player):
        if player.queue.is_empty:
            await player.guild.voice_client.disconnect(force=True)
            await Music.reset_embed(self, player)
        else:
            next_song = player.queue.get()
            await player.play(next_song)

    # A function to search for a track and to queue it onto the player
    # plus a boolean if the search should try YouTubeMusic first
    async def search_and_queue(self, player: wavelink.Player, ctx: commands.Context, 
                               query: str, ytm: bool = False, sc: bool = False, pl: bool = False):
        try:    
            if ytm:
                track = await wavelink.YouTubeMusicTrack.search(query = query, return_first=True)
                tracks = [track]
            elif pl:
                video = None
                if '&list' in query:
                    query = query.split("&")
                    video = query[0]
                    query = query[1]
                    query = "https://www.youtube.com/playlist?" + query

                tracks = await wavelink.YouTubePlaylist.search(query=query)
                tracks = tracks.tracks
                    
                if video is not None:
                    video = await wavelink.YouTubeTrack.search(query=video, return_first=True)
                    tracks_copy = tracks.copy()
                    for track in tracks_copy:
                        if track.thumb == video.thumb:
                            break
                        tracks.remove(track)
            elif sc:
                track = await wavelink.SoundCloudTrack.search(query=query, return_first=True)
                tracks = [track]
            else:
                track = await wavelink.YouTubeTrack.search(query = query, return_first=True)
                tracks = [track]
        except:
            if not ytm and not pl:
                embed = functions.discordEmbed("Player", "Error: Could not find track, try giving me the URL", botColourInt)
                msg = await ctx.send(embed=embed)
                await asyncio.sleep(2)
                await msg.delete()
                if not player.is_playing():
                    await self.next(player)
            return

        for track in tracks:    
            if player.is_playing():
                player.queue.put(track)
            else:
                await player.play(track)

    #### LISTENERS ####

    # Triggers when a track starts playing
    @commands.Cog.listener()
    async def on_wavelink_track_start(self, player: wavelink.Player, track: wavelink.Track):
        await self.update_embed(player)

    # Triggers when a track ends 
    # Either by full run through or skip
    @commands.Cog.listener()
    async def on_wavelink_track_end(self, player: wavelink.Player, track: wavelink.Track, reason):        
        if shuffle == 1:
            if not player.queue.is_empty:
                index = random.randint(0,player.queue.count-1)
                strack = player.queue._queue[index]
        
        if loop == 0:
            if shuffle == 1 and not player.queue.is_empty:
                await player.play(strack)
                del player.queue._queue[index]
            else:
                await self.next(player)
        elif loop == 2:
            await player.play(track)
        else:
            player.queue.put(track)
            if shuffle == 1 and not player.queue.is_empty:
                await player.play(strack)
                del player.queue._queue[index]
            else:
                await self.next(player)

        if player.is_playing():
            await self.update_embed(player)

    # Triggers when a connection to a node has been established
    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node):
        print(f'Node: <{node.identifier}> is ready!')

    # Triggers when any message is sent
    @commands.Cog.listener()
    async def on_message(self, message):
        bot = self.bot

        # So the bot doesn't react to its own messages.
        if message.author == bot.user:
            return

        if self.setup is True and message.channel.id == channel_id:
            ctx = await bot.get_context(message)
            asyncio.get_event_loop().create_task(self.del_msg(message))
            ctx.command = bot.get_command('play')
            await self.cog_before_invoke(ctx)
            await ctx.invoke(bot.get_command('play'), query=message.content, author=message.author)


    #### COMMANDS ####

    # Play a song given a query, joins a voicechannel if not already in one
    @commands.command()
    async def play(self, ctx: commands.Context, *, query: str, author):
        check = await Music.check_cond(self, ctx, None, ctx.voice_client, author)
        if not check:
            return
        
        if not ctx.voice_client:
            vc: wavelink.Player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
        else:
            vc: wavelink.Player = ctx.voice_client

        # Dealing with spotify link
        if "open.spotify.com/" in query and self.spotify.lower() == "true":
            # Log into Spotify
            client_credentials_manager = SpotifyClientCredentials(client_id=config["spotify_client_id"], client_secret=config["spotify_client_secret"])
            sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

            # Grab URI
            URI = query.split("/")[-1].split("?")[0]

            # Dealing with playlist
            if "playlist" in query:
                results = sp.playlist_tracks(URI)
                tracks = results['items']

                # Grab all entries in playlist
                while results['next']:
                    results = sp.next(results)
                    tracks.extend(results['items'])

                embed = functions.discordEmbed("Spotify Playlist", "Adding songs to queue, please wait", botColourInt)
                embed.set_thumbnail(url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExZTkwMzc4NTViYzliOTdiMmY2NTcyMmE0OTE0N2ZmNTIyOTFiNmIwMCZjdD1z/cOfwtFobGCLJBU3DNn/giphy.gif")
                msg = await ctx.send(embed=embed)

                for track in tracks:
                    track_name = track["track"]["name"]
                    artist_name = track["track"]["artists"][0]["name"]
                    album = track["track"]["album"]["name"]

                    ytm_query = str(str(track_name) + " " + str(artist_name) + " " + str(album))
                    await self.search_and_queue(player=vc, ctx=ctx, query=ytm_query, ytm=True)

                await msg.delete()
            else:
                # Dealing with an Album
                album = ""
                if "album" in query:
                    results = sp.album_tracks(URI)
                    tracks = results['items']
                    
                    while results['next']:
                        results = sp.next(results)
                        tracks.extend(results['items'])
                        album = sp.album(URI)['name']
                # Dealing with an individual track
                else:
                    track = sp.track(URI)
                    tracks = [track]

                if len(tracks) > 1:
                    embed = functions.discordEmbed("Spotify Playlist", "Adding songs to queue, please wait", botColourInt)
                    embed.set_thumbnail(url="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExZTkwMzc4NTViYzliOTdiMmY2NTcyMmE0OTE0N2ZmNTIyOTFiNmIwMCZjdD1z/cOfwtFobGCLJBU3DNn/giphy.gif")
                    msg = await ctx.send(embed=embed)

                for track in tracks:
                    track_name = track["name"]
                    artist_name = track["artists"][0]["name"]
                    ytm_query = str(str(track_name) + " " + str(artist_name) + " " + str(album))
                    await self.search_and_queue(player=vc, ctx=ctx, query=ytm_query, ytm=True, pl=True)

                if len(tracks) > 1:
                    await msg.delete()
        # Deal1ing with soundcloud links            
        elif "soundcloud.com" in query and self.soundcloud.lower() == "true":
            api = SoundcloudAPI()
            if '/sets/' in query:
                playlist = await api.resolve(query)
                try:
                    assert type(playlist) is Playlist

                    for track in playlist.tracks:
                        await self.search_and_queue(player=vc, ctx=ctx, query=track.title, sc=True)
                except:
                    assert type(playlist) is Track

                    await self.search_and_queue(player=vc, ctx=ctx, query=playlist.title, sc=True)
            else:
                track = await api.resolve(query)
                assert type(track) is Track

                await self.search_and_queue(player=vc, ctx=ctx, query=track.title, sc=True)
        # Dealing with normal YouTube tracks
        else:
            if query.startswith("https://www.youtube.com/playlist?") or '&list' in query:
                await self.search_and_queue(player=vc, ctx=ctx, query=query, pl=True)
            else:
                if '&t' in query:
                    query = query.split("&")
                    query = query[0]

                await self.search_and_queue(player=vc, ctx=ctx, query=query)
        
        if vc.is_playing():
            await self.update_embed(vc)

    # Moves a song position in the queue to one specified
    @app_commands.command(name = "mv", description = "Change a songs position in queue")
    @app_commands.describe(song_number = "Song number in queue", move_number = "New position in queue")
    async def move(self, interaction: discord.Interaction, song_number: int, move_number: int):
        ctx = await interaction.client.get_context(interaction)
        check = await Music.check_cond(self, ctx, interaction, ctx.voice_client)

        if check:
            vc: wavelink.Player = ctx.voice_client
            if vc.queue.is_empty:
                return
        
            current = song_number - 1
            new = move_number - 1

            if current > len(vc.queue)-1 or current < 0:
                await interaction.response.send_message(content = 'Current index out of bounds', ephemeral = True, delete_after = (2))
        
            if new > len(vc.queue)-1 or new < 0:
                await interaction.response.send_message(content = 'New index out of bounds', ephemeral = True, delete_after = (2))

            song = vc.queue._queue[current]
            
            del vc.queue._queue[current]
            queue = vc.queue

            for i in range(len(queue)-1, new):
                if i == len(queue) -1:
                    queue.put(queue._queue[i])
                else:
                    queue._queue[i+1] = queue._queue[i]
        else:
            return

        vc.queue.put_at_index(new, song)
        await self.update_embed(vc)
        embed = functions.discordEmbed('Move', 'Moved ' + song.title + ' from ' + str(current+1) + ' to ' + str(new+1), botColourInt)
        await interaction.response.send_message(embed=embed, delete_after = (4))

    # Removes a song from queue given its queue index
    @app_commands.command(name = "rm", description = "Remove song from queue")
    @app_commands.describe(song_number = "Song number in queue")
    async def remove(self, interaction: discord.Interaction, song_number: int):
        ctx = await interaction.client.get_context(interaction)
        check = await Music.check_cond(self, ctx, interaction, ctx.voice_client)

        if check:
            vc: wavelink.Player = ctx.voice_client
            if vc.queue.is_empty:
                return
            song = vc.queue._queue[song_number-1]
            del vc.queue._queue[song_number-1]

            embed = functions.discordEmbed('Remove', "Song removed: " + song.title, botColourInt)
            await interaction.response.send_message(embed=embed, delete_after = (1))
            await self.update_embed(vc)

    # Disconnects the bot from the voice channel and clears player queue
    @app_commands.command(name = "dc", description = "Disconnect bot from voice")
    async def disconnect(self, interaction: discord.Interaction):
        ctx = await interaction.client.get_context(interaction)
        check = await Music.check_cond(self, ctx, interaction, ctx.voice_client)

        if check:
            vc: wavelink.Player = ctx.voice_client
            vc.queue.clear()
            await Music.reset_embed(self, vc)
            await vc.disconnect()
            embed = functions.discordEmbed(title = 'Disconnected', description = 'Bot disconnected', colour = botColourInt)
            await interaction.response.send_message(embed=embed, delete_after = (1))

    # Outputs the queue in pages of 10 songs each, page number needs to be inputted
    @app_commands.command(name = "q", description = "Shows music queue")
    @app_commands.describe(page = "Page number of queue")
    async def queue(self, interaction: discord.Interaction, page: int = 1):
        ctx = await interaction.client.get_context(interaction)
        check = await Music.check_cond(self, ctx, interaction, ctx.voice_client)

        if check:
            vc: wavelink.Player = ctx.voice_client
        
        queue = vc.queue

        if len(queue) == 0:
            embed = functions.discordEmbed("Queue", 'No songs in queue | Why not queue something?', int(config["bot_colour"], 16))
            await interaction.response.send_message(embed=embed, ephemeral = True, delete_after = (1))
            return
        
        qDesc = ''

        items_per_page = 10
        pages = math.ceil(len(queue) / items_per_page)

        if page > pages:
            embed = functions.discordEmbed("Queue", 'Invalid page: Max page is ' + str(pages), int(config["bot_colour"], 16))
            await interaction.response.send_message(embed=embed, ephemeral = True, delete_after = (1))
            return

        start = (page - 1) * items_per_page
        if len(queue) < items_per_page:
            end = len(queue)
        elif len(queue) - ((page -1) * items_per_page) > items_per_page:
            end = start + items_per_page
        else:
            end = start + len(queue) - ((page -1) * items_per_page)


        for i in range(start,end):
            song = queue._queue[i]
            qDesc += f'[{str(i + 1) + " - " + song.title}]({song.uri})' + '\n'
            
        
        embed = functions.discordEmbed("Queue", qDesc, int(config["bot_colour"], 16))
        embed.set_footer(text=f'Viewing Page {page}/{pages}')
        await interaction.response.send_message(embed=embed, delete_after = (7))

    # Sends a message containing the current runtime of the song
    @app_commands.command(name = "np", description = "Shows information about whats currently playing")
    async def now(self, interaction: discord.Interaction):
        ctx = await interaction.client.get_context(interaction)
        check = await Music.check_cond(self, ctx, interaction, ctx.voice_client)

        if check:
            vc: wavelink.Player = ctx.voice_client
            current_song  = vc.track
            pos = str(datetime.timedelta(seconds=int(vc.position))) 
            dur = str(datetime.timedelta(seconds=current_song.length)) 

            song = f'**[{current_song.title}]({current_song.uri})**\n({pos}/{dur})'
            embed = discord.Embed(color= int(config["bot_colour"], 16), title='Now Playing', description=song)
            await interaction.response.send_message(embed=embed, ephemeral = True, delete_after = (5))

    # Seeks out and jumps to a point in a song based on time given
    @app_commands.command(name = "seek", description = "Jump to a time in the song")
    @app_commands.describe(time = "Time to jump to in (HH:)MM:SS")
    async def seek(self, interaction: discord.Interaction, time: str):
        ctx = await interaction.client.get_context(interaction)
        check = await Music.check_cond(self, ctx, interaction, ctx.voice_client)

        if check:
            vc: wavelink.Player = ctx.voice_client
            time_msec = self.get_sec(time) * 1000

            if not time_msec:
                embed = functions.discordEmbed('Seek' , 'You need to specify a time to skip to', botColourInt)
            else:
                embed = functions.discordEmbed('Seek', 'Moved track to ' + time, botColourInt)
                await vc.seek(time_msec)
            
            await interaction.response.send_message(embed=embed, delete_after = (1))

    # Adds a volume filter to the player, up to volume increase of 500%
    @app_commands.command(name = "volume", description = "Change volume of the player")
    @app_commands.describe(vol = "Volume in percent (Goes up to 1000%) (No need for %)")
    async def volume(self, interaction: discord.Interaction, vol: int):
        ctx = await interaction.client.get_context(interaction)
        check = await Music.check_cond(self, ctx, interaction, ctx.voice_client)

        if check:
            vc: wavelink.Player = ctx.voice_client

            if vol > 1000 or vol < 0:
                embed = functions.discordEmbed('Volume' , 'Invalid volume size, please try between 0-1000', botColourInt)
            else:
                await vc.set_volume(vol)
                embed = functions.discordEmbed('Volume' , f'🔈 | Set to {vol}%', botColourInt)

            await interaction.response.send_message(embed=embed, delete_after = (1))

    # Only really to be used in the even the embed is stuck/not updated
    @app_commands.command(name = "update", description = "Updates the music embed if stuck")
    async def update(self, interaction: discord.Interaction):
        ctx = await interaction.client.get_context(interaction)
        check = await Music.check_cond(self, ctx, interaction, ctx.voice_client)

        if check:
            vc: wavelink.Player = ctx.voice_client
            await self.update_embed(vc)
            embed = functions.discordEmbed('Update' , 'Updated!', botColourInt)
            await interaction.response.send_message(embed=embed, ephemeral = True)
        else:
            await Music.reset_embed(self, interaction)
            embed = functions.discordEmbed('Update' , 'Reset!', botColourInt)
            await interaction.response.send_message(embed=embed, ephemeral = True)

    # Sets up the channel to take in queries & commands and adds to database
    @app_commands.command(name = "setup", description = "Setups up music channel")
    async def setup(self, interaction: discord.Interaction):
        global channel_id, message_id
        ctx = await interaction.client.get_context(interaction)
        if not ctx.author.guild_permissions.administrator:
            embed = functions.discordEmbed('Setup' , 'You have insufficient permissions', botColourInt)
            await interaction.response.send_message(embed=embed, ephemeral = True)
            return

        if config["setup"] is True:
            embed = functions.discordEmbed('Setup' , 'Music channel already set up :)', botColourInt)  
            await interaction.response.send_message(embed=embed, ephemeral = True)
        else:
            channel = await ctx.guild.create_text_channel("music")
            await channel.edit(topic = "Other commands: /mv, /rm, /dc, /q, /np, /seek, /vol")

            embed = discord.Embed(title = "No song currently playing ", color = int(config["bot_colour"], 16))
            embed.add_field(name="Queue: ", value="Empty")
            embed.set_image(url=config["background_image"]) 
            embed.set_footer(text="Status: Idle")

            message = await channel.send(content="To add a song join voice, and type song or url here",embed=embed, view=Music.music_button_view())

            channel_id = message.channel.id
            message_id = message.id

            config["music_channel_id"] = message.channel.id
            config["music_channel_msg_id"] = message.id
            config["setup"] = True

            with open('config.json', 'w') as json_file:
                json.dump(config, json_file)
            
            embed = functions.discordEmbed('Setup' , 'Channel now setup', botColourInt)
            await interaction.response.send_message(embed=embed, ephemeral = True)


    # Removes the music channel and its entry in the database
    @app_commands.command(name = "terminate", description = "Removes music channel")
    async def terminate(self, interaction: discord.Interaction):
        ctx = await interaction.client.get_context(interaction)
        if not ctx.author.guild_permissions.administrator:
            await interaction.response.send_message("You have insufficient permissions", ephemeral = True)
            return

        if config["setup"] is True:
            channel = interaction.client.get_channel(channel_id)
            await channel.delete()            
            embed = functions.discordEmbed('Terminate' , 'Music channel removed', botColourInt)
            await interaction.response.send_message(embed=embed, ephemeral = True)

            config["music_channel_id"] = 0
            config["music_channel_msg_id"] = 0
            config["setup"] = False

            with open('config.json', 'w') as json_file:
                json.dump(config, json_file)

        else:
            embed = functions.discordEmbed('Terminate' , 'There is no channel setup, please use /setup', botColourInt)
            await interaction.response.send_message(embed=embed, ephemeral = True)

    # Changes the equaliser settings
    @app_commands.command(name = 'eq', description = 'Change the settings of the equaliser.')
    @app_commands.describe(profile = 'Choose a preset EQ Profile.')
    async def eq(self, interaction: discord.Interaction, profile: str):
        ctx = await interaction.client.get_context(interaction)
        check = await Music.check_cond(self, ctx, interaction, ctx.voice_client)
        EQ_FLAT = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0), (8, 0), (9, 0), (10, 0), (11, 0), (12, 0), (13, 0), (14, 0)]
        EQ_BASS_BOOSTED = [(0, 0.8), (1, 0.4275), (2, 0.365), (3, 0.3025), (4, 0.24), (5, 0.1775), (6, 0.115), (7, 0.0525), (8, 0), (9, 0), (10, 0), (11, 0), (12, 0), (13, 0), (14, 0)]
        EQ_MAX_BASS_BOOSTED = [(0, 1.0), (1, 1.0), (2, 1.0), (3, 1.0), (4, 1.0), (5, 1.0), (6, 1.0), (7, 1.0), (8, 0), (9, 0), (10, 0), (11, 0), (12, 0), (13, 0), (14, 0)]
        EQ_ROCK = [(0, 0.45), (1, 0.425), (2, 0.375), (3, 0.325), (4, 0.275), (5, 0.225), (6, 0.175), (7, -0.05), (8, 0.05), (9, 0.1), (10, 0.15), (11, 0.2), (12, 0.25), (13, 0.3), (14, 0.35)]
        EQ_POP = [(0, -0.05), (1, -0.03), (2, -0.025), (3, 0), (4, 0.15), (5, 0.2), (6, 0.32), (7, 0.31), (8, 0.29), (9, 0.23), (10, 0.15), (11, 0.01), (12, -0.025), (13, -0.03), (14, -0.05)]
        EQ_IN_THE_CLUB_TOILETS = [(0, 0.3), (1, 0.25), (2, 0.15), (3, 0.1), (4, -0.25), (5, -0.25), (6, -0.25), (7, -0.25), (8, -0.25), (9, -0.25), (10, -0.25), (11, -0.25), (12, -0.25), (13, -0.25), (14, -0.25)]
        EQ_CLASSICAL = [(0, 0.1), (1, 0.1), (2, 0.05), (3, 0), (4, 0.05), (5, 0.12), (6, 0.14), (7, 0.15), (8, 0.05), (9, 0.14), (10, 0.19), (11, 0.23), (12, 0.15), (13, 0.165), (14, 0.19)]
        EQ_EDM = [(0, 0.45), (1, 0.4), (2, 0.37), (3, 0.15), (4, 0.12), (5, 0), (6, -0.13), (7, -0.06), (8, 0.12), (9, 0.06), (10, 0.02), (11, 0.07), (12, 0.2), (13, 0.35), (14, 0.45)]

        if check:
            if profile.lower() == 'bass boosted':
                eq = wavelink.Equalizer(bands=EQ_BASS_BOOSTED)
                embed = functions.discordEmbed('EQ', 'EQ was set to Bass Boosted.', botColourInt)
            elif profile.lower() == 'max bass boosted':
                eq = wavelink.Equalizer(bands=EQ_MAX_BASS_BOOSTED)
                embed = functions.discordEmbed('EQ', 'EQ was set to Max Bass Boosted.', botColourInt)
            elif profile.lower() == 'rock':
                eq = wavelink.Equalizer(bands=EQ_ROCK)
                embed = functions.discordEmbed('EQ', 'EQ was set to Rock.', botColourInt)
            elif profile.lower() == 'pop':
                eq = wavelink.Equalizer(bands=EQ_POP)
                embed = functions.discordEmbed('EQ', 'EQ was set to Pop.', botColourInt)
            elif profile.lower() == 'in the club toilets':
                eq = wavelink.Equalizer(bands=EQ_IN_THE_CLUB_TOILETS)
                embed = functions.discordEmbed('EQ', 'EQ was set to In The Club Toilets.', botColourInt)
            elif profile.lower() == 'classical':
                eq = wavelink.Equalizer(bands=EQ_POP)
                embed = functions.discordEmbed('EQ', 'EQ was set to Classical.', botColourInt)
            elif profile.lower() == 'edm':
                eq = wavelink.Equalizer(bands=EQ_EDM)
                embed = functions.discordEmbed('EQ', 'EQ was set to EDM.', botColourInt)
            else:
                # Default Flat EQ
                eq = wavelink.Equalizer(bands=EQ_FLAT)
                embed = functions.discordEmbed('EQ', 'EQ was set to flat.', botColourInt)

            # Create filter and set the filter to the player
            eqFilter = wavelink.Filter(equalizer=eq)
            vc: wavelink.Player = ctx.voice_client
            await vc.set_filter(eqFilter)

            await interaction.response.send_message(embed=embed, delete_after = (1))


async def setup(bot):
    await bot.add_cog(Music(bot))