import os
import asyncio
import concurrent.futures

import discord
from discord.ext import commands
import yt_dlp
from dotenv import load_dotenv

# ==== ENV ====
load_dotenv()  # local only; Railway will inject env vars
TOKEN = os.getenv("DISCORD_TOKEN")

# ==== DISCORD ====
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ==== FS SETUP ====
DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ==== QUEUE ====
song_queue = asyncio.Queue()

# ==== YT-DLP ====
def _download_audio_sync(url: str) -> str | None:
    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "m4a", "preferredquality": "192"}
        ],
        # ffmpeg paths inside Docker/Nixpacks
        "ffmpeg_location": "/usr/bin/ffmpeg",
        "ffprobe_location": "/usr/bin/ffprobe",
        "postprocessor_args": ["-hide_banner"],
        "quiet": True,
        "outtmpl": os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s"),
        "default_search": "ytsearch",
        "nocheckcertificate": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # <<< the important part: get the FINAL path >>>
            # After post-processing, yt-dlp stores the real file path here:
            reqs = info.get("requested_downloads") or []
            if reqs and "filepath" in reqs[0]:
                return reqs[0]["filepath"]

            # Fallback (sometimes works if no post-processing changed the name)
            candidate = info.get("filepath") or ydl.prepare_filename(info)
            return candidate if candidate and os.path.exists(candidate) else None
    except Exception as e:
        print(f"[yt-dlp] error: {e}")
        return None

async def download_audio(url: str) -> str | None:
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return await loop.run_in_executor(pool, _download_audio_sync, url)

# ==== HELPERS ====
async def ensure_connected(ctx):
    if ctx.voice_client is None:
        if ctx.author.voice and ctx.author.voice.channel:
            await ctx.author.voice.channel.connect()
            await ctx.send("Joined the voice channel!")
        else:
            await ctx.send("You need to be in a voice channel first!")
            return False
    return True

async def play_next_song(ctx):
    if song_queue.empty():
        await ctx.send("Queue is empty.")
        return

    audio_file = await song_queue.get()
    if audio_file is None or not os.path.exists(audio_file):
        await ctx.send("Failed to load the audio file. Skipping…")
        return await play_next_song(ctx)

    def _after_playback(err):
        if err:
            print(f"[playback] error: {err}")
        # schedule next track from the event loop
        fut = asyncio.run_coroutine_threadsafe(play_next_song(ctx), bot.loop)
        try:
            fut.result()
        except Exception as e:
            print(f"[after] error: {e}")

    source = discord.FFmpegPCMAudio(
        executable="/usr/bin/ffmpeg",
        source=audio_file,
        before_options="-nostdin",
        options="-vn"
    )
    ctx.voice_client.play(source, after=_after_playback)

# ==== COMMANDS ====
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ready)")

@bot.command()
async def join(ctx):
    await ensure_connected(ctx)

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Left the voice channel!")
    else:
        await ctx.send("I'm not in a voice channel!")

@bot.command()
async def play(ctx, *, url: str):
    if url.startswith("https://music.youtube.com"):
        url = url.replace("https://music.youtube.com", "https://www.youtube.com")
        await ctx.send("Detected YouTube Music link, converting to YouTube…")

    if not await ensure_connected(ctx):
        return

    # playlist detection
    if "playlist" in url:
        await ctx.send("Detected a playlist, fetching songs…")
        try:
            with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                entries = info.get("entries") or []
                for entry in entries:
                    song_url = entry.get("webpage_url")
                    if song_url:
                        audio_file = await download_audio(song_url)
                        await song_queue.put(audio_file)
                await ctx.send(f"Queued {len(entries)} tracks.")
        except Exception as e:
            await ctx.send(f"Failed to parse playlist: {e}")
            return
    else:
        audio_file = await download_audio(url)
        await song_queue.put(audio_file)
        await ctx.send(f"Added to queue: {url}")

    if not ctx.voice_client.is_playing():
        await play_next_song(ctx)

@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Paused.")
    else:
        await ctx.send("Nothing is playing.")

@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Resumed.")
    else:
        await ctx.send("Nothing is paused.")

@bot.command()
async def stop(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Stopped.")
    else:
        await ctx.send("Nothing is playing.")

@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped.")
    else:
        await ctx.send("Nothing to skip.")

@bot.command(name="queue")
async def _queue(ctx):
    if song_queue.empty():
        await ctx.send("The queue is empty!")
    else:
        queue_list = list(song_queue._queue)
        message = "🎶 **Current Queue:**\n" + "\n".join(f"{i+1}. {os.path.basename(s) if s else 'Error'}" for i, s in enumerate(queue_list))
        await ctx.send(message)

@bot.command()
async def clear(ctx):
    try:
        while not song_queue.empty():
            await song_queue.get()
        await ctx.send("Cleared the queue!")
    except Exception:
        await ctx.send("Queue already empty.")

# ==== RUN ====
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set.")
bot.run(TOKEN)
