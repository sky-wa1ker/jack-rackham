from bs4 import BeautifulSoup
import requests
import discord
import timeago
import os
import json
import asyncio
import aiohttp
import difflib
import pymongo
import re
from discord.ext import commands, tasks
import arrow
from pymongo import MongoClient
from datetime import datetime


token = os.environ['token']
api_key = os.environ['api_key']
db_client = MongoClient(os.environ["db_access_url"])
db = db_client.get_database('jack_rackham_db')


intents = discord.Intents.all()
client = commands.Bot(command_prefix = ';', intents = intents)         #  << change it before pushing it live
client.remove_command('help')


@client.event
async def on_ready():
    game = discord.Game("it cool. type ;help")
    await client.change_presence(status=discord.Status.online, activity=game)
    await get_last_war()
    await get_member_list()
    member_alert.start()
    update_alliance_data.start()
    war_alert.start()
    recruitment.start()
    print('Online as {0.user}'.format(client))






@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Command is missing one or more required arguments.')
    elif isinstance(error, TypeError):
        await ctx.send('Wrong argument type.')
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f'Try again in {round(error.retry_after)} seconds.')



@client.command()
@commands.cooldown(1, 10, commands.BucketType.user)
async def ping(ctx):
    await ctx.send(f'Pong! {round(client.latency*1000)}ms')

@client.command(aliases=['register'])
@commands.cooldown(1, 3, commands.BucketType.default)
async def verify(ctx, nation_id:int):
    if type(db.discord_users.find_one({'_id':ctx.author.id})) is dict:
        await ctx.send('You\'re already registered.')
    elif db.discord_users.find_one({'_id':ctx.message.author.id}) == None:
        r = requests.get(f'https://politicsandwar.com/nation/id={nation_id}')
        if r.status_code == 200:
            try:
                soup = BeautifulSoup(r.content, 'html.parser')
                username = soup.find("td", text="Discord Username:").find_next_sibling("td").text
            except AttributeError:
                await ctx.send('Verification failed, make sure your nation ID is correct and you have your discord username (not server nickname) on your nation page exactly the way you see it on discord.')
            if username == str(ctx.message.author):
                db.discord_users.insert_one({'_id':ctx.author.id, 'username':ctx.author.name, 'nation_id':nation_id, 'nation_link':f'https://politicsandwar.com/nation/id={nation_id}'})
                await ctx.send('Registration successful! you\'ve been verified.')
                await ctx.author.add_roles(discord.utils.get(ctx.author.guild.roles, name='Jack Approves! ✅'))
            else:
                await ctx.send('Verification failed, your username does not match with in-game username.')
        else:
            await ctx.send('I had trouble communicating to PnW server, try again later..')
    else:
        await ctx.send('Something went wrong...')


@client.command(aliases=['ad_register'])
async def ad_verify(ctx, user:discord.User, nation_id:int):
    role = discord.utils.get(ctx.guild.roles, name="Admiralty")
    if role in ctx.author.roles:
        if type(db.discord_users.find_one({'_id':user.id})) is dict:
            await ctx.send('The user has already been registered.')
        elif db.discord_users.find_one({'_id':user.id}) == None:
            db.discord_users.insert_one({'_id':user.id, 'username':user.name, 'nation_id':nation_id, 'nation_link': f'https://politicsandwar.com/nation/id={nation_id}'})
            await ctx.send("Success!, the user has been verified and registered.")
            member = ctx.guild.get_member(user.id)
            await member.add_roles(discord.utils.get(ctx.guild.roles, name='Jack Approves! ✅'))
        else:
            await ctx.send('Something went wrong...')
    else:
        await ctx.send(f'This command is only for {role.name}')
    

@client.command()
async def update_verify(ctx, user:discord.User, nation_id:int):
    role = discord.utils.get(ctx.guild.roles, name="Admiralty")
    if role in ctx.author.roles:
        if type(db.discord_users.find_one({'_id':user.id})) is dict:
            filter = { '_id':user.id }
            db.discord_users.update_one(filter, {"$set": {'username':user.name, 'nation_id':nation_id, 'nation_link': f'https://politicsandwar.com/nation/id={nation_id}'}})
            await ctx.send("Success!, the verification details for this user have been updated.")
        elif db.discord_users.find_one({'_id':user.id}) == None:
            await ctx.send('The user is not verified yet.')
        else:
            await ctx.send('Something went wrong...')
    else:
        await ctx.send(f'This command is only for {role.name}')




@client.command()
async def unregister(ctx):
    if type(db.discord_users.find_one({'_id':ctx.author.id})) is dict:
        db.discord_users.delete_one({'_id':ctx.author.id})
        await ctx.author.remove_roles(discord.utils.get(ctx.author.guild.roles, name='Jack Approves! ✅'))
        await ctx.send('Success! Good bye!')
    else:
        await ctx.send('https://i.kym-cdn.com/photos/images/original/001/535/068/29d.jpg')


@client.command()
async def alliance(ctx, *, aa_name):
    aa_dict = db.alliances.find_one({"query_name":aa_name.lower()})
    if aa_dict:
        aa_id = aa_dict["id"]
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://politicsandwar.com/api/alliance/id={aa_id}&key={api_key}") as r:
                aa_dict = await r.json()
                soldiers = aa_dict["soldiers"]
                tanks = aa_dict["tanks"]
                aircraft = aa_dict["aircraft"]
                ships = aa_dict["ships"]
                embed = discord.Embed(title=f'{aa_dict["name"]}({aa_dict["acronym"]})', url=f'https://politicsandwar.com/alliance/id={aa_dict["allianceid"]}', description=f'''
**General**
ID : {aa_dict["allianceid"]}
Score : {aa_dict["score"]}
Members : {aa_dict["members"]} ({aa_dict["vmodemembers"]} of them in VM.)
Applicants : {aa_dict["applicants"]}
[Discord Link]({aa_dict["irc"]})
**Military (Militarization %)**
Soldiers : {soldiers:,} ({str(round(soldiers/(15000*(aa_dict["cities"])), 2)*100)+"%"})
Tanks : {tanks:,} ({str(round(tanks/(1250*(aa_dict["cities"])), 2)*100)+"%"})
Aircraft : {aircraft:,} ({str(round(aircraft/(75*(aa_dict["cities"])), 2)*100)+"%"})
Ships : {ships:,} ({str(round(ships/(15*(aa_dict["cities"])), 2)*100)+"%"})
Missiles : {aa_dict["missiles"]}
Nukes : {aa_dict["nukes"]}
                ''')
                embed.set_image(url=f"{aa_dict['flagurl']}")
                embed.set_footer(text="DM Sam Cooper for help or to report a bug.", icon_url='https://i.ibb.co/qg5vp8w/dp-cropped.jpg')
                await ctx.send(embed=embed)
    else:
        alliances = db.alliances.find()
        aa_list = [sub['name'] for sub in alliances]
        aa = difflib.get_close_matches(aa_name, aa_list, n=1)
        await ctx.send(f'No exact match, did you mean **{aa[0]}**?')



@client.command(aliases=["whois"])
async def who(ctx, user:discord.User):
    account = db.discord_users.find_one({'_id':user.id})
    if account:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://politicsandwar.com/api/nation/id={account["nation_id"]}&key={api_key}') as r:
                nat_dict = await r.json()
                if nat_dict["success"]:
                    score = float(nat_dict["score"])
                    member_rank_dict = {'1':'Applicant', '2':'Member', '3':'Officer', '4':'Heir', '5':'Leader'}
                    time_ago = arrow.utcnow().shift(minutes=-(nat_dict['minutessinceactive'])).humanize()
                    embed=discord.Embed(title=f'{nat_dict["name"]}', url=f'https://politicsandwar.com/nation/id={nat_dict["nationid"]}', description=f'{nat_dict["leadername"]}', color=0x000000)
                    embed.add_field(name="Alliance", value=f"[{nat_dict['alliance']}](https://politicsandwar.com/alliance/id={nat_dict['allianceid']}) | {member_rank_dict[(nat_dict['allianceposition'])]}", inline=False)
                    embed.add_field(name="General", value=f"`ID: {nat_dict['nationid']} | 🏙️ {nat_dict['cities']} | Score: {score}` \n `{nat_dict['war_policy']} | Active: {time_ago} \n{nat_dict['daysold']} days old. | Discord: {user.display_name} `", inline=False)
                    embed.add_field(name="VM-Beige", value=f'`In VM: For {nat_dict["vmode"]} turns.\nIn Beige: For {nat_dict["beige_turns_left"]} turns.`', inline=False)
                    embed.add_field(name="War Range", value=f'`⬆️ {round((score * 0.75),2)} to {round((score * 1.75),2)}\n\n⬇️ {round((score / 1.75),2)} to {round((score / 0.75),2)}`', inline=False)
                    embed.add_field(name="Wars", value=f'`⬆️ {nat_dict["offensivewars"]} | ⬇️ {nat_dict["defensivewars"]}`', inline=False)
                    embed.add_field(name="Military", value=f'`💂 {nat_dict["soldiers"]} | ⚙️ {nat_dict["tanks"]} | ✈️ {nat_dict["aircraft"]} | 🚢 {nat_dict["ships"]}\n🚀 {nat_dict["missiles"]} | ☢️ {nat_dict["nukes"]}`', inline=False)
                    embed.set_image(url=f'{nat_dict["flagurl"]}')
                    embed.set_footer(text="DM Sam Cooper for help or to report a bug                  .", icon_url='https://i.ibb.co/qg5vp8w/dp-cropped.jpg')

                    await ctx.send(embed=embed)
                else:
                    await ctx.send(nat_dict["error"])
    else:
        await ctx.send("Could not find this user.")



@client.command()
async def user(ctx, nation:int):
    account = db.discord_users.find_one({'nation_id':nation})
    if account:
        user = client.get_user(account["_id"])
        await ctx.send(f'''
Username : `{user.display_name}`
ID : `{user.id}`
        ''')
    else:
        await ctx.send('There was an error.')



@client.command()
async def me(ctx):
    account = db.discord_users.find_one({'_id':ctx.author.id})
    if account:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://politicsandwar.com/api/nation/id={account["nation_id"]}&key={api_key}') as r:
                nat_dict = await r.json()
                if nat_dict["success"]:
                    score = float(nat_dict["score"])
                    member_rank_dict = {'1':'Applicant', '2':'Member', '3':'Officer', '4':'Heir', '5':'Leader'}
                    time_ago = arrow.utcnow().shift(minutes=-(nat_dict['minutessinceactive'])).humanize()
                    embed=discord.Embed(title=f'{nat_dict["name"]}', url=f'https://politicsandwar.com/nation/id={nat_dict["nationid"]}', description=f'{nat_dict["leadername"]}', color=0x000000)
                    embed.add_field(name="Alliance", value=f"[{nat_dict['alliance']}](https://politicsandwar.com/alliance/id={nat_dict['allianceid']}) | {member_rank_dict[(nat_dict['allianceposition'])]}", inline=False)
                    embed.add_field(name="General", value=f"`ID: {nat_dict['nationid']} | 🏙️ {nat_dict['cities']} | Score: {score}` \n `{nat_dict['war_policy']} | Active: {time_ago} \n{nat_dict['daysold']} days old. | Discord: {ctx.author.display_name} `", inline=False)
                    embed.add_field(name="VM-Beige", value=f'`In VM: For {nat_dict["vmode"]} turns.\nIn Beige: For {nat_dict["beige_turns_left"]} turns.`', inline=False)
                    embed.add_field(name="War Range", value=f'`⬆️ {round((score * 0.75),2)} to {round((score * 1.75),2)}\n\n⬇️ {round((score / 1.75),2)} to {round((score / 0.75),2)}`', inline=False)
                    embed.add_field(name="Wars", value=f'`⬆️ {nat_dict["offensivewars"]} | ⬇️ {nat_dict["defensivewars"]}`', inline=False)
                    embed.add_field(name="Military", value=f'`💂 {nat_dict["soldiers"]} | ⚙️ {nat_dict["tanks"]} | ✈️ {nat_dict["aircraft"]} | 🚢 {nat_dict["ships"]}\n🚀 {nat_dict["missiles"]} | ☢️ {nat_dict["nukes"]}`', inline=False)
                    embed.set_image(url=f'{nat_dict["flagurl"]}')
                    embed.set_footer(text="DM Sam Cooper for help or to report a bug                  .", icon_url='https://i.ibb.co/qg5vp8w/dp-cropped.jpg')

                    await ctx.send(embed=embed)
                else:
                    await ctx.send(nat_dict["error"])
    else:
        await ctx.send("Could not find this user.")

@tasks.loop(minutes=1380)
async def update_alliance_data():
    db.alliances.delete_many({})
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://politicsandwar.com/api/alliances/?key={api_key}") as r:
            json_obj = await r.json()
            alliances = json_obj["alliances"]
            for x in alliances:
                x["query_name"] = (x["name"]).lower()
            db.alliances.insert_many((alliances))


@client.command()
async def api(ctx):
    if ctx.message.author.id == 343397899369054219:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://politicsandwar.com/api/v2/nations/{api_key}/&alliance_id=913&date_created=20190830') as r:
                api_check = await r.json()
                max_reqs = api_check['api_request']['api_key_details']['daily_requests_maximum']
                used_reqs = api_check['api_request']['api_key_details']['daily_requests_used']
                remaining_reqs = api_check['api_request']['api_key_details']['daily_requests_remaining']
        await ctx.send(f'Requests made today :** {used_reqs}** \nRequests remaining: **{remaining_reqs}** \nMaximum daily requests: **{max_reqs}**')

    else:
        await ctx.send('This command can only be used by my master.')



async def get_last_war():
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://politicsandwar.com/api/wars/?key={api_key}&limit=5&alliance_id=913') as r:
            json_obj = await r.json()
            wars = json_obj['wars']
            global last_war
            last_war = int(wars[0]["warID"])


@tasks.loop(minutes=2)
async def war_alert():
    await asyncio.sleep(20)
    channel = client.get_channel(514689777778294785)
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://politicsandwar.com/api/wars/?key={api_key}&limit=200&alliance_id=913') as r:
            json_obj = await r.json()
            wars = json_obj['wars']
            last_war_ind = wars.index(next(item for item in wars if item["warID"] == last_war))
            if last_war_ind == 0:
                m = await channel.send('No new wars declared....')
                await asyncio.sleep(15)
                await m.delete()
            else:
                final_wars = wars[0:last_war_ind]
                for i in final_wars:
                    async with session.get(f"https://politicsandwar.com/api/nation/id={i['attackerID']}&key={api_key}") as r2:
                        a_nation_dict = await r2.json()
                        if a_nation_dict["pirate_economy"] == "1":
                            a_off_slots = "6"
                        else:
                            a_off_slots = "5"
                    async with session.get(f"https://politicsandwar.com/api/nation/id={i['defenderID']}&key={api_key}") as r3:
                        d_nation_dict = await r3.json()
                        if d_nation_dict["pirate_economy"] == "1":
                            d_off_slots = "6"
                        else:
                            d_off_slots = "5"
                    if i["defenderAA"] in ("Arrgh", "Arrgh Applicant"):
                        dcolor = 15158332
                    else:
                        dcolor = 3066993
                    embed = discord.Embed(title=f'''{i['attackerAA']} on {i['defenderAA']}''', description=f'''
[{a_nation_dict["name"]}](https://politicsandwar.com/nation/id={i["attackerID"]}) declared a(n) {i['war_type']} war on [{d_nation_dict["name"]}](https://politicsandwar.com/nation/id={i["defenderID"]})
                
Score: `{a_nation_dict['score']}` on `{d_nation_dict['score']}`
Slots: `{str(a_nation_dict["offensivewars"])}/{a_off_slots} | {str(a_nation_dict["defensivewars"])}/3` on `{str(d_nation_dict["offensivewars"])}/{d_off_slots} | {str(d_nation_dict["defensivewars"])}/3`
Cities: `{a_nation_dict["cities"]}` on `{d_nation_dict["cities"]}`
Attacker Military
`💂 {a_nation_dict["soldiers"]} | ⚙️ {a_nation_dict["tanks"]} | ✈️ {a_nation_dict["aircraft"]} | 🚢 {a_nation_dict["ships"]}\n🚀 {a_nation_dict["missiles"]} | ☢️ {a_nation_dict["nukes"]}`
Defender Military
`💂 {d_nation_dict["soldiers"]} | ⚙️ {d_nation_dict["tanks"]} | ✈️ {d_nation_dict["aircraft"]} | 🚢 {d_nation_dict["ships"]}\n🚀 {d_nation_dict["missiles"]} | ☢️ {d_nation_dict["nukes"]}`
[Go to war page.](https://politicsandwar.com/nation/war/timeline/war={i["warID"]})
Find counters: `;counter {i["attackerID"]}`
[Counters with slotter](https://slotter.bsnk.dev/search?nation={i["attackerID"]}&alliances=913&countersMode=true&threatsMode=false&vm=false&grey=true&beige=true)
                    ''', color=dcolor)
                    await channel.send(embed=embed)
                    if i["defenderAA"]=="Arrgh" and type(db.discord_users.find_one({'nation_id':i["defenderID"]})) is dict:
                        account = db.discord_users.find_one({'nation_id':i["defenderID"]})
                        await channel.send(f"You have been attacked <@{account['_id']}>")
            global last_war
            last_war = int(wars[0]['warID'])
                    
                        

def list_diff(old_list, new_list): 
    li_dif = [i for i in old_list if i not in new_list]  #[members left]
    return li_dif

async def get_member_list():
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://politicsandwar.com/api/alliance/id=913&key={api_key}') as r:
            json_obj = await r.json()
            global or_members_list
            or_members_list = json_obj["member_id_list"]


@tasks.loop(hours=1)
async def member_alert():
    channel = client.get_channel(220580210251137024) #channel where alerts are sent
    role = 576711897328386069 #role that gets pinged
    await asyncio.sleep(90)
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://politicsandwar.com/api/alliance/id=913&key={api_key}') as r:
            json_obj = await r.json()
            new_members_list = json_obj["member_id_list"]
            global or_members_list
            changes = list_diff(or_members_list, new_members_list)
            if len(changes) > 0:
                await channel.send(f'<@&{role}> Following nations have left Arrgh.')
                for x in changes:
                    await channel.send(f'https://politicsandwar.com/nation/id={x}')
                or_members_list = new_members_list



@client.command()
async def counter(ctx, enemy_id):
    if ctx.channel.category.name != 'PUBLIC':
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://politicsandwar.com/api/nation/id={enemy_id}&key={api_key}') as r:
                enemy_data = await r.json()
                if enemy_data['success'] is False:
                    await ctx.send('There was an error, double check your nation ID.')
                elif int(enemy_data['vmode']) > 0:
                    await ctx.send('In VM, cannot be countered.')
                elif enemy_data['defensivewars'] == 3:
                    await ctx.send('No slots available, cannot counter.')
                else:
                    min_score = round(float(enemy_data['score']) / 1.75, 2)
                    max_score = round(float(enemy_data['score']) / 0.75, 2)
                    e_name = enemy_data['name']
                    e_leader = enemy_data['leadername']
                    e_alliance = enemy_data['alliance']
                    e_war_policy = enemy_data['war_policy']
                    e_city_count = enemy_data['cities']
                    e_score = enemy_data['score']
                    e_soldiers = enemy_data['soldiers']
                    e_tanks = enemy_data['tanks']
                    e_aircraft = enemy_data['aircraft']
                    e_ships = enemy_data['ships']
                    e_missiles = enemy_data['missiles']
                    e_nukes = enemy_data['nukes']
                    async with session.get(f'https://politicsandwar.com/api/v2/nations/{api_key}/&alliance_id=913&v_mode=0&min_score={min_score}&max_score={max_score}&alliance_position=2,3,4,5') as r2:
                        test_request = await r2.json()
                        in_range_members = test_request['data']

                        if test_request['api_request']['success'] is True:
                            for d in in_range_members: d['mil_score'] = float(d['soldiers']) * 0.001 + float(
                                d['tanks']) * 0.005 + float(d['aircraft']) * 0.3 + float(d['ships']) * 0.75 + float(
                                d['cities'] * 4.0 + float(d['score'] * 0.1))
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

                                embed = discord.Embed(title='Counter Search', color=0x000000)
                                embed.add_field(name="Enemy",
                                                value=f"[{e_leader} of {e_name}](https://politicsandwar.com/nation/id={enemy_id}) \n `{e_alliance} | {e_war_policy} | 🏙️ {e_city_count} | NS: {e_score}` \n`💂 {e_soldiers} | ⚙️ {e_tanks} | ✈️ {e_aircraft} | 🚢 {e_ships}\n🚀 {e_missiles} | ☢️ {e_nukes}`",
                                                inline=False)
                                embed.add_field(name='Counter 1',
                                                value=f'[{name1}](https://politicsandwar.com/nation/id={id1}) \n `{leader1} | 🏙️ {city_count1} | Score: {score1}` \n `💂 {soldiers1} | ⚙️ {tanks1} | ✈️ {aircraft1} | 🚢 {ships1}`',
                                                inline=False)
                                embed.set_footer(text="DM Sam Cooper for help or to report a bug                     .",
                                                 icon_url='https://i.ibb.co/qg5vp8w/dp-cropped.jpg')

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

                                embed = discord.Embed(title='Counter Search', color=0x000000)
                                embed.add_field(name="Enemy",
                                                value=f"[{e_leader} of {e_name}](https://politicsandwar.com/nation/id={enemy_id}) \n `{e_alliance} | {e_war_policy} | 🏙️ {e_city_count} | NS: {e_score}` \n`💂 {e_soldiers} | ⚙️ {e_tanks} | ✈️ {e_aircraft} | 🚢 {e_ships}\n🚀 {e_missiles} | ☢️ {e_nukes}`",
                                                inline=False)
                                embed.add_field(name='Counter 1',
                                                value=f'[{name1}](https://politicsandwar.com/nation/id={id1}) \n `{leader1} | 🏙️ {city_count1} | Score: {score1}` \n `💂 {soldiers1} | ⚙️ {tanks1} | ✈️ {aircraft1} | 🚢 {ships1}`',
                                                inline=False)
                                embed.add_field(name='Counter 2',
                                                value=f'[{name2}](https://politicsandwar.com/nation/id={id2}) \n `{leader2} | 🏙️ {city_count2} | Score: {score2}` \n `💂 {soldiers2} | ⚙️ {tanks2} | ✈️ {aircraft2} | 🚢 {ships2}`',
                                                inline=False)
                                embed.set_footer(text="DM Sam Cooper for help or to report a bug                     .",
                                                 icon_url='https://i.ibb.co/qg5vp8w/dp-cropped.jpg')

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

                                embed = discord.Embed(title='Counter Search', color=0x000000)
                                embed.add_field(name="Enemy",
                                                value=f"[{e_leader} of {e_name}](https://politicsandwar.com/nation/id={enemy_id}) \n `{e_alliance} | {e_war_policy} | 🏙️ {e_city_count} | NS: {e_score}` \n`💂 {e_soldiers} | ⚙️ {e_tanks} | ✈️ {e_aircraft} | 🚢 {e_ships}\n🚀 {e_missiles} | ☢️ {e_nukes}`",
                                                inline=False)
                                embed.add_field(name='Counter 1',
                                                value=f'[{name1}](https://politicsandwar.com/nation/id={id1}) \n `{leader1} | 🏙️ {city_count1} | Score: {score1}` \n `💂 {soldiers1} | ⚙️ {tanks1} | ✈️ {aircraft1} | 🚢 {ships1}`',
                                                inline=False)
                                embed.add_field(name='Counter 2',
                                                value=f'[{name2}](https://politicsandwar.com/nation/id={id2}) \n `{leader2} | 🏙️ {city_count2} | Score: {score2}` \n `💂 {soldiers2} | ⚙️ {tanks2} | ✈️ {aircraft2} | 🚢 {ships2}`',
                                                inline=False)
                                embed.add_field(name='Counter 3',
                                                value=f'[{name3}](https://politicsandwar.com/nation/id={id3}) \n `{leader3} | 🏙️ {city_count3} | Score: {score3}` \n `💂 {soldiers3} | ⚙️ {tanks3} | ✈️ {aircraft3} | 🚢 {ships3}`',
                                                inline=False)
                                embed.set_footer(text="DM Sam Cooper for help or to report a bug                     .",
                                                 icon_url='https://i.ibb.co/qg5vp8w/dp-cropped.jpg')

                                await ctx.send(embed=embed)

                        else:
                            await ctx.send('Couldn\'t find any counters.')


    else:
        await ctx.send('Wrong channel mate!')



@client.command()
async def trade(ctx, resource):
    resources = ['credits', 'coal', 'oil', 'uranium', 'lead', 'iron', 'bauxite', 'gasoline', 'munitions', 'steel', 'aluminum']
    if resource.lower() not in resources:
        await ctx.send('No such resource.')
    else:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://politicsandwar.com/api/tradeprice/?resource={resource.lower()}&key={api_key}') as r:
                trade_dict = await r.json()
                sell_ppu = "${:,}".format(int(trade_dict['lowestbuy']['price']))
                buy_ppu = "${:,}".format(int(trade_dict['highestbuy']['price']))
                total_sell = "${:,}".format(int(trade_dict['lowestbuy']['totalvalue']))
                total_buy = "${:,}".format(int(trade_dict['highestbuy']['totalvalue']))
                embed = discord.Embed(title=f"Real-time prices for {trade_dict['resource']}")
                embed.add_field(name="Lowest Sell Offer", value=f"Amount: **{trade_dict['lowestbuy']['amount']}**\nPrice: **{sell_ppu}** PPU\nTotal: **{total_sell}**", inline=False)
                embed.add_field(name="Highest Buy Offer", value=f"Amount: **{trade_dict['highestbuy']['amount']}**\nPrice: **{buy_ppu}** PPU\nTotal: **{total_buy}**", inline=False)
                embed.add_field(name="Extras", value=f"[Go to sell offers page.](https://politicsandwar.com/index.php?id=90&display=world&resource1={trade_dict['resource']}&buysell=sell&ob=price&od=DEF&maximum=50&minimum=0&search=Go)\n[Go to buy offers page.](https://politicsandwar.com/index.php?id=90&display=world&resource1={trade_dict['resource']}&buysell=buy&ob=price&od=DEF&maximum=50&minimum=0&search=Go)\n[Post a trade offer for {trade_dict['resource']}.](https://politicsandwar.com/nation/trade/create/resource={trade_dict['resource']})")
                embed.set_footer(text="DM Sam Cooper for help or to report a bug.", icon_url='https://i.ibb.co/qg5vp8w/dp-cropped.jpg')
                await ctx.send(embed=embed)


@tasks.loop(minutes=3)
async def recruitment():
    message = """
<p><span style="color: rgb(228, 182, 174);">-------------------------------------------------------------</span> <img src="https://i.ibb.co/s5MYDwf/Arrgh-Flag.jpg" alt="Arrgh-Flag" class="center" border="0"><span style="color: rgb(228, 182, 174);">------------------------------------------------------------</span></p>
<p style="text-align: center;">Hello and welcome to Politics and War<br>Now I know you are getting a lot of messages like this one and you have to read them all so I&apos;ll keep it short</p>
<p style="text-align: center;">Do you like taking orders? insane taxes? do you like receiving a portion of your own taxes in the name of free money (grants)? and being hunted down when you don&apos;t pay them back? if yes, please join any other alliance than Arrgh.</p>
<p style="text-align: center;">If you like pirates, raiding, no taxes whatsoever, freedom to wage wars as you like, join Arrgh!. Don&apos;t be a soulless soldier in another man&apos;s army. Wage war. Destroy as you like. Many others will sell you an idea of power. You...make your own power. We work together to loot and maim this planet as we see fit. You have the potential, don&apos;t waste it taking orders from an idiot.&nbsp;</p>
<p style="text-align: center;"><strong>Arrgh!!!</strong></p>
<p style="text-align: center;"><strong>How to join:</strong><br>1. <a href="https://politicsandwar.com/alliance/join/id=913" target="_blank" rel="noopener noreferrer"></a><a href="https://politicsandwar.com/alliance/join/id=913" rel="noopener noreferrer" target="_blank">Click here to join in-game</a></p>
<p style="text-align: center;">2.&nbsp;<a href="https://discord.gg/rKSST5d">Join our Discord server and open a ticket (mandatory)</a></p>
<p style="text-align: center;"><br></p>
<p style="text-align: center;"><a href="https://politicsandwar.fandom.com/wiki/Arrgh#The_Pirate_Code" rel="noopener noreferrer" target="_blank"><strong>Know more about us (The Pirate Code)</strong></a></p>
"""
    today = datetime.utcnow().strftime('%Y%m%d')
    channel = client.get_channel(312420656312614912)
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://politicsandwar.com/api/v2/nations/{api_key}/&date_created={today}&alliance=none") as r:
            json_obj = await r.json()
            nations = json_obj["data"]
            for x in nations:
                if type(db.recruitment.find_one({"nation_id": x["nation_id"]})) is not dict:
                    data = {'key': api_key, 'to': f'{x["nation_id"]}', 'subject': 'Have you considered piracy?', 'message': message}
                    async with session.post("https://politicsandwar.com/api/send-message", data = data) as p:
                        if p.status == 200:
                            await channel.send(f'Sent message to {x["leader"]} of {x["nation"]} ({x["nation_id"]})')
                            db.recruitment.insert_one(x)
                        else:
                            await channel.send(f'Could not send message to {x["leader"]} of {x["nation"]} ({x["nation_id"]}')


@client.event
async def on_message_delete(message):
    if message.author == client.user:
        return
    elif message.author.bot == True:
        return
    elif message.author.id in [343397899369054219, 356444851803389952]:
        return
    elif message.channel.category_id in [797754859100045332, 520548149698494464, 360585064024768523, 653197917774938123]:
        return
    now = datetime.now() 
    current_time=now.strftime("%H:%M:%S") 
    current_date=now.strftime("%d/%m/%Y") 
    delete_embed=discord.Embed(title = f"Message Deleted", description= f'**User:** <@{message.author.id}>\n**Channel:** <#{message.channel.id}>\n**Message:** \n{message.content}', color=0)
    delete_embed.set_footer(text=f"Message ID: {message.id}\nDate: {current_date} • Time: {current_time}")
    delete_embed.set_author(name =f"{message.author}", icon_url=f"{message.author.avatar}") 
    archive_delete=client.get_channel(312420656312614912)
    try:
        delete_embed.set_image(url=message.attachments[0].proxy_url)
    except IndexError:
        pass
    await archive_delete.send(embed=delete_embed)



@client.event
async def on_message_edit(message_before, message_after):
    if message_before.author == client.user:
        return
    elif message_before.author.bot == True:
        return
    elif message_before.author.id in [343397899369054219, 356444851803389952]:
        return
    elif message_before.channel.category_id in [797754859100045332, 520548149698494464, 360585064024768523, 653197917774938123]:
        return
    now = datetime.now()
    current_time=now.strftime("%H:%M:%S")
    current_date=now.strftime("%d/%m/%Y") 
    delete_embed=discord.Embed(title = f"Message Edited", description= f'**User:** <@{message_before.author.id}>\n**Channel:** <#{message_before.channel.id}>\n**Old Message:** \n{message_before.content}\n**New Message:** \n{message_after.content}', color=0)
    delete_embed.set_footer(text=f"Date: {current_date} • Time: {current_time}")
    delete_embed.set_author(name =f"{message_before.author}", icon_url=f"{message_before.author.avatar}") 
    archive_delete=client.get_channel(312420656312614912)
    await archive_delete.send(embed=delete_embed)


@client.command()
async def piratebuild(ctx):
    await ctx.send('''
```
{
    "infra_needed": 900,
    "imp_total": 18,
    "imp_coalpower": 0,
    "imp_oilpower": 0,
    "imp_windpower": 0,
    "imp_nuclearpower": 1,
    "imp_coalmine": 0,
    "imp_oilwell": 0,
    "imp_uramine": 0,
    "imp_leadmine": 0,
    "imp_ironmine": 0,
    "imp_bauxitemine": 0,
    "imp_farm": 0,
    "imp_gasrefinery": 0,
    "imp_aluminumrefinery": 0,
    "imp_munitionsfactory": 0,
    "imp_steelmill": 0,
    "imp_policestation": 1,
    "imp_hospital": 1,
    "imp_recyclingcenter": 0,
    "imp_subway": 0,
    "imp_supermarket": 0,
    "imp_bank": 0,
    "imp_mall": 0,
    "imp_stadium": 0,
    "imp_barracks": 5,
    "imp_factory": 3,
    "imp_hangars": 5,
    "imp_drydock": 2
}
``` 
    ''')






client.run(token)
