import asyncio
import discord
import aiohttp
import json
import os
from discord import app_commands
from discord import ButtonStyle
from discord.ui import Button, View

# Load Config
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log.txt")

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

DISCORD_TOKEN = config["discord_token"]
WIGLE_API_TOKEN = config["wigle_api_token"]
WDGWARS_API_KEY = config["wdgwars_api_key"]

color = 0xBF00FF  # Purple

# Endpoints
WIGLE_TRANSACTIONS_URL = "https://api.wigle.net/api/v2/file/transactions?pagestart=0"
WIGLE_CSV_URL = "https://api.wigle.net/api/v2/file/csv/{transid}"
WDGWARS_UPLOAD_URL = "https://wdgwars.pl/api/upload-csv"
WDGWARS_LATEST_URL = "https://wdgwars.pl/api/upload-history?limit=1"
WDGWARS_STATS_URL = "https://wdgwars.pl/card/{}.json"

intents = discord.Intents.default()
intents.message_content = True

# Log File
def is_in_log(transid):
    if not os.path.exists(LOG_FILE):
        return False
    with open(LOG_FILE, "r") as f:
        return transid in f.read().splitlines()

def add_to_log(transid):
    with open(LOG_FILE, "a") as f:
        f.write(f"{transid}\n")

# Bot Setup
class SyncBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("[SYNC] Slash commands synced")

class HelpView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="WDGWars", style=ButtonStyle.link, url="https://wdgwars.pl"))
        self.add_item(Button(label="WiGLE", style=ButtonStyle.link, url="https://wigle.net"))
        self.add_item(Button(label="Kavitate", style=ButtonStyle.link, url="https://github.com/kavitate"))

bot = SyncBot()

@bot.event
async def on_ready():
    print(f"[SYNC] Logged in as {bot.user}")
    print(f"[SYNC] Ready to sync WDGWars Uploader by Kavitate")

# Embeds
def error_embed(title, description):
    return discord.Embed(title=f"{title}", description=description, color=color)

def success_embed(lines):
    description = "\n".join(f"{name} {value}" for name, value in lines)
    return discord.Embed(title="✅ Upload Successful!", description=description, color=color)

def info_embed(title, description):
    return discord.Embed(title=f"{title}", description=description, color=color)

# WDGWars API
async def get_wdgwars_latest(session):
    headers = {"X-API-Key": WDGWARS_API_KEY, "User-Agent": "wigle-wdgwars-discord-bot/1.0"}
    try:
        async with session.get(WDGWARS_LATEST_URL, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                uploads = data.get("uploads", [])
                if uploads:
                    return uploads[0]
    except Exception as e:
        print(f"[SYNC] Warning: couldn't fetch WDGWars latest: {e}")
    return None

def build_stats_lines(transid, wdgwars_entry):
    result = wdgwars_entry["result"]
    wdgwars_filename = wdgwars_entry.get("filename", "unknown")
    imported = result.get("imported", 0)
    captured = result.get("captured", 0)
    updated = result.get("updated", 0)
    aircraft_imported = result.get("aircraft_imported", 0)
    duplicates = result.get("duplicates", 0)
    total_received = imported + captured + updated + aircraft_imported + duplicates

    return [
        ("🔑 **Transaction ID:**", f"`{transid}`"),
        ("📄 **File Name:**", f"`{wdgwars_filename}`"),
        ("📊 **Total Received:**", str(total_received)),
        ("🆕 **New:**", str(imported)),
        ("🎯 **Captured:**", str(captured)),
        ("🔄 **Reinforced:**", str(updated)),
        ("✈️ **Aircraft Imported:**", str(aircraft_imported)),
        ("♻️ **Duplicates:**", str(duplicates)),
    ]

async def get_wdgwars_stats(session, username):
    url = WDGWARS_STATS_URL.format(username)

    headers = {"User-Agent": "wigle-wdgwars-discord-bot/1.0"}

    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return None, f"WDGWars returned HTTP {resp.status}"

            data = await resp.json()

            if not data.get("ok"):
                return None, "WDGWars could not find that player."

            return data, None

    except aiohttp.ClientError as e:
        return None, f"Network error: {e}"

    except Exception as e:
        return None, f"Unexpected error: {e}"

def stats_embed(stats):
    username = stats.get("handle", "Unknown")

    embed = discord.Embed(title=f"📊 {username} — WDGWars Stats",color=color)
    embed.add_field(name="👤 Player",value=f"`{username}`",inline=False)
    embed.add_field(name="🏴‍☠️ Team",value=stats.get("team", "None"),inline=False)
    
    level = stats.get("level", 0)
    title = stats.get("title", "Unknown")
    rank = stats.get("rank", "Unknown").title()

    embed.add_field(name="🏆 Rank",value=f"{level} - {title} ({rank})",inline=False)
    embed.add_field(name="⌛ Progress to Next Level",value=f"{stats.get('pct', 0)}%",inline=False)
    embed.add_field(name="🏅 Badges",value=str(stats.get("badges", 0)),inline=False)
    embed.add_field(name="👁️ Spectrum",value=stats.get("spectrum", "Unknown"),inline=False)
    embed.add_field(name="📡 WiFi",value=f"{stats.get('wifi', 0):,}",inline=False)
    embed.add_field(name="📟 Bluetooth",value=f"{stats.get('ble', 0):,}",inline=False)
    embed.add_field(name="📊 Total",value=f"**{stats.get('total', 0):,}**",inline=False)
    embed.set_image(url=f"https://wdgwars.pl/card/{username}.png")

    return embed

def compare_embed(stats1, stats2):
    username1 = stats1.get("handle", "Unknown")
    username2 = stats2.get("handle", "Unknown")

    embed = discord.Embed(
        title=f"⚔️ {username1} vs {username2}",
        color=color
    )

    level1 = stats1.get("level", 0)
    level2 = stats2.get("level", 0)

    title1 = stats1.get("title", "Unknown")
    title2 = stats2.get("title", "Unknown")

    rank1 = stats1.get("rank", "Unknown").title()
    rank2 = stats2.get("rank", "Unknown").title()

    rank1_display = (
        f"{level1} - {title1} ({rank1}) 🏆"
        if level1 > level2
        else f"{level1} - {title1} ({rank1})"
    )

    rank2_display = (
        f"{level2} - {title2} ({rank2}) 🏆"
        if level2 > level1
        else f"{level2} - {title2} ({rank2})"
    )

    embed.add_field(
        name="🏆 Rank",
        value=(
            f"{username1}: {rank1_display}\n"
            f"{username2}: {rank2_display}"
        ),
        inline=False
    )

    pct1 = stats1.get("pct", 0)
    pct2 = stats2.get("pct", 0)

    pct1_display = f"{pct1}% 🏆" if pct1 > pct2 else f"{pct1}%"
    pct2_display = f"{pct2}% 🏆" if pct2 > pct1 else f"{pct2}%"

    embed.add_field(
        name="⌛ Progress to Next Level",
        value=(
            f"{username1}: {pct1_display}\n"
            f"{username2}: {pct2_display}"
        ),
        inline=False
    )

    badges1 = stats1.get("badges", 0)
    badges2 = stats2.get("badges", 0)

    badges1_display = (
        f"{badges1:,} 🏆" if badges1 > badges2
        else f"{badges1:,}"
    )

    badges2_display = (
        f"{badges2:,} 🏆" if badges2 > badges1
        else f"{badges2:,}"
    )

    embed.add_field(
        name="🏅 Badges",
        value=(
            f"{username1}: {badges1_display}\n"
            f"{username2}: {badges2_display}"
        ),
        inline=False
    )

    spectrum1 = stats1.get("spectrum", "0/0")
    spectrum2 = stats2.get("spectrum", "0/0")

    try:
        spectrum_value1 = int(str(spectrum1).split("/")[0])
    except (ValueError, IndexError):
        spectrum_value1 = 0

    try:
        spectrum_value2 = int(str(spectrum2).split("/")[0])
    except (ValueError, IndexError):
        spectrum_value2 = 0

    spectrum1_display = (
        f"{spectrum1} 🏆" if spectrum_value1 > spectrum_value2
        else f"{spectrum1}"
    )

    spectrum2_display = (
        f"{spectrum2} 🏆" if spectrum_value2 > spectrum_value1
        else f"{spectrum2}"
    )

    embed.add_field(
        name="👁️ Spectrum",
        value=(
            f"{username1}: {spectrum1_display}\n"
            f"{username2}: {spectrum2_display}"
        ),
        inline=False
    )

    wifi1 = stats1.get("wifi", 0)
    wifi2 = stats2.get("wifi", 0)

    wifi1_display = (
        f"{wifi1:,} 🏆" if wifi1 > wifi2
        else f"{wifi1:,}"
    )

    wifi2_display = (
        f"{wifi2:,} 🏆" if wifi2 > wifi1
        else f"{wifi2:,}"
    )

    embed.add_field(
        name="📡 WiFi",
        value=(
            f"{username1}: {wifi1_display}\n"
            f"{username2}: {wifi2_display}"
        ),
        inline=False
    )

    ble1 = stats1.get("ble", 0)
    ble2 = stats2.get("ble", 0)

    ble1_display = (
        f"{ble1:,} 🏆" if ble1 > ble2
        else f"{ble1:,}"
    )

    ble2_display = (
        f"{ble2:,} 🏆" if ble2 > ble1
        else f"{ble2:,}"
    )

    embed.add_field(
        name="📟 Bluetooth",
        value=(
            f"{username1}: {ble1_display}\n"
            f"{username2}: {ble2_display}"
        ),
        inline=False
    )

    total1 = stats1.get("total", 0)
    total2 = stats2.get("total", 0)

    total1_display = (
        f"{total1:,} 🏆" if total1 > total2
        else f"{total1:,}"
    )

    total2_display = (
        f"{total2:,} 🏆" if total2 > total1
        else f"{total2:,}"
    )

    embed.add_field(
        name="📊 Total",
        value=(
            f"{username1}: {total1_display}\n"
            f"{username2}: {total2_display}"
        ),
        inline=False
    )

    categories = [
        ("Rank", level1, level2),
        ("Progress", pct1, pct2),
        ("Badges", badges1, badges2),
        ("Spectrum", spectrum_value1, spectrum_value2),
        ("WiFi", wifi1, wifi2),
        ("Bluetooth", ble1, ble2),
        ("Total", total1, total2),
    ]

    wins1 = 0
    wins2 = 0
    ties = 0

    for _, value1, value2 in categories:
        if value1 > value2:
            wins1 += 1
        elif value2 > value1:
            wins2 += 1
        else:
            ties += 1

    if wins1 > wins2:
        winner_text = f"**{username1}** wins! 🏆"
    elif wins2 > wins1:
        winner_text = f"**{username2}** wins! 🏆"
    else:
        winner_text = "🤝 **It's a tie!**"

    embed.add_field(
        name="⚔️ Results",
        value=(
            f"{winner_text}\n"
            f"**{username1}:** {wins1} categories\n"
            f"**{username2}:** {wins2} categories\n"
            f"**Ties:** {ties}"
        ),
        inline=False
    )

    return embed

@bot.tree.command(name="sync", description="Pulls the latest WiGLE upload and pushes it to WDGWars.")
async def sync_command(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    try:
        async with aiohttp.ClientSession() as session:
            # Step 1: Fetch latest WiGLE transaction
            wigle_headers = {"Authorization": f"Basic {WIGLE_API_TOKEN}", "User-Agent": "wigle-wdgwars-discord-bot/1.0"}

            async with session.get(WIGLE_TRANSACTIONS_URL, headers=wigle_headers) as resp:
                if resp.status == 204:
                    await interaction.followup.send(
                        embed=info_embed("⌛ Still Processing",
                            "Latest file hasn't finished uploading to WiGLE.\nPlease try again later."))
                    return

                if resp.status != 200:
                    body = await resp.text()
                    await interaction.followup.send(
                        embed=error_embed("🚫 Upload Failed!",
                            f"WiGLE transactions API returned HTTP {resp.status}.\n```{body[:200]}```"))
                    return

                data = await resp.json()

            results = data.get("results", [])
            if not results:
                await interaction.followup.send(
                    embed=error_embed("🚫 Upload Failed!", "No uploads found on your WiGLE account."))
                return

            latest = results[0]
            transid = latest.get("transid")
            filename = latest.get("fileName", "unknown")
            wait = latest.get("wait")

            if not transid:
                await interaction.followup.send(
                    embed=error_embed("🚫 Upload Failed!", "Couldn't find a transaction ID in the WiGLE response."))
                return

            # Step 2: Check if WiGLE is still processing
            if wait:
                await interaction.followup.send(
                    embed=info_embed("⌛ Still Processing!",
                        f"Latest file hasn't finished uploading to WiGLE.\n"
                        f"Queue Position: `{wait}`\n"
                        f"Transaction ID: `{transid}`\n"
                        f"File Name: `{filename}`\n\n"
                        f"Please try again later."))
                return

            # Step 3: Check log for duplicate
            if is_in_log(transid):
                await interaction.followup.send(
                    embed=info_embed("📄 Duplicate File",
                        f"\nWiGLE transaction ID `{transid}` has already been uploaded to WDGWars.\n"
                        f"File Name: `{filename}`"))
                return

            # Step 4: Log the transaction ID
            add_to_log(transid)

            print(f"[SYNC] Syncing WiGLE upload: {transid} ({filename})")

            # Step 5: Download CSV from WiGLE
            csv_url = WIGLE_CSV_URL.format(transid=transid)

            async with session.get(csv_url, headers=wigle_headers) as resp:
                if resp.status == 204:
                    await interaction.followup.send(
                        embed=info_embed("⌛ Still Processing!",
                            f"Latest file hasn't finished uploading to WiGLE.\n"
                            f"Transaction ID: `{transid}`\n"
                            f"File Name: `{filename}`\n\n"
                            f"Please try again later."))
                    return

                if resp.status != 200:
                    body = await resp.text()
                    await interaction.followup.send(
                        embed=error_embed("🚫 Upload Failed!",
                            f"WiGLE CSV download returned HTTP {resp.status}.\n```{body[:200]}```"))
                    return

                csv_data = await resp.read()

            if not csv_data:
                await interaction.followup.send(
                    embed=error_embed("🚫 Upload Failed!", "WiGLE returned an empty CSV file."))
                return

            csv_size_kb = len(csv_data) / 1024
            print(f"[SYNC] Downloaded CSV: {csv_size_kb:.1f} KB")

            # Step 6: Upload CSV to WDGWars
            wdgwars_headers = {"X-API-Key": WDGWARS_API_KEY, "User-Agent": "wigle-wdgwars-discord-bot/1.0"}

            form = aiohttp.FormData()
            form.add_field("file", csv_data, filename=f"{transid}.csv", content_type="text/csv")

            async with session.post(WDGWARS_UPLOAD_URL, headers=wdgwars_headers, data=form) as resp:
                response_text = await resp.text()

                if resp.status in (200, 202):
                    # Step 7: Poll WDGWars for stats (up to 30s)
                    expected_filename = f"{transid}.csv"
                    wdgwars_result = None
                    max_attempts = 6
                    for attempt in range(max_attempts):
                        if attempt > 0:
                            await asyncio.sleep(5)
                        wdgwars_latest = await get_wdgwars_latest(session)
                        if wdgwars_latest and wdgwars_latest.get("filename") == expected_filename and wdgwars_latest.get("result"):
                            wdgwars_result = wdgwars_latest
                            break
                        print(f"[SYNC] Waiting for WDGWars to process... (attempt {attempt + 1}/{max_attempts})")

                    if wdgwars_result:
                        lines = build_stats_lines(transid, wdgwars_result)
                        await interaction.followup.send(embed=success_embed(lines))
                    else:
                        await interaction.followup.send(embed=info_embed(
                            "⌛ Uploaded — Awaiting Results",
                            f"File `{transid}.csv` was uploaded to WDGWars but is still being processed.\n"
                            f"Run `/sync` again in a minute to see your stats."))

                    print(f"[SYNC] Upload Successful!: {transid}")
                else:
                    await interaction.followup.send(
                        embed=error_embed("🚫 Upload Failed!",
                            f"WDGWars returned HTTP {resp.status}.\n```{response_text[:300]}```"))
                    print(f"[SYNC] Upload failed!: HTTP {resp.status}")

    except aiohttp.ClientError as e:
        await interaction.followup.send(
            embed=error_embed("🚫 Upload Failed!", f"Network error: `{e}`"))
        print(f"[SYNC] Network error: {e}")
    except Exception as e:
        await interaction.followup.send(
            embed=error_embed("🚫 Upload Failed!", f"Unexpected error: `{e}`"))
        print(f"[SYNC] Error: {e}")

@bot.tree.command(name="stats", description="Look up WDGWars stats for a player.")
@app_commands.describe(username="The WDGWars username to look up")
async def stats_command(interaction: discord.Interaction, username: str):
    await interaction.response.defer(thinking=True)

    username = username.strip()

    if not username:
        await interaction.followup.send(
            embed=error_embed(
                "🚫 Stats Lookup Failed!",
                "Please provide a WDGWars username."
            )
        )
        return

    try:
        async with aiohttp.ClientSession() as session:
            stats, error = await get_wdgwars_stats(session, username)

            if error:
                await interaction.followup.send(
                    embed=error_embed(
                        "🚫 Stats Lookup Failed!",
                        error
                    )
                )
                return

            embed = stats_embed(stats)

            await interaction.followup.send(embed=embed)

            print(
                f"[STATS] {interaction.user} looked up "
                f"WDGWars player: {stats.get('handle', username)}"
            )

    except Exception as e:
        await interaction.followup.send(
            embed=error_embed(
                "🚫 Stats Lookup Failed!",
                f"Unexpected error: `{e}`"
            )
        )

        print(f"[STATS] Error: {e}")

@bot.tree.command(name="compare",description="Compare WDGWars stats between two players.")
@app_commands.describe(username1="First WDGWars username",username2="Second WDGWars username")
async def compare_command(
    interaction: discord.Interaction,
    username1: str,
    username2: str
):
    await interaction.response.defer(thinking=True)

    username1 = username1.strip()
    username2 = username2.strip()

    if not username1 or not username2:
        await interaction.followup.send(
            embed=error_embed(
                "🚫 Comparison Failed!",
                "Please provide two WDGWars usernames."
            )
        )
        return

    if username1.lower() == username2.lower():
        await interaction.followup.send(
            embed=error_embed(
                "🚫 Comparison Failed!",
                "Please provide two different usernames."
            )
        )
        return

    try:
        async with aiohttp.ClientSession() as session:

            results = await asyncio.gather(
                get_wdgwars_stats(session, username1),
                get_wdgwars_stats(session, username2)
            )

            stats1, error1 = results[0]
            stats2, error2 = results[1]

            if error1 or not stats1:
                await interaction.followup.send(
                    embed=error_embed(
                        "🚫 Comparison Failed!",
                        f"Couldn't find `{username1}`.\n\n"
                        f"{error1 or 'Player data was unavailable.'}"
                    )
                )
                return

            if error2 or not stats2:
                await interaction.followup.send(
                    embed=error_embed(
                        "🚫 Comparison Failed!",
                        f"Couldn't find `{username2}`.\n\n"
                        f"{error2 or 'Player data was unavailable.'}"
                    )
                )
                return

            embed = compare_embed(stats1, stats2)

            await interaction.followup.send(embed=embed)

            print(
                f"[COMPARE] {interaction.user} compared "
                f"{stats1.get('handle', username1)} vs "
                f"{stats2.get('handle', username2)}"
            )

    except aiohttp.ClientError as e:
        await interaction.followup.send(
            embed=error_embed(
                "🚫 Comparison Failed!",
                f"Network error: `{e}`"
            )
        )

        print(f"[COMPARE] Network error: {e}")

    except Exception as e:
        await interaction.followup.send(
            embed=error_embed(
                "🚫 Comparison Failed!",
                f"Unexpected error: `{e}`"
            )
        )

        print(f"[COMPARE] Error: {e}")

@bot.tree.command(name="help", description="Displays help information for WDGWars Sidekick.")
async def help_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)

    help_text = (
        "**Command List**\n"
        "`/stats` - Displays a users WDGWars stats.\n"
        "`/compare` - Compares WDGWars stats between two users.\n"
        "`/sync` - Pulls the latest WiGLE upload and pushes it to WDGWars.\n"
        "- Allow time for processing after an initial WiGLE upload.\n"
        "- The bot will only pull the most recent upload to WiGLE.\n")

    embed = discord.Embed(title="WDGWars Sidekick Information", description=help_text, color=color)
    embed.set_footer(text="WDGWars Sidekick by Kavitate")
    embed.set_image(url="https://i.imgur.com/XpcN6uA.png")

    view = HelpView()
    await interaction.followup.send(embed=embed, view=view)

if __name__ == "__main__":
    if DISCORD_TOKEN == "discord_token":
        print("ERROR: Update config.json with your actual tokens!")
        exit(1)

    bot.run(DISCORD_TOKEN)
