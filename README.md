<h1 align="center">:pager::satellite: Watch Dogs Go Wars Discord Bot Sidekick :satellite::pager:</h1>

## Screenshots
<table> <tr> <td align="center"> <strong>/stats</strong> </td> <td align="center"> <strong>/compare</strong> </td> </tr> <tr> <td align="center"> <img src="https://i.imgur.com/wrA7XGq.png" width="400"> </td> <td align="center"> <img src="https://i.imgur.com/OjIcNsu.png" width="400"> </td> </tr> </table>

<p align="center"> <img src="https://i.imgur.com/ynj72Bq.png" width=300"> </p>

<p align="center"> <img src="https://i.imgur.com/Ek8qxLU.png" width="700"> </p>

## Purpose
Users can pull their stats or the stats of other users utilizing the `/stats` command.

Compare the stats of two different users utilizing the `/compare` command.

For users primarily wardriving using the [WiGLE WiFi Wardriving](https://play.google.com/store/apps/details?id=net.wigle.wigleandroid&hl=en_US) Android app, the bot has a `/sync` command that will pull the latest upload from [WiGLE](https://wigle.net/) and push it to your [Watch Dogs Go Wars](https://wdgwars.pl/) account.

## Variables
Prior to using the bot the following variables must be changed in the `config.json` file:
- Remove the `XXXX` text in `discord_token` and replace it with your Discord Bot Token.
  - If you do not know how to create a Discord bot, instructions on how to do so can be found [here](https://discordpy.readthedocs.io/en/stable/discord.html)
- Remove the `XXXX` text in `wigle_api_token` and replace it with your WiGLE API Key.
  - Your API key can be found [here](https://api.wigle.net/), select your account page in the lower right, then select "Show My Token".
  - The token you are looking for will be listed as the "Encoded for use".
- Remove the `XXXX` text in `wdgwars_api_key` and replace it with your Watch Dogs Go Wars API Key.
  - Your API key can be found [here](https://wdgwars.pl/profile/), scroll down to "API Keys", and generate a new key with the name "Discord Bot" for example.

## Commands
Once the above variables have been updated, run the bot using the following commands:
- `/stats` to pull a users WDGWars stats.
- `/compare` to compare WDGWars stats between two users.
- `/sync` to pull the latest WiGLE upload and push it to WDGWars.
- `/help` to display helpful information for the WDGWars Sidekick.
