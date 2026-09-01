<h1 align="center">:pager::satellite: Watch Dogs Go Wars Discord Bot Sidekick :satellite::pager:</h1>

## Screenshots
<table> <tr> <td align="center"> <strong>/stats</strong> </td> <td align="center"> <strong>/compare</strong> </td> </tr> <tr> <td align="center"> <img src="https://i.imgur.com/8p7rAVe.png" width="400"> </td> <td align="center"> <img src="https://i.imgur.com/L7JuVuG.png" height="1000" width="400"> </td> </tr> </table>

## Purpose
Users can pull their stats or the stats of other users utilizing the `/stats` command.

Compare the stats of two different users utilizing the `/compare` command.

Note that the badges and badge totals exclude the "State" badges to prevent the doxxing of users.
This is done at the API endpoint, not through the bot so users will have a slightly higher badge total when viewing their profile on wdgwars.pl.

This bot previously had a `/sync` command that would pull your last WiGLE upload and push it to WDGWars.
The command has since been removed as it is much easier to upload to both WiGLE and WDGWars utilizing the [Wardrive Go](https://play.google.com/store/apps/details?id=com.rocketgod.wardrive) Android App.

## Variables
Prior to using the bot the following variables must be changed in the `config.json` file:
- Remove the `XXXX` text in `discord_token` and replace it with your Discord Bot Token.
  - If you do not know how to create a Discord bot, instructions on how to do so can be found [here](https://discordpy.readthedocs.io/en/stable/discord.html)
- Remove the `XXXX` text in `wdgwars_api_key` and replace it with your Watch Dogs Go Wars API Key.
  - Your API key can be found [here](https://wdgwars.pl/profile/), scroll down to "API Keys", and generate a new key with the name "Discord Bot" for example.

## Commands
Once the above variables have been updated, run the bot using the following commands:
- `/stats` to pull a user's WDGWars stats.
- `/compare` to compare WDGWars stats between two users.
- `/help` to display helpful information for the WDGWars Sidekick.
