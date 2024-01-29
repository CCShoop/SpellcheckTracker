'''Written by Cael Shoop.'''

import os
import json
import random
import datetime
from dotenv import load_dotenv
from discord import app_commands, Intents, Client, File, Message, Interaction, TextChannel, utils
from discord.ext import tasks

load_dotenv()


def get_time():
    ct = str(datetime.datetime.now())
    hour = int(ct[11:13])
    minute = int(ct[14:16])
    return hour, minute


def get_log_time():
    time = datetime.datetime.now().astimezone()
    output = ''
    if time.hour < 10:
        output += '0'
    output += f'{time.hour}:'
    if time.minute < 10:
        output += '0'
    output += f'{time.minute}:'
    if time.second < 10:
        output += '0'
    output += f'{time.second}'
    return output


def get_score(player):
    return player.score


def main():
    class SpellcheckTrackerClient(Client):
        FILENAME = 'info.json'

        class Player():
            def __init__(self, name):
                self.name = name
                self.score = 0
                self.winCount = 0
                self.registered = True
                self.completedToday = False
                self.filePath = ''
                self.messageContent = ''


        def __init__(self, intents):
            super(SpellcheckTrackerClient, self).__init__(intents=intents)
            self.tree = app_commands.CommandTree(self)
            self.text_channel:TextChannel = None
            self.game_number:int = 0
            self.scored_today = False
            self.sent_warning = False
            self.midnight_called = False
            self.players = []


        def read_json_file(self):
            '''Reads player information from the json file and puts it in the players list'''
            if os.path.exists(self.FILENAME):
                with open(self.FILENAME, 'r', encoding='utf-8') as file:
                    print(f'{get_log_time()}> Reading {self.FILENAME}')
                    data = json.load(file)
                    for firstField, secondField in data.items():
                        if firstField == 'text_channel':
                            self.text_channel = self.get_channel(int(secondField['text_channel']))
                            print(f'{get_log_time()}> Got text channel id of {self.text_channel.id}')
                        elif firstField == 'game_number':
                            self.game_number = int(secondField['game_number'])
                        elif firstField == 'scored_today':
                            self.scored_today = secondField['scored_today']
                            print(f'{get_log_time()}> Scored today: {self.scored_today}')
                        else:
                            player_exists = False
                            for player in self.players:
                                if firstField == player.name:
                                    player_exists = True
                                    break
                            if not player_exists:
                                load_player = self.Player(firstField)
                                load_player.winCount = secondField['winCount']
                                load_player.score = secondField['score']
                                load_player.registered = secondField['registered']
                                load_player.completedToday = secondField['completedToday']
                                self.players.append(load_player)
                                print(f'{get_log_time()}> Loaded player {load_player.name} - '
                                    f'wins: {load_player.winCount}, '
                                    f'score: {load_player.score}, '
                                    f'registered: {load_player.registered}, '
                                    f'completed: {load_player.completedToday}')
                    print(f'{get_log_time()}> Successfully loaded {self.FILENAME}')


        def write_json_file(self):
            '''Writes player information from the players list to the json file'''
            data = {}
            data['text_channel'] = {'text_channel': self.text_channel.id}
            data['game_number'] = {'game_number': self.game_number}
            data['scored_today'] = {'scored_today': self.scored_today}
            for player in self.players:
                data[player.name] = {'winCount': player.winCount,
                                     'score': player.score,
                                     'registered': player.registered,
                                     'completedToday': player.completedToday}
            json_data = json.dumps(data, indent=4)
            print(f'{get_log_time()}> Writing {self.FILENAME}')
            with open(self.FILENAME, 'w+', encoding='utf-8') as file:
                file.write(json_data)


        def get_previous_answers(self):
            if self.scored_today:
                return
            for player in self.players:
                if player.completedToday and os.path.exists(f'{player.name}.png'):
                    player.filePath = f'{player.name}.png'
                    print(f'{get_log_time()}> Found {player.name}\'s answers as file {player.filePath}')


        async def process(self, message: Message, player: Player):
            try:
                parseAll = message.content.split('\n')
                parseGameNum = parseAll[0].split('#')
                parseGameNum = parseGameNum[1]
                if int(parseGameNum) != self.game_number:
                    message.channel.send(f'You sent results for Spellcheck #{parseGameNum}; I\'m currently only accepting results for Spellcheck #{self.game_number}.')
                    return

                player.score = 0
                results = parseAll[1:]
                points = 1
                for line in results:
                    for char in line:
                        if char == '🟩':
                            player.score += points
                    points += 1

                player.completedToday = True
                client.write_json_file()
                print(f'{get_log_time()}> Player {player.name} - score: {player.score}')
                response = f'{message.author.name} scored {player.score} points.\n'
                if player.filePath == '':
                    response += 'Please send a screenshot of your spellings as a spoiler attachment, **NOT** a link.'
                await message.channel.send(response)
            except:
                print(f'{get_log_time()}> User {player.name} submitted invalid result message')
                await message.channel.send(f'{player.name}, you sent a Spellcheck results message with invalid syntax. Please try again.')
                    

        def tally_scores(self):
            '''Sorts players and returns a list of strings to send as Discord messages'''
            if not self.players:
                print('No players to score')
                return

            print(f'{get_log_time()}> Tallying score')
            winners = [] # list of winners - the one/those with the lowest score
            results = [] # list of strings - the scoreboard to print out
            results.append(f'SPELLCHECK #{self.game_number} COMPLETE!\n\n**SCOREBOARD:**\n')

            # sort the players
            spellcheck_players = []
            for player in self.players:
                if player.registered and player.completedToday:
                    spellcheck_players.append(player)
            spellcheck_players.sort(key=get_score)
            first_winner = spellcheck_players[0]
            winners.append(first_winner)
            # for the rest of the players, check if they're tied
            for player_it in spellcheck_players[1:]:
                if player_it.score == first_winner.score:
                    winners.append(player_it)
                else:
                    break
            self.scored_today = True

            place_counter = 1
            prev_score = 0
            for player in spellcheck_players:
                print(f'{get_log_time()}> {place_counter}. {player.name} ({player.winCount} wins) with {player.score} score')
                if player in winners:
                    player.winCount += 1
                    if player.winCount == 1:
                        results.append(f'1. {player.name} (1 win) wins with a score of {player.score}!\n')
                    else:
                        results.append(f'1. {player.name} ({player.winCount} wins) wins with a score of {player.score}!\n')
                else:
                    if player.winCount == 1:
                        results.append(f'{place_counter}. {player.name} (1 win) got a score of {player.score}.\n')
                    else:
                        results.append(f'{place_counter}. {player.name} ({player.winCount} wins) got a score of {player.score}.\n')
                if prev_score != player.score:
                    place_counter += 1
                prev_score = player.score

            self.write_json_file()
            return results

        async def setup_hook(self):
            await self.tree.sync()


    discord_token = os.getenv('DISCORD_TOKEN')
    client = SpellcheckTrackerClient(intents=Intents.all())


    @client.event
    async def on_ready():
        client.read_json_file()
        client.get_previous_answers()
        if not midnight_call.is_running():
            midnight_call.start()
        print(f'{get_log_time()}> {client.user} has connected to Discord!')


    @client.event
    async def on_message(message: Message):
        '''Client on_message event'''
        # message is from this bot or not in dedicated text channel
        if message.author == client.user or client.scored_today:
            return

        if 'Spellcheck #' in message.content and ('🟥' in message.content or '🟩' in message.content):
            await message.delete()
            # no registered players
            if not client.players:
                await message.channel.send(f'{message.author.mention}, there are no registered players! Please register and resend your results to be the first.')
                return
            # find player in memory
            player: client.Player
            foundPlayer = False
            for player_it in client.players:
                if message.author.name == player_it.name:
                    foundPlayer = True
                    player = player_it
            # player is not registered
            if not foundPlayer:
                await message.channel.send(f'{message.author.name}, you are not registered! Please register and resend your results.')
                return
            # player has already sent results
            if player.completedToday:
                print(f'{get_log_time()}> {player.name} tried to resubmit results')
                await message.channel.send(f'{player.name}, you have already submitted your results today.')
                return

            # set channel
            client.text_channel = message.channel
            client.write_json_file()

            # process player's results
            await client.process(message, player)
        elif message.channel.id == client.text_channel.id and message.attachments and message.attachments[0].is_spoiler():
            for player in client.players:
                if message.author.name == player.name:
                    if player.filePath == '':
                        response = f'Received image from {message.author.name}.\n'
                    else:
                        response = f'Received replacement image from {message.author.name}.\n'
                    await message.delete()
                    player.filePath = f'{message.author.name}.png'
                    with open(player.filePath, 'wb') as file:
                        await message.attachments[0].save(file)
                    player.messageContent = message.content
                    if not player.completedToday:
                        response += 'Please copy and send your Spellcheck-generated results.'
                    await message.channel.send(response)
                    break

        if client.scored_today: return
        for player in client.players:
            if player.registered and (not player.completedToday or player.filePath == ''):
                print(f'{get_log_time()}> Waiting for {player.name}')
                return
        scoreboard = ''
        for line in client.tally_scores():
            scoreboard += line
        await message.channel.send(scoreboard)
        for player in client.players:
            if player.registered and player.filePath != '':
                await message.channel.send(content=f'__{player.name}:__\n{player.messageContent}', file=File(player.filePath))
                try:
                    os.remove(player.filePath)
                except OSError as e:
                    print(f'{get_log_time()}> Error deleting {player.filePath}: {e}')
                player.filePath = ''
                player.messageContent = ''


    @client.tree.command(name='register', description='Register for Spellcheck tracking.')
    async def register_command(interaction: Interaction):
        '''Command to register a player'''
        client.text_channel = interaction.channel
        client.write_json_file()
        response = ''
        playerFound = False
        for player in client.players:
            if interaction.user.name.strip() == player.name.strip():
                if player.registered:
                    print(f'{get_log_time()}> User {interaction.user.name.strip()} attempted to re-register for tracking')
                    response += 'You are already registered for Spellcheck tracking!\n'
                else:
                    print(f'{get_log_time()}> Registering user {interaction.user.name.strip()} for tracking')
                    player.registered = True
                    client.write_json_file()
                    response += 'You have been registered for Spellcheck tracking.\n'
                playerFound = True
        if not playerFound:
            print(f'{get_log_time()}> Registering user {interaction.user.name.strip()} for tracking')
            player_obj = client.Player(interaction.user.name.strip())
            client.players.append(player_obj)
            client.write_json_file()
            response += 'You have been registered for Spellcheck tracking.\n'
        await interaction.response.send_message(response)


    @client.tree.command(name='deregister', description='Deregister from Spellcheck tracking. Use twice to delete saved data.')
    async def deregister_command(interaction: Interaction):
        '''Command to deregister a player'''
        client.text_channel = interaction.channel
        client.write_json_file()
        players_copy = client.players.copy()
        response = ''
        playerFound = False
        for player in players_copy:
            if player.name.strip() == interaction.user.name.strip():
                if player.registered:
                    player.registered = False
                    print(f'{get_log_time()}> Deregistered user {player.name}')
                    response += 'You have been deregistered for Spellcheck tracking.'
                else:
                    client.players.remove(player)
                    print(f'{get_log_time()}> Deleted data for user {player.name}')
                    response += 'Your saved data has been deleted for Spellcheck tracking.'
                client.write_json_file()
                playerFound = True
        if not playerFound:
            print(f'{get_log_time()}> Non-existant user {interaction.user.name.strip()} attempted to deregister')
            response += 'You have no saved data for Spellcheck tracking.'
        await interaction.response.send_message(response)


    @tasks.loop(seconds=1)
    async def midnight_call():
        '''Midnight call loop task that is run every second with a midnight check.'''
        if not client.players:
            return

        hour, minute = get_time()
        if client.sent_warning and hour == 23 and minute == 1:
            client.sent_warning = False
        if not client.sent_warning and not client.scored_today and hour == 23 and minute == 0:
            warning = ''
            for player in client.players:
                if player.registered and not player.completedToday:
                    user = utils.get(client.users, name=player.name)
                    warning += f'{user.mention} '
            if warning != '':
                await client.text_channel.send(f'{warning}, you have one hour left to do (or skip) the Spellcheck #{client.game_number}!')
            client.sent_warning = True

        if client.midnight_called and hour == 0 and minute == 1:
            client.midnight_called = False
        if client.midnight_called or hour != 0 or minute != 0:
            return
        client.midnight_called = True

        print(f'{get_log_time()}> It is midnight, sending daily scoreboard if unscored and then mentioning registered players')

        if not client.scored_today:
            shamed = ''
            for player in client.players:
                if player.registered and not player.completedToday:
                    user = utils.get(client.users, name=player.name)
                    if user:
                        shamed += f'{user.mention} '
                    else:
                        print(f'{get_log_time()}> Failed to mention user {player.name}')
            if shamed != '':
                await client.text_channel.send(f'SHAME ON {shamed} FOR NOT DOING Spellcheck #{client.game_number}!')
            scoreboard = ''
            for line in client.tally_scores():
                scoreboard += line
            await client.text_channel.send(scoreboard)
            for player in client.players:
                if player.registered and player.filePath != '':
                    await client.text_channel.send(content=f'__{player.name}:__\n{player.messageContent}', file=File(player.filePath))
                    try:
                        os.remove(player.filePath)
                    except OSError as e:
                        print(f'Error deleting {player.filePath}: {e}')
                    player.filePath = ''
                    player.messageContent = ''

        client.scored_today = False
        everyone = ''
        for player in client.players:
            player.score = 0
            player.completedToday = False
            user = utils.get(client.users, name=player.name)
            if user:
                if player.registered:
                    everyone += f'{user.mention} '
            else:
                print(f'{get_log_time()}> Failed to mention user {player.name}')
        client.game_number += 1
        await client.text_channel.send(f'{everyone}\nIt\'s time to do Spellcheck #{client.game_number}!\nhttps://spellcheck.xyz/')
        client.write_json_file()

    client.run(discord_token)


if __name__ == '__main__':
    main()
