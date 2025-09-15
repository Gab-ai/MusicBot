import discord
from discord.ext import commands
import yt_dlp
import asyncio
import concurrent.futures
import os
from dotenv import load_dotenv

# load environment variables from .env file (local dev only)
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Define the bot and its command prefix
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Define a queue for songs
song_queue = asyncio.Queue()

# Function to download audio from YouTube
def download_audio(url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
            'preferredquality': '192',
        }],
        'ffmpeg_location': '/usr/bin/ffmpeg',
        'ffprobe_location': '/usr/bin/ffprobe',
        'postprocessor_args': ['-hide_banner'],
        'quiet': True,
        'outtmpl': '/home/scoutregiment830/bot_env/downloads/%(title)s.m4a',
        'default_search': 'ytsearch',
        'source_address': '0.0.0.0',
        'nocheckcertificate': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
        except Exception as e:
            print(f"Error downloading audio: {e}")
            return None

async def async_download_audio(url):
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(pool, download_audio, url)
    
# Function to add songs to the queue
async def add_to_queue(ctx, url):
    # Replace YouTube Music links with standard YouTube links
    if url.startswith("https://music.youtube.com"):
        url = url.replace("https://music.youtube.com", "https://www.youtube.com")
        await ctx.send("Detected YouTube Music link, converting to YouTube link...")

    audio_file = download_audio(url)
    await song_queue.put(audio_file)
    await ctx.send(f"Added to queue: {url}")

    # Check if the bot is connected to a voice channel first
    if ctx.voice_client is None:
        if ctx.author.voice:  # Check if the user is in a voice channel
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("You need to be in a voice channel first!")
            return

    # Check if a song is already playing
    if not ctx.voice_client.is_playing():
        await play_next_song(ctx)




# Function to play the next song in the queue
async def play_next_song(ctx):
    if not song_queue.empty():
        audio_file = await song_queue.get()
        print(f"Playing: {audio_file}")

        source = discord.FFmpegPCMAudio(
            executable="/usr/bin/ffmpeg",
            source=audio_file,
            before_options="-nostdin",
            options="-vn"
        )

        ctx.voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next_song(ctx), bot.loop))
    else:
        await ctx.send("Queue is empty.")



# Command to join a voice channel
@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send("Joined the voice channel!")
    else:
        await ctx.send("You need to join a voice channel first!")

# Command to leave a voice channel
@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Left the voice channel!")
    else:
        await ctx.send("I'm not in a voice channel!")

# Command to play a song or playlist
@bot.command()
async def play(ctx, url):
    # Check if it's a playlist
    if 'playlist' in url:
        await ctx.send("Detected a playlist, fetching songs...")
        ydl_opts = {'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            for entry in info['entries']:
                song_url = entry['webpage_url']
                await add_to_queue(ctx, song_url)
    else:
        # If it's a single song
        await add_to_queue(ctx, url)

# Command to pause the song
@bot.command()
async def pause(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Paused the song!")
    else:
        await ctx.send("No song is currently playing.")

# Command to resume the song
@bot.command()
async def resume(ctx):
    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Resumed the song!")
    else:
        await ctx.send("No song is currently paused.")

# Command to stop the song
@bot.command()
async def stop(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Stopped the song!")
    else:
        await ctx.send("No song is currently playing.")

# Command to skip the current song
@bot.command()
async def skip(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped the song!")
    else:
        await ctx.send("No song to skip!")

# Command to view the queue
@bot.command()
async def queue(ctx):
    if song_queue.empty():
        await ctx.send("The queue is empty!")
        print("Queue is empty.")
    else:
        queue_list = list(song_queue._queue)
        print(f"Current queue: {queue_list}")
        message = "🎶 **Current Queue:**\n"
        for idx, song in enumerate(queue_list, 1):
            message += f"{idx}. {song}\n"
        await ctx.send(message)


# Command to clear the queue
@bot.command()
async def clear(ctx):
    while not song_queue.empty():
        await song_queue.get()
    await ctx.send("Cleared the queue!")

# Run the bot
bot.run(TOKEN)
