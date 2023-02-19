from bs4 import BeautifulSoup
import requests
import discord
import calendar
import timeago
import os
import json
import asyncio
import aiohttp
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
graphql = f"https://api.politicsandwar.com/graphql?api_key={api_key}"


intents = discord.Intents.all()
client = commands.Bot(command_prefix = ';', intents = intents)         #  << change it before pushing it live
client.remove_command('help')


@client.event
async def on_ready():
    game = discord.Game("it cool.")
    await client.change_presence(status=discord.Status.online, activity=game)
    if not recruitment.is_running():
        recruitment.start()
    if not war_alert.is_running():
        war_alert.start()
    if not member_updates.is_running():
        member_updates.start()
    if not menu_v3.is_running():
        menu_v3.start()
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
                db.discord_users.insert_one({'_id':ctx.author.id, 'username':ctx.author.name, 'nation_id':nation_id})
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
            db.discord_users.insert_one({'_id':user.id, 'username':user.name, 'nation_id':nation_id})
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
            db.discord_users.update_one(filter, {"$set": {'username':user.name, 'nation_id':nation_id}})
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
                    async with session.get(f'https://politicsandwar.com/api/v2/nations/{api_key}/&alliance_id=913&v_mode=0&min_score={min_score}&max_score={max_score}&alliance_position=2,3,4,5') as r2:
                        test_request = await r2.json()
                        in_range_members = test_request['data']
                        if test_request['api_request']['success'] is True:
                            for d in in_range_members: d['mil_score'] = float(d['soldiers']) * 0.001 + float(
                                d['tanks']) * 0.008 + float(d['aircraft']) * 0.4 + float(d['ships']) * 0.60 + float(
                                d['cities'] * 4.0 + float(d['score'] * 0.1))
                            counters = sorted(in_range_members, key = lambda i: i['mil_score'],reverse=True)
                            if len(counters) >= 5:
                                n = 5
                            else:
                                n = len(counters)
                            enemy_embed = discord.Embed(title='Enemy', description=f'''
[{enemy_data['name']} of {enemy_data['leadername']}](https://politicsandwar.com/nation/id={enemy_id}) \n `{enemy_data['alliance']} | {enemy_data['war_policy']} | 🏙️ {enemy_data['cities']} | NS: {enemy_data['score']}` \n`💂 {enemy_data['soldiers']} | ⚙️ {enemy_data['tanks']} | ✈️ {enemy_data['aircraft']} | 🚢 {enemy_data['ships']}\n🚀 {enemy_data['missiles']} | ☢️ {enemy_data['nukes']}`
                            ''')
                            await ctx.send(embed=enemy_embed)
                            for x in counters[0:n]:
                                counter_embed = discord.Embed(title=f"Counter {counters.index(x)}", description=f'''
[{x['nation']}](https://politicsandwar.com/nation/id={x['nation_id']}) \n `{x['leader']} | 🏙️ {x['cities']} | Score: {x['score']}` \n `💂 {x['soldiers']} | ⚙️ {x['tanks']} | ✈️ {x['aircraft']} | 🚢 {x['ships']}`
                                ''')
                                await ctx.send(embed=counter_embed)
                        else:
                            await ctx.send('Couldn\'t find any counters.')



@client.slash_command(description="See warchest information of a captain, restricted to Mentors and above.")
async def warchest(ctx, nation_id:int=None, user:discord.User=None):
    admiralty = discord.utils.get(ctx.guild.roles, name="Admiralty")
    mentor = discord.utils.get(ctx.guild.roles, name="Mentor")
    if admiralty in ctx.author.roles or mentor in ctx.author.roles:
        await ctx.defer(ephemeral=True)
        if user != None and nation_id == None:
            user_nation = db.discord_users.find_one({"_id": user.id})
            nation_id = user_nation['nation_id']
        nation = db.captains.find_one({"_id": nation_id})
        if nation:
            embed = discord.Embed(title=f"{nation['leader']} of {nation['nation']}", description=f'''
Money : {"${:,.2f}".format(float(nation["money"]))}
Credits : {int(nation['credits'])}
Food : {"{:,.2f}".format(float(nation["food"]))}
Coal : {"{:,.2f}".format(float(nation["coal"]))}
Oil : {"{:,.2f}".format(float(nation["oil"]))}
Uranium : {"{:,.2f}".format(float(nation["uranium"]))}
Lead : {"{:,.2f}".format(float(nation["lead"]))}
Iron : {"{:,.2f}".format(float(nation["iron"]))}
Bauxite : {"{:,.2f}".format(float(nation["bauxite"]))}
Gasoline : {"{:,.2f}".format(float(nation["gasoline"]))}
Munitions : {"{:,.2f}".format(float(nation["munitions"]))}
Steel : {"{:,.2f}".format(float(nation["steel"]))}
Aluminum : {"{:,.2f}".format(float(nation["aluminum"]))}

            ''',)
            await ctx.followup.send(embed=embed)
        else:
            await ctx.followup.send("can't find nation with given arguments.")
    else:
        await ctx.respond('You do not have permission to use this command', ephemeral=True)







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

@client.command()
async def pcode(ctx):
    await ctx.send('https://arrgh-pirate-code.vercel.app/')


@tasks.loop(minutes=3)
async def war_alert():
    await asyncio.sleep(6)
    channel = client.get_channel(514689777778294785)
    misc = db.misc.find_one({'_id':True})
    async with aiohttp.ClientSession() as session:
             async with session.post(graphql, json={'query':f"{{wars(alliance_id:913, min_id:{misc['last_arrgh_war']}, orderBy:{{column:ID, order:ASC}}){{data{{id date war_type reason attacker{{id leader_name nation_name alliance_id score num_cities soldiers tanks aircraft ships missiles nukes alliance{{name}}alliance_position}}defender{{ id leader_name nation_name alliance_id score num_cities soldiers tanks aircraft ships missiles nukes alliance{{name}}alliance_position}}}}}}}}"}) as r:
                json_obj = await r.json()
                wars = json_obj["data"]["wars"]["data"]
                if len(wars) > 0:
                    for war in wars:
                        attacker = war["attacker"]
                        defender = war["defender"]
                        if defender["alliance_id"] == '913':
                            dcolor = 15158332
                        else:
                            dcolor = 3066993
                        try:
                            a_alliance = attacker["alliance"]["name"]
                        except:
                            a_alliance = 'None'
                        try:
                            d_alliance = defender["alliance"]["name"]
                        except:
                            d_alliance = 'None'
                        embed = discord.Embed(title=f'''{a_alliance} {attacker["alliance_position"]} on {d_alliance} {defender["alliance_position"]}''', description=f'''
[{attacker["nation_name"]}](https://politicsandwar.com/nation/id={attacker["id"]}) declared a(n) {war['war_type']} war on [{defender["nation_name"]}](https://politicsandwar.com/nation/id={defender["id"]})
Reason: `{war["reason"]}`
                    
Score: `{attacker['score']}` on `{defender['score']}`
Cities: `{attacker["num_cities"]}` on `{defender["num_cities"]}`
Attacker Military
`💂 {attacker["soldiers"]} | ⚙️ {attacker["tanks"]} | ✈️ {attacker["aircraft"]} | 🚢 {attacker["ships"]}\n🚀 {attacker["missiles"]} | ☢️ {attacker["nukes"]}`
Defender Military
`💂 {defender["soldiers"]} | ⚙️ {defender["tanks"]} | ✈️ {defender["aircraft"]} | 🚢 {defender["ships"]}\n🚀 {defender["missiles"]} | ☢️ {defender["nukes"]}`
[Go to war page](https://politicsandwar.com/nation/war/timeline/war={war["id"]})
Find counters: `;counter {attacker["id"]}`
[Counters with slotter](https://slotter.bsnk.dev/search?nation={attacker["id"]}&alliances=913&countersMode=true&threatsMode=false&vm=false&grey=true&beige=true)
                        ''', color=dcolor)
                        await channel.send(embed=embed)
                        if defender["alliance_id"] == '913' and type(db.discord_users.find_one({'nation_id':int(defender["id"])})) is dict:
                            account = db.discord_users.find_one({'nation_id':int(defender["id"])})
                            await channel.send(f"You have been attacked <@{account['_id']}>")
                        last_war = int(war["id"]) + 1
                        db.misc.update_one({'_id':True}, {"$set": {'last_arrgh_war':last_war}})



@tasks.loop(minutes=15)
async def member_updates():
    channel = client.get_channel(220580210251137024) #channel where alerts are sent
    role = 576711897328386069 #role that gets pinged
    async with aiohttp.ClientSession() as session:
        async with session.get(f'https://politicsandwar.com/api/alliance-members/?allianceid=913&key={api_key}') as r:
            json_obj = await r.json()
            captains = json_obj["nations"]
            new_id_list = []
            old_id_list = []
            for captain in captains:
                captain["_id"] = captain.pop("nationid")
                new_id_list.append(captain["_id"])
            old_captains = db.captains.find({})
            for old_captain in old_captains:
                old_id_list.append(old_captain["_id"])
            changes = [i for i in old_id_list if i not in new_id_list]  #[members left]
            if len(changes) > 0:
                await channel.send(f'<@&{role}> Following nations have left Arrgh.')
                for x in changes:
                    await channel.send(f'https://politicsandwar.com/nation/id={x}')
            db.captains.delete_many({})
            db.captains.insert_many(captains)


def get_raid_value(attack):
    loot_info = attack["loot_info"]
    loot_note = loot_info.split("looted",1)[1]
    string_list = re.findall('[0-9]+', loot_note.replace(',', ''))
    x = [int(i) for i in string_list]
    basic_loot_value = x[0] + (x[1]*2000) + (x[2]*2000) + (x[3]*2400) + (x[4]*2000) + (x[5]*2500) + (x[6]*2700) + (x[7]*3000) + (x[8]*1800) + (x[9]*3400) + (x[10]*2700) + (x[11]*130)
    war_type_modifier = {'RAID': 1, 'ORDINARY': 2, 'ATTRITION':4}
    loot_value = lambda basic_loot_value: basic_loot_value*war_type_modifier[attack["war"]["war_type"]]
    beige_unix = iso_to_unix(attack["date"])
    return {'loot_value': int(loot_value(basic_loot_value)), 'beige_unix': beige_unix}


def iso_to_unix(iso_string):
    date_time = datetime.datetime.fromisoformat(iso_string)
    return calendar.timegm(date_time.utctimetuple())


def get_alliance_loot_value(loot_note):
    alliance_name = re.findall(r"(?<=% of )(.*)(?='s )", loot_note)
    string_list = re.findall(r'[\d]+', (loot_note.split("taking",1)[1]).replace(',', '')) 
    x = [int(i) for i in string_list]
    loot_value = x[0] + (x[1]*2000) + (x[2]*2000) + (x[3]*2400) + (x[4]*2000) + (x[5]*2500) + (x[6]*2700) + (x[7]*3000) + (x[8]*1800) + (x[9]*3400) + (x[10]*2700) + (x[11]*130)
    return (alliance_name[0], int(loot_value))



@tasks.loop(minutes = 10)
async def menu_v3():
    channel = client.get_channel(858725272279187467) #menu channel
    misc = db.misc.find_one({'_id':True})
    async with aiohttp.ClientSession() as session:
        async with session.post(graphql, json={'query':f"{{warattacks(orderBy:{{column:ID, order:DESC}}, min_id:{misc['last_menu_id']}){{data{{id date type loot_info war{{id war_type}}defender{{id nation_name leader_name score num_cities beige_turns vacation_mode_turns last_active alliance_id soldiers tanks aircraft ships}}}}}}}}"}) as r:
            json_obj = await r.json()
            attacks = json_obj["data"]["warattacks"]["data"]
            for attack in attacks:
                if attack["type"] == "VICTORY":
                    raid = get_raid_value(attack)
                    if raid['loot_value'] > 20000000:
                        defender = attack["defender"]
                        embed = discord.Embed(title=f"{defender['nation_name']}", url=f'https://politicsandwar.com/nation/id={defender["id"]}', description=f'''
Estimated Loot : **{"${:,.2f}".format(raid["loot_value"])}**
Beiged : <t:{raid["beige_unix"]}:R>
Last Active : <t:{iso_to_unix(defender["last_active"])}:R>
Military : `💂 {defender["soldiers"]} | ⚙️ {defender["tanks"]} | ✈️ {defender["aircraft"]} | 🚢 {defender["ships"]}`
Defensive Range : `{round((float(defender['score']) / 1.75),2)} to {round((float(defender['score']) / 0.75),2)}`
VM/Beige : `VM: {defender["vacation_mode_turns"]} turns | Beige: {defender["beige_turns"]} turns. (<t:{(raid["beige_unix"])+(defender["beige_turns"]*7200)}:R>)`
[War Link](https://politicsandwar.com/nation/war/timeline/war={attack["war"]["id"]})
[Nation's war page](https://politicsandwar.com/nation/id={defender["id"]}&display=war)
                                            ''')
                        await channel.send(embed=embed)

                if attack["type"] == "ALLIANCELOOT":
                    alliance = get_alliance_loot_value(attack)
                    if alliance["loot_value"] > 20000000:
                        embed = discord.Embed(title='Alliance loot', description=f'''
`{alliance[0]}`'s bank was looted for:
{"${:,.2f}".format(alliance[1])}
[Visit war page.]([War Link](https://politicsandwar.com/nation/war/timeline/war={attack["war"]["id"]}))                        
                        ''')
                        await channel.send(embed=embed)
            last_menu_id = attacks[0]["id"] + 1
            db.misc.update_one({'_id':True}, {"$set": {'last_menu_id':last_menu_id}})






client.run(token)


