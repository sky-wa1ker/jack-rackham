import requests
import discord
import timeago
import os
from discord.ext import commands
from datetime import datetime



token = os.environ['token']
api_key = os.environ['api_key']


client = commands.Bot(command_prefix = '.')
client.remove_command('help')

@client.event
async def on_ready():
    game = discord.Game("innocent. type .help")
    await client.change_presence(status=discord.Status.online, activity=game)
    print('Online as {0.user}'.format(client))


@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Command is missing one or more required arguments.')
    else:
        await ctx.send('There was some error lol.')


@client.command()
async def ping(ctx):
    await ctx.send(f'Pong! {round(client.latency*1000)}ms')


@client.command()
async def help(ctx):
    embed=discord.Embed(title="Jack Rackham help centre", description="Commands and help:", color=0x007bff)
    embed.add_field(name=".nation {nation/leader name}", value="Search for a nation. (.nation Markovia)", inline=False)
    embed.add_field(name='.counter {target nation ID}', value= 'Search for counters. (.counter 176311)', inline=False)
    embed.add_field(name='.api', value= 'API details, not for general use.')
    embed.add_field(name="About", value="Developed and maintained by Sam Cooper.", inline=False)
    

    await ctx.send(embed=embed)




@client.command()
async def api(ctx):
    if ctx.message.author.id == 343397899369054219:
        api_check = requests.get(f'https://politicsandwar.com/api/v2/nations/{api_key}/&alliance_id=913&date_created=20190830').json()
        max_reqs = api_check['api_request']['api_key_details']['daily_requests_maximum']
        used_reqs = api_check['api_request']['api_key_details']['daily_requests_used']
        remaining_reqs = api_check['api_request']['api_key_details']['daily_requests_remaining']

        await ctx.send(f'Requests made today :** {used_reqs}** \nRequests remaining: **{remaining_reqs}** \nMaximum daily requests: **{max_reqs}**')

    else:
        await ctx.send('This command can only be used by my master.')





#nations_v1 = requests.get(f'https://politicsandwar.com/api/nations/?key={api_key}').json()['nations']


def nation_search(self):
    nations_v2 = requests.get(f'https://politicsandwar.com/api/v2/nations/{api_key}/').json()['data']
    
    result = next((item for item in nations_v2 if (item["nation"]).lower() == (f"{self}").lower()), False)

    if result != False:
        return result
    else:
        return next((item for item in nations_v2 if (item["leader"]).lower() == (f"{self}").lower()), False)



@client.command()
async def nation(ctx, *, nation_name):
    if ctx.channel.name == ('tech_support'):
        result_dict = nation_search(nation_name)
        if result_dict is False:
            await ctx.send('No results.')
        else:
            n_name = result_dict.get('nation')
            n_leader = result_dict.get('leader')
            n_id = result_dict.get('nation_id')
            war_policy = result_dict.get('war_policy')
            war_policy_dict = {1:'Attrition', 2:'Turtle', 3:'Blitzkrieg', 4:'Fortress', 5:'Moneybags', 6:'Pirate', 7:'Tactician', 8:'Gaurdian', 9:'Covert', 10:'Arcane'}
            a_id = result_dict.get('alliance_id')
            a_name = result_dict.get('alliance')
            city_count = result_dict.get('cities')
            o_wars = str(result_dict.get('offensive_wars'))
            d_wars = str(result_dict.get('defensive_wars'))
            score = result_dict.get('score')
            v_mode_turns = str(result_dict.get('v_mode_turns'))
            beige_turns = str(result_dict.get('beige_turns'))
            last_active = result_dict.get('last_active')
            now = datetime.utcnow()
            time_ago = timeago.format(last_active, now)
            soldiers = result_dict.get('soldiers')
            tanks = result_dict.get('tanks')
            aircraft = result_dict.get('aircraft')
            ships = result_dict.get('ships')
            missiles = result_dict.get('missiles')
            nukes = result_dict.get('nukes')
            embed=discord.Embed(title=f'{n_name}', url=f'https://politicsandwar.com/nation/id={n_id}', description=f'{n_leader}', color=0x000000)
            embed.add_field(name="Alliance", value=f"[{a_name}](https://politicsandwar.com/alliance/id={a_id})", inline=False)
            embed.add_field(name="General", value=f"`ID: {n_id} | 🏙️ {city_count} | Score: {score}` \n `{war_policy_dict[war_policy]} | Active: {time_ago}`", inline=False)
            embed.add_field(name="VM-Beige", value=f'`In VM: For {v_mode_turns} turns.\nIn Beige: For {beige_turns} turns.`', inline=False)
            embed.add_field(name="War Range", value=f'`⬆️ {round((score * 0.75),2)} to {round((score * 1.75),2)}\n\n⬇️ {round((score / 1.75),2)} to {round((score / 0.75),2)}`', inline=False)
            embed.add_field(name="Wars", value=f'`⬆️ {o_wars} | ⬇️ {d_wars}`', inline=False)
            embed.add_field(name="Military", value=f'`💂 {soldiers} | ⚙️ {tanks} | ✈️ {aircraft} | 🚢 {ships}\n🚀 {missiles} | ☢️ {nukes}`', inline=False)
            embed.set_footer(text="DM Sam Cooper for help or to report a bug                  .")
            await ctx.send(embed=embed)
    else:
        await ctx.send('Wrong channel mate!')
        
        
        





@client.command()
async def counter(ctx, *, enemy_id):
    if ctx.channel.name == ('tech_support'):
        if enemy_id is int:
            await ctx.send('error lol.')
        else:
            enemy_data = requests.get(f'https://politicsandwar.com/api/nation/id={enemy_id}&key={api_key}').json()
            if enemy_data['success'] is False:
                await ctx.send('There was an error, double check your nation ID.')
            elif int(enemy_data['vmode']) > 0:
                await ctx.send('In VM, cannot be countered.')
            elif enemy_data['defensivewars'] == 3:
                await ctx.send('No slots available, cannot counter.')
            else:
                min_score = round(float(enemy_data['score'])/1.75, 2)
                max_score = round(float(enemy_data['score'])/0.75, 2)
                e_name = enemy_data.get('name')
                e_leader = enemy_data.get('leadername')
                e_alliance = enemy_data.get('alliance')
                e_war_policy = enemy_data.get('war_policy')
                e_city_count = enemy_data.get('cities')
                e_score = enemy_data.get('score')
                e_soldiers = enemy_data.get('soldiers')
                e_tanks = enemy_data.get('tanks')
                e_aircraft = enemy_data.get('aircraft')
                e_ships = enemy_data.get('ships')
                e_missiles = enemy_data.get('missiles')
                e_nukes = enemy_data.get('nukes')
                test_request = requests.get(f'https://politicsandwar.com/api/v2/nations/{api_key}/&alliance_id=913&v_mode=0&min_score={min_score}&max_score={max_score}').json()
                in_range_members = test_request['data']

                if (test_request.get('api_request')).get('success') is True:
                    for d in in_range_members: d['mil_score'] = float(d['soldiers'])*0.001 + float(d['tanks'])*0.005 + float(d['aircraft'])*0.3 + float(d['ships'])*0.75 + float(d['cities']*4.0 + float(d['score']*0.1))
                    counters = sorted(in_range_members, key = lambda i: i['mil_score'],reverse=True)
                    if len(counters) == 1:
                        name1 = (counters[0]).get('nation')
                        id1 = (counters[0]).get('nation_id')
                        leader1 = (counters[0]).get('leader')
                        score1 = (counters[0]).get('score')
                        city_count1 = (counters[0]).get('cities')
                        soldiers1 = (counters[0]).get('soldiers')
                        tanks1 = (counters[0]).get('tanks')
                        aircraft1 = (counters[0]).get('aircraft')
                        ships1 = (counters[0]).get('ships')

                        embed=discord.Embed(title='Counter Search', color=0x000000)
                        embed.add_field(name="Enemy", value=f"[{e_leader} of {e_name}](https://politicsandwar.com/nation/id={enemy_id}) \n `{e_alliance} | {e_war_policy} | 🏙️ {e_city_count} | Score: {e_score}` \n`💂 {e_soldiers} | ⚙️ {e_tanks} | ✈️ {e_aircraft} | 🚢 {e_ships}\n🚀 {e_missiles} | ☢️ {e_nukes}`", inline=False)
                        embed.add_field(name='Counter 1', value=f'[{name1}](https://politicsandwar.com/nation/id={id1}) \n `{leader1} | 🏙️ {city_count1} | Score: {score1}` \n `💂 {soldiers1} | ⚙️ {tanks1} | ✈️ {aircraft1} | 🚢 {ships1}`', inline=False)
                        embed.set_footer(text="DM Sam Cooper for help or to report a bug                     .")

                        await ctx.send(embed=embed)

                    elif len(counters) == 2:
                        name1 = (counters[0]).get('nation')
                        id1 = (counters[0]).get('nation_id')
                        leader1 = (counters[0]).get('leader')
                        score1 = (counters[0]).get('score')
                        city_count1 = (counters[0]).get('cities')
                        soldiers1 = (counters[0]).get('soldiers')
                        tanks1 = (counters[0]).get('tanks')
                        aircraft1 = (counters[0]).get('aircraft')
                        ships1 = (counters[0]).get('ships')

                        name2 = (counters[1]).get('nation')
                        id2 = (counters[1]).get('nation_id')
                        leader2 = (counters[1]).get('leader')
                        score2 = (counters[1]).get('score')
                        city_count2 = (counters[1]).get('cities')
                        soldiers2 = (counters[1]).get('soldiers')
                        tanks2 = (counters[1]).get('tanks')
                        aircraft2 = (counters[1]).get('aircraft')
                        ships2 = (counters[1]).get('ships')

                        embed=discord.Embed(title='Counter Search', color=0x000000)
                        embed.add_field(name="Enemy", value=f"[{e_leader} of {e_name}](https://politicsandwar.com/nation/id={enemy_id}) \n `{e_alliance} | {e_war_policy} | 🏙️ {e_city_count} | Score: {e_score}` \n`💂 {e_soldiers} | ⚙️ {e_tanks} | ✈️ {e_aircraft} | 🚢 {e_ships}\n🚀 {e_missiles} | ☢️ {e_nukes}`", inline=False)
                        embed.add_field(name='Counter 1', value=f'[{name1}](https://politicsandwar.com/nation/id={id1}) \n `{leader1} | 🏙️ {city_count1} | Score: {score1}` \n `💂 {soldiers1} | ⚙️ {tanks1} | ✈️ {aircraft1} | 🚢 {ships1}`', inline=False)
                        embed.add_field(name='Counter 2', value=f'[{name2}](https://politicsandwar.com/nation/id={id2}) \n `{leader2} | 🏙️ {city_count2} | Score: {score2}` \n `💂 {soldiers2} | ⚙️ {tanks2} | ✈️ {aircraft2} | 🚢 {ships2}`', inline=False)
                        embed.set_footer(text="DM Sam Cooper for help or to report a bug                     .")

                        await ctx.send(embed=embed)

                    else:
                        name1 = (counters[0]).get('nation')
                        id1 = (counters[0]).get('nation_id')
                        leader1 = (counters[0]).get('leader')
                        score1 = (counters[0]).get('score')
                        city_count1 = (counters[0]).get('cities')
                        soldiers1 = (counters[0]).get('soldiers')
                        tanks1 = (counters[0]).get('tanks')
                        aircraft1 = (counters[0]).get('aircraft')
                        ships1 = (counters[0]).get('ships')

                        name2 = (counters[1]).get('nation')
                        id2 = (counters[1]).get('nation_id')
                        leader2 = (counters[1]).get('leader')
                        score2 = (counters[1]).get('score')
                        city_count2 = (counters[1]).get('cities')
                        soldiers2 = (counters[1]).get('soldiers')
                        tanks2 = (counters[1]).get('tanks')
                        aircraft2 = (counters[1]).get('aircraft')
                        ships2 = (counters[1]).get('ships')

                        name3 = (counters[2]).get('nation')
                        id3 = (counters[2]).get('nation_id')
                        leader3 = (counters[2]).get('leader')
                        score3 = (counters[2]).get('score')
                        city_count3 = (counters[2]).get('cities')
                        soldiers3 = (counters[2]).get('soldiers')
                        tanks3 = (counters[2]).get('tanks')
                        aircraft3 = (counters[2]).get('aircraft')
                        ships3 = (counters[2]).get('ships')

                        embed=discord.Embed(title='Counter Search', color=0x000000)
                        embed.add_field(name="Enemy", value=f"[{e_leader} of {e_name}](https://politicsandwar.com/nation/id={enemy_id}) \n `{e_alliance} | {e_war_policy} | 🏙️ {e_city_count} | Score: {e_score}` \n`💂 {e_soldiers} | ⚙️ {e_tanks} | ✈️ {e_aircraft} | 🚢 {e_ships}\n🚀 {e_missiles} | ☢️ {e_nukes}`", inline=False)
                        embed.add_field(name='Counter 1', value=f'[{name1}](https://politicsandwar.com/nation/id={id1}) \n `{leader1} | 🏙️ {city_count1} | Score: {score1}` \n `💂 {soldiers1} | ⚙️ {tanks1} | ✈️ {aircraft1} | 🚢 {ships1}`', inline=False)
                        embed.add_field(name='Counter 2', value=f'[{name2}](https://politicsandwar.com/nation/id={id2}) \n `{leader2} | 🏙️ {city_count2} | Score: {score2}` \n `💂 {soldiers2} | ⚙️ {tanks2} | ✈️ {aircraft2} | 🚢 {ships2}`', inline=False)
                        embed.add_field(name='Counter 3', value=f'[{name3}](https://politicsandwar.com/nation/id={id3}) \n `{leader3} | 🏙️ {city_count3} | Score: {score3}` \n `💂 {soldiers3} | ⚙️ {tanks3} | ✈️ {aircraft3} | 🚢 {ships3}`', inline=False)
                        embed.set_footer(text="DM Sam Cooper for help or to report a bug                     .")

                        await ctx.send(embed=embed)


                else:
                    await ctx.send('We couldn\'t find any counters')
    else:
        await ctx.send('Wrong channel mate!')


        
        
        
        
        
        
        


client.run(token)