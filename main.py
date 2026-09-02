import asyncio
import discord
import aiohttp
import json
import os
from datetime import datetime
from urllib.parse import quote
from discord import app_commands
from discord import ButtonStyle
from discord.ui import Button, View, Select

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

DISCORD_TOKEN = config["discord_token"]
WDGWARS_API_KEY = config["wdgwars_api_key"]

color = 0xBF00FF  # Purple

# Endpoints
WDGWARS_CARD_URL = "https://wdgwars.pl/card/{}.json"
WDGWARS_API_STATS_URL = "https://wdgwars.pl/api/users/{}/stats"
WDGWARS_LEADERBOARD_URL = "https://wdgwars.pl/api/leaderboard"

intents = discord.Intents.default()
intents.message_content = True


def format_join_date(date_string):
    if not date_string or date_string == "Unknown":
        return "Unknown"

    try:
        date = datetime.strptime(date_string, "%Y-%m-%d")
        return date.strftime("%-d %B %Y")

    except (ValueError, TypeError):
        return date_string


def format_badges(badges):
    if not badges:
        return "None"

    formatted_badges = []

    for badge in badges:
        badge_name = badge.replace("_", " ").title()

        formatted_badges.append(f"`{badge_name}`")

    return " ".join(formatted_badges)


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

        self.add_item(
            Button(label="WDGWars", style=ButtonStyle.link, url="https://wdgwars.pl")
        )

        self.add_item(
            Button(label="WiGLE", style=ButtonStyle.link, url="https://wigle.net")
        )

        self.add_item(
            Button(
                label="Kavitate",
                style=ButtonStyle.link,
                url="https://github.com/kavitate",
            )
        )


bot = SyncBot()


@bot.event
async def on_ready():
    print(f"[SYNC] Logged in as {bot.user}")
    print("[SYNC] Ready to sync WDGWars Sidekick by Kavitate")


def error_embed(title, description):
    return discord.Embed(title=title, description=description, color=color)

async def send_ephemeral_error(interaction, title, description):
    try:
        await interaction.delete_original_response()
    except discord.NotFound:
        pass
    except discord.HTTPException as e:
        print(f"[ERROR] Failed to delete original response: {e}")

    try:
        await interaction.followup.send(
            embed=error_embed(title, description),
            ephemeral=True,
        )
    except discord.NotFound:
        print("[ERROR] Interaction expired before ephemeral error could be sent.")
    except discord.HTTPException as e:
        print(f"[ERROR] Failed to send ephemeral error: {e}")


async def get_wdgwars_card_stats(session, username):
    encoded_username = quote(username, safe="")

    url = WDGWARS_CARD_URL.format(encoded_username)

    headers = {"User-Agent": "wigle-wdgwars-discord-bot/1.0"}

    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return None, f"WDGWars card endpoint returned HTTP {resp.status}"

            data = await resp.json()

            if not data.get("ok"):
                return None, "WDGWars could not find that player."

            return data, None

    except aiohttp.ClientError as e:
        return None, f"Network error: {e}"

    except Exception as e:
        return None, f"Unexpected error: {e}"


async def get_wdgwars_api_stats(session, username):
    encoded_username = quote(username, safe="")

    url = WDGWARS_API_STATS_URL.format(encoded_username)

    headers = {
        "User-Agent": "wigle-wdgwars-discord-bot/1.0",
        "X-API-Key": WDGWARS_API_KEY,
    }

    try:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 404:
                return (
                    None,
                    "WDGWars could not find that player, or the player is hidden.",
                )

            if resp.status == 403:
                return (None, "That player has opted out of public statistics.")

            if resp.status == 429:
                return (
                    None,
                    "WDGWars API rate limit reached. Please try again shortly.",
                )

            if resp.status != 200:
                return (None, f"WDGWars stats API returned HTTP {resp.status}")

            data = await resp.json()

            return data, None

    except aiohttp.ClientError as e:
        return None, f"Network error: {e}"

    except Exception as e:
        return None, f"Unexpected error: {e}"


async def get_combined_wdgwars_stats(session, username):
    card_result, api_result = await asyncio.gather(
        get_wdgwars_card_stats(session, username),
        get_wdgwars_api_stats(session, username),
    )

    card_stats, card_error = card_result
    api_stats, api_error = api_result

    if card_error or not card_stats:
        return (
            None,
            None,
            (
                f"Couldn't retrieve profile information for "
                f"`{username}`.\n\n"
                f"{card_error or 'Profile data was unavailable.'}"
            ),
        )

    if api_error or not api_stats:
        return (
            None,
            None,
            (
                f"Couldn't retrieve statistics for "
                f"`{username}`.\n\n"
                f"{api_error or 'Statistics were unavailable.'}"
            ),
        )

    return card_stats, api_stats, None


async def get_wdgwars_leaderboard(session):
    url = WDGWARS_LEADERBOARD_URL

    headers = {
        "User-Agent": "wigle-wdgwars-discord-bot/1.0",
        "X-API-Key": WDGWARS_API_KEY,
    }

    try:
        async with session.get(url, headers=headers) as resp:

            if resp.status == 401:
                return None, "WDGWars API key is invalid or unauthorized."

            if resp.status == 403:
                return None, "Access to the WDGWars leaderboard was denied."

            if resp.status == 429:
                return None, "WDGWars API rate limit reached. Please try again shortly."

            if resp.status != 200:
                return None, f"WDGWars leaderboard API returned HTTP {resp.status}"

            data = await resp.json()

            return data, None

    except aiohttp.ClientError as e:
        return None, f"Network error: {e}"

    except Exception as e:
        return None, f"Unexpected error: {e}"


def stats_embed(card_stats, api_stats):
    username = card_stats.get("handle", api_stats.get("username", "Unknown"))
    team = card_stats.get("team", "None")
    spectrum = card_stats.get("spectrum", "Unknown")
    rank = card_stats.get("rank", "Unknown").title()
    level = card_stats.get("level", 0)
    pct = card_stats.get("pct", 0)
    title = card_stats.get("title", "Unknown")
    country = api_stats.get("country", "Unknown")
    stats = api_stats.get("stats", {})
    wifi = stats.get("wifi", 0)
    ble = stats.get("ble", 0)
    aircraft = stats.get("aircraft", 0)
    mesh = stats.get("mesh", 0)
    total = stats.get("total", 0)
    badges = stats.get("badges", [])
    joined = format_join_date(api_stats.get("joined", "Unknown"))
    recent_today = api_stats.get("recent_today", 0)
    recent_7d = api_stats.get("recent_7d", 0)

    embed = discord.Embed(title="📊 WDGWars Stats", color=color)
    embed.add_field(name="👤 Player", value=f"{username}", inline=False)
    embed.add_field(name="🌎 Country", value=f"{country}", inline=False)
    embed.add_field(name="🏆 Rank", value=f"{level} - {title} ({rank})", inline=False)
    embed.add_field(name="⌛ Progress to Next Level", value=f"{pct}%", inline=False)
    embed.add_field(name="🏴‍☠️ Team", value=f"{team}", inline=False)
    embed.add_field(name="👁️ Spectrum", value=f"{spectrum}", inline=False)
    embed.add_field(name="📡 WiFi", value=f"{wifi:,}", inline=False)
    embed.add_field(name="📟 Bluetooth", value=f"{ble:,}", inline=False)
    embed.add_field(name="✈️ Aircraft", value=f"{aircraft:,}", inline=False)
    embed.add_field(name="📶 Mesh", value=f"{mesh:,}", inline=False)
    embed.add_field(name="📊 Total", value=f"**{total:,}**", inline=False)
    embed.add_field(name="📅 Joined", value=f"{joined}", inline=False)
    embed.add_field(name="📈 Captures Today", value=f"{recent_today:,}", inline=False)
    embed.add_field(name="📈 Captures in Last 7 Days", value=f"{recent_7d:,}", inline=False)
    embed.add_field(name=f"🏅 Badges ({len(badges)})", value=format_badges(badges), inline=False)

    encoded_username = quote(username, safe="")

    embed.set_image(url=f"https://wdgwars.pl/card/{encoded_username}.png")

    return embed


def compare_embed(card_stats1, api_stats1, card_stats2, api_stats2):
    username1 = api_stats1.get("username", card_stats1.get("handle", "Unknown"))
    username2 = api_stats2.get("username", card_stats2.get("handle", "Unknown"))

    level1 = card_stats1.get("level", 0)
    level2 = card_stats2.get("level", 0)

    title1 = card_stats1.get("title", "Unknown")
    title2 = card_stats2.get("title", "Unknown")

    rank1 = card_stats1.get("rank", "Unknown").title()
    rank2 = card_stats2.get("rank", "Unknown").title()

    pct1 = card_stats1.get("pct", 0)
    pct2 = card_stats2.get("pct", 0)

    team1 = card_stats1.get("team", "None")
    team2 = card_stats2.get("team", "None")

    spectrum1 = card_stats1.get("spectrum", "0/0")
    spectrum2 = card_stats2.get("spectrum", "0/0")

    stats1 = api_stats1.get("stats", {})
    stats2 = api_stats2.get("stats", {})

    badges1 = len(api_stats1.get("badges", []))
    badges2 = len(api_stats2.get("badges", []))

    wifi1 = stats1.get("wifi", 0)
    wifi2 = stats2.get("wifi", 0)

    ble1 = stats1.get("ble", 0)
    ble2 = stats2.get("ble", 0)

    aircraft1 = stats1.get("aircraft", 0)
    aircraft2 = stats2.get("aircraft", 0)

    mesh1 = stats1.get("mesh", 0)
    mesh2 = stats2.get("mesh", 0)

    total1 = stats1.get("total", 0)
    total2 = stats2.get("total", 0)

    joined1 = format_join_date(api_stats1.get("joined", "Unknown"))
    joined2 = format_join_date(api_stats2.get("joined", "Unknown"))

    embed = discord.Embed(title=f"⚔️ {username1} vs {username2}", color=color)

    # Rank
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
        value=(f"{username1}: {rank1_display}\n{username2}: {rank2_display}"),
        inline=False,
    )

    # Progress
    pct1_display = f"{pct1}% 🏆" if pct1 > pct2 else f"{pct1}%"

    pct2_display = f"{pct2}% 🏆" if pct2 > pct1 else f"{pct2}%"

    embed.add_field(
        name="⌛ Progress to Next Level",
        value=(f"{username1}: {pct1_display}\n{username2}: {pct2_display}"),
        inline=False,
    )

    # Team
    embed.add_field(
        name="🏴‍☠️ Team",
        value=(f"{username1}: {team1}\n{username2}: {team2}"),
        inline=False,
    )

    # Badges
    badges1_display = f"{badges1:,} 🏆" if badges1 > badges2 else f"{badges1:,}"

    badges2_display = f"{badges2:,} 🏆" if badges2 > badges1 else f"{badges2:,}"

    embed.add_field(
        name="🏅 Badges",
        value=(f"{username1}: {badges1_display}\n{username2}: {badges2_display}"),
        inline=False,
    )

    # Spectrum
    try:
        spectrum_value1 = int(str(spectrum1).split("/")[0])
    except (ValueError, IndexError):
        spectrum_value1 = 0

    try:
        spectrum_value2 = int(str(spectrum2).split("/")[0])
    except (ValueError, IndexError):
        spectrum_value2 = 0

    spectrum1_display = (
        f"{spectrum1} 🏆" if spectrum_value1 > spectrum_value2 else f"{spectrum1}"
    )

    spectrum2_display = (
        f"{spectrum2} 🏆" if spectrum_value2 > spectrum_value1 else f"{spectrum2}"
    )

    embed.add_field(
        name="👁️ Spectrum",
        value=(f"{username1}: {spectrum1_display}\n{username2}: {spectrum2_display}"),
        inline=False,
    )

    # WiFi
    wifi1_display = f"{wifi1:,} 🏆" if wifi1 > wifi2 else f"{wifi1:,}"

    wifi2_display = f"{wifi2:,} 🏆" if wifi2 > wifi1 else f"{wifi2:,}"

    embed.add_field(
        name="📡 WiFi",
        value=(f"{username1}: {wifi1_display}\n{username2}: {wifi2_display}"),
        inline=False,
    )

    # Bluetooth
    ble1_display = f"{ble1:,} 🏆" if ble1 > ble2 else f"{ble1:,}"

    ble2_display = f"{ble2:,} 🏆" if ble2 > ble1 else f"{ble2:,}"

    embed.add_field(
        name="📟 Bluetooth",
        value=(f"{username1}: {ble1_display}\n{username2}: {ble2_display}"),
        inline=False,
    )

    # Aircraft
    aircraft1_display = (
        f"{aircraft1:,} 🏆" if aircraft1 > aircraft2 else f"{aircraft1:,}"
    )

    aircraft2_display = (
        f"{aircraft2:,} 🏆" if aircraft2 > aircraft1 else f"{aircraft2:,}"
    )

    embed.add_field(
        name="✈️ Aircraft",
        value=(f"{username1}: {aircraft1_display}\n{username2}: {aircraft2_display}"),
        inline=False,
    )

    # Mesh
    mesh1_display = f"{mesh1:,} 🏆" if mesh1 > mesh2 else f"{mesh1:,}"

    mesh2_display = f"{mesh2:,} 🏆" if mesh2 > mesh1 else f"{mesh2:,}"

    embed.add_field(
        name="📶 Mesh",
        value=(f"{username1}: {mesh1_display}\n{username2}: {mesh2_display}"),
        inline=False,
    )

    # Total
    total1_display = f"{total1:,} 🏆" if total1 > total2 else f"{total1:,}"

    total2_display = f"{total2:,} 🏆" if total2 > total1 else f"{total2:,}"

    embed.add_field(
        name="📊 Total",
        value=(f"{username1}: {total1_display}\n{username2}: {total2_display}"),
        inline=False,
    )

    # Joined
    embed.add_field(
        name="📅 Joined",
        value=(f"{username1}: {joined1}\n{username2}: {joined2}"),
        inline=False,
    )

    # Results
    categories = [
        ("Rank", level1, level2),
        ("Progress", pct1, pct2),
        ("Badges", badges1, badges2),
        ("Spectrum", spectrum_value1, spectrum_value2),
        ("WiFi", wifi1, wifi2),
        ("Bluetooth", ble1, ble2),
        ("Aircraft", aircraft1, aircraft2),
        ("Mesh", mesh1, mesh2),
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
        inline=False,
    )

    return embed


def leaderboard_embed(category, entries, as_of=None):
    titles = {
        "today": "☀️ WDGWars Leaderboard — Today",
        "week": "📆 WDGWars Leaderboard — This Week",
        "all_time": "🏆 WDGWars Leaderboard — All-Time",
        "gangs": "🏴‍☠️ WDGWars Leaderboard — Gangs",
        "hunters": "🎯 WDGWars Leaderboard — Bounty Hunters",
    }

    embed = discord.Embed(
        title=titles.get(category, "🏆 WDGWars Leaderboard"),
        color=color,
    )

    entries = entries[:25]

    if not entries:
        embed.description = "No leaderboard data is currently available."
        return embed

    lines = []

    if category in ("today", "week", "all_time"):
        for position, entry in enumerate(entries, start=1):
            username = str(entry.get("username", "Unknown"))
            total = entry.get("total", 0)

            lines.append(
                f"`{position:02}` {username} — **{total:,}**"
            )

    elif category == "gangs":
        for position, entry in enumerate(entries, start=1):
            name = str(entry.get("name", "Unknown"))
            member_count = entry.get("member_count", 0)
            ap_count = entry.get("ap_count", 0)

            lines.append(
                f"`{position:02}` {name} — "
                f"**{ap_count:,}** with {member_count:,} members"
            )

    elif category == "hunters":
        for position, entry in enumerate(entries, start=1):
            username = str(entry.get("username", "Unknown"))
            completed = entry.get("completed", 0)
            earned = entry.get("earned", 0)

            lines.append(
                f"`{position:02}` **{username}** — "
                f"{completed:,} completed "
                f"with {earned:,} earned"
            )

    embed.description = "\n".join(lines)

    if as_of:
        try:
            date = datetime.strptime(as_of, "%Y-%m-%d")
            formatted_as_of = date.strftime("%-d %B %Y")
        except (ValueError, TypeError):
            formatted_as_of = as_of
    else:
        formatted_as_of = "Unknown"

    return embed

class LeaderboardSelect(Select):
    def __init__(self, leaderboard_data, user_id):
        self.leaderboard_data = leaderboard_data
        self.user_id = user_id

        options = [
            discord.SelectOption(
                label="Today",
                value="today",
                emoji="☀️",
                description="Top 25 players today",
            ),
            discord.SelectOption(
                label="This Week",
                value="week",
                emoji="📆",
                description="Top 25 players this week",
            ),
            discord.SelectOption(
                label="All-Time",
                value="all_time",
                emoji="🏆",
                description="Top 25 players of all time",
            ),
            discord.SelectOption(
                label="Gangs",
                value="gangs",
                emoji="🏴‍☠️",
                description="Top 25 gangs",
            ),
            discord.SelectOption(
                label="Bounty Hunters",
                value="hunters",
                emoji="🎯",
                description="Top 25 bounty hunters",
            ),
        ]

        super().__init__(
            placeholder="Select a leaderboard...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]

        entries = self.leaderboard_data.get(category, [])

        embed = leaderboard_embed(
            category,
            entries,
            self.leaderboard_data.get("_as_of"),
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self.view,
        )


class LeaderboardView(View):
    def __init__(self, leaderboard_data, user_id):
        super().__init__(timeout=300)

        self.user_id = user_id
        self.leaderboard_data = leaderboard_data

        self.add_item(
            LeaderboardSelect(
                leaderboard_data,
                user_id,
            )
        )

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Only the person who ran `/leaderboard` can use this menu.",
                ephemeral=True,
            )
            return False

        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


@bot.tree.command(name="stats", description="Look up WDGWars stats for a player.")
@app_commands.describe(username="The WDGWars username to look up")
async def stats_command(interaction: discord.Interaction, username: str):
    try:
        await interaction.response.defer(thinking=True)

    except discord.NotFound:
        print("[STATS] Discord interaction expired before defer.")

        return

    except discord.HTTPException as e:
        print(f"[STATS] Failed to defer interaction: {e}")

        return

    username = username.strip()

    if not username:
        await send_ephemeral_error(
            interaction,
            "🚫 Stats Lookup Failed!",
            "Please provide a WDGWars username.",
        )

        return

    try:
        async with aiohttp.ClientSession() as session:
            card_result, api_result = await asyncio.gather(
                get_wdgwars_card_stats(session, username),
                get_wdgwars_api_stats(session, username),
            )

            card_stats, card_error = card_result
            api_stats, api_error = api_result

            if card_error or not card_stats:
                await send_ephemeral_error(
                    interaction,
                    "🚫 Stats Lookup Failed!",
                    f"Couldn't retrieve profile information "
                    f"for `{username}`.\n\n"
                    f"{card_error or 'Profile data was unavailable.'}",
                )

                return

            if api_error or not api_stats:
                await send_ephemeral_error(
                    interaction,
                    "🚫 Stats Lookup Failed!",
                    f"Couldn't retrieve statistics for "
                    f"`{username}`.\n\n"
                    f"{api_error or 'Statistics were unavailable.'}",
                )

                return

            embed = stats_embed(card_stats, api_stats)

            await interaction.followup.send(embed=embed)

            print(
                f"[STATS] {interaction.user} looked up "
                f"WDGWars player: "
                f"{api_stats.get('username', username)}"
            )

    except aiohttp.ClientError as e:
        await send_ephemeral_error(
            interaction,
            "🚫 Stats Lookup Failed!",
            f"Network error: `{e}`",
        )

        print(f"[STATS] Network error: {e}")

    except discord.NotFound:
        print(
            "[STATS] Discord interaction expired before "
            "the follow-up response could be sent."
        )

    except Exception as e:
        await send_ephemeral_error(
            interaction,
            "🚫 Stats Lookup Failed!",
            f"Unexpected error: `{e}`",
        )

        print(f"[STATS] Error: {e}")


@bot.tree.command(name="compare", description="Compare WDGWars stats between two players.")
@app_commands.describe(username1="First WDGWars username", username2="Second WDGWars username")
async def compare_command(
    interaction: discord.Interaction, username1: str, username2: str
):
    try:
        await interaction.response.defer(thinking=True)

    except discord.NotFound:
        print("[COMPARE] Discord interaction expired before defer.")

        return

    except discord.HTTPException as e:
        print(f"[COMPARE] Failed to defer interaction: {e}")

        return

    username1 = username1.strip()
    username2 = username2.strip()

    if not username1 or not username2:
        await send_ephemeral_error(
            interaction,
            "🚫 Comparison Failed!",
            "Please provide two WDGWars usernames.",
        )

        return

    if username1.lower() == username2.lower():
        await send_ephemeral_error(
            interaction,
            "🚫 Comparison Failed!",
            "Please provide two different usernames.",
        )

        return

    try:
        async with aiohttp.ClientSession() as session:
            player1_result, player2_result = await asyncio.gather(
                get_combined_wdgwars_stats(session, username1),
                get_combined_wdgwars_stats(session, username2),
            )

            card_stats1, api_stats1, error1 = player1_result
            card_stats2, api_stats2, error2 = player2_result

            if error1:
                await send_ephemeral_error(
                    interaction,
                    "🚫 Comparison Failed!",
                    error1,
                )

                return

            if error2:
                await send_ephemeral_error(
                    interaction,
                    "🚫 Comparison Failed!",
                    error2,
                )

                return

            embed = compare_embed(card_stats1, api_stats1, card_stats2, api_stats2)

            await interaction.followup.send(embed=embed)

            print(
                f"[COMPARE] {interaction.user} compared "
                f"{api_stats1.get('username', username1)} vs "
                f"{api_stats2.get('username', username2)}"
            )

    except aiohttp.ClientError as e:
        await send_ephemeral_error(
            interaction,
            "🚫 Comparison Failed!",
            f"Network error: `{e}`",
        )

        print(f"[COMPARE] Network error: {e}")

    except discord.NotFound:
        print(
            "[COMPARE] Discord interaction expired before "
            "the follow-up response could be sent."
        )

    except Exception as e:
        await send_ephemeral_error(
            interaction,
            "🚫 Comparison Failed!",
            f"Unexpected error: `{e}`",
        )

        print(f"[COMPARE] Error: {e}")


@bot.tree.command(name="leaderboards",description="View WDGWars leaderboards.")
async def leaderboard_command(interaction: discord.Interaction):

    try:
        await interaction.response.defer(thinking=True)

    except discord.NotFound:
        print("[LEADERBOARD] Discord interaction expired before defer.")
        return

    except discord.HTTPException as e:
        print(f"[LEADERBOARD] Failed to defer interaction: {e}")
        return

    try:
        async with aiohttp.ClientSession() as session:

            leaderboard_data, error = await get_wdgwars_leaderboard(
                session
            )

        if error or not leaderboard_data:
            await send_ephemeral_error(
                interaction,
                "🚫 Leaderboard Lookup Failed!",
                error or "Leaderboard data was unavailable.",
            )
            return

        category = "today"

        entries = leaderboard_data.get(category, [])

        embed = leaderboard_embed(
            category,
            entries,
            leaderboard_data.get("_as_of"),
        )

        view = LeaderboardView(
            leaderboard_data,
            interaction.user.id,
        )

        await interaction.followup.send(
            embed=embed,
            view=view,
        )

        print(
            f"[LEADERBOARD] {interaction.user} "
            f"viewed the WDGWars leaderboard."
        )

    except aiohttp.ClientError as e:
        await send_ephemeral_error(
            interaction,
            "🚫 Leaderboard Lookup Failed!",
            f"Network error: `{e}`",
        )

        print(f"[LEADERBOARD] Network error: {e}")

    except discord.NotFound:
        print(
            "[LEADERBOARD] Discord interaction expired before "
            "the follow-up response could be sent."
        )

    except Exception as e:
        await send_ephemeral_error(
            interaction,
            "🚫 Leaderboard Lookup Failed!",
            f"Unexpected error: `{e}`",
        )

        print(f"[LEADERBOARD] Error: {e}")


@bot.tree.command(name="help", description="Displays help information for WDGWars Sidekick.")
async def help_command(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)

    help_text = (
        "**Command List**\n"
        "`/stats` - Displays a user's WDGWars stats.\n"
        "`/compare` - Compares WDGWars stats between two users.\n"
        "`/leaderboard` - Displays WDGWars leaderboards.\n"
    )

    embed = discord.Embed(
        title="WDGWars Sidekick Information", description=help_text, color=color
    )

    embed.set_footer(text="WDGWars Sidekick by Kavitate")

    embed.set_image(url="https://i.imgur.com/XpcN6uA.png")

    view = HelpView()

    await interaction.followup.send(embed=embed, view=view)


if __name__ == "__main__":
    if DISCORD_TOKEN == "discord_token":
        print("ERROR: Update config.json with your actual tokens!")
        exit(1)

    if not WDGWARS_API_KEY:
        print("ERROR: WDGWars API Key is not configured!")
        exit(1)

    bot.run(DISCORD_TOKEN)
