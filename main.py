############ boilerplate ################
from tinydb import TinyDB
import discord
import aiohttp
import re
import pandas as pd
import humanize
from datetime import datetime, timezone, timedelta
import os
from discord.ext import commands, tasks
from pymongo import MongoClient
import zipfile
import csv
from pathlib import Path
from itertools import combinations_with_replacement
from collections import Counter
import asyncio
import calendar
import pnwkit





token = os.environ['TOKEN']
api_key = os.environ['API_KEY']
doom_api_key = os.environ['DOOM_API_KEY']
db_client = MongoClient(os.environ['DB_ACCESS_URL'])


kit = pnwkit.QueryKit(api_key)
tinydb = TinyDB('tinydb.json')
tiny_nations = tinydb.table('nations')
tiny_alliances = tinydb.table('alliances')
db = db_client.get_database('jack_rackham_db')
graphql = f"https://api.politicsandwar.com/graphql?api_key={api_key}"
beige_alerts_graphql = f"https://api.politicsandwar.com/graphql?api_key={doom_api_key}"


intents = discord.Intents.all()
client = commands.Bot(intents = intents)


############## Intiailization ################

@client.event
async def on_ready():
    game = discord.Game("it cool.")
    await client.change_presence(status=discord.Status.online, activity=game)
    if not tinydb_update.is_running():
         tinydb_update.start()
    if not captains_update.is_running():
         captains_update.start()
    if not menu.is_running():
        menu.start()
    client.loop.create_task(recruitment())
    client.loop.create_task(off_war_alert())
    client.loop.create_task(def_war_alert())
    if not big_bank_scanner.is_running():
        big_bank_scanner.start()
    if not alerts.is_running():
        alerts.start()
    print('Online as {0.user}'.format(client))




@client.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Command is missing one or more required arguments.')
    elif isinstance(error, TypeError):
        await ctx.send('Wrong argument type, try again.')
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send('This command cannot be used in DMs.')
    elif isinstance(error, commands.PrivateMessageOnly):
        await ctx.send('This command can only be used in DMs.')
    elif isinstance(error, commands.MissingRole):
        await ctx.send('You do not have permission to use this command.')
    elif isinstance(error, commands.NotOwner):
        await ctx.send('Go away creep! You are not sam (˶˃⤙˂˶)')



######################### for later use ############################



alerts_cache = {}
async def targets_autocomplete(ctx: discord.AutocompleteContext):
    user_id = ctx.interaction.user.id
    search_term = ctx.value.lower()
    if user_id not in alerts_cache:
        all_targets = list(db.beige_alerts.find({}))
        user_targets = [target for target in all_targets if user_id in target['subscribed_captains']]
        alerts_cache[user_id] = [f"{target['_id']} - {target['name']}" for target in user_targets]
    targets = alerts_cache[user_id]
    if not targets:
        return ["No active alerts"]
    filtered_targets = [target for target in targets if search_term in target.lower()]
    return filtered_targets[:25]



def get_raid_value(attack):
    loot_info = attack["loot_info"]
    loot_note = loot_info.split("looted",1)[1]
    string_list = re.findall('[0-9]+', loot_note.replace(',', ''))
    x = [int(i) for i in string_list]
    basic_loot_value = x[0] + (x[1]*3500) + (x[2]*3500) + (x[3]*3000) + (x[4]*4200) + (x[5]*3500) + (x[6]*3500) + (x[7]*3200) + (x[8]*2000) + (x[9]*4400) + (x[10]*2700) + (x[11]*130)
    if attack["war"]["war_type"] == 'ATTRITION' and attack["defender"]["id"] == attack["war"]["att_id"]:
        attack["war"]["war_type"] = 'ORDINARY'
    war_type_modifier = {'RAID': 1, 'ORDINARY': 2, 'ATTRITION':4}
    loot_value = lambda basic_loot_value: basic_loot_value*war_type_modifier[attack["war"]["war_type"]]
    beige_unix = iso_to_unix(attack["date"])
    return {'loot_value': int(loot_value(basic_loot_value)), 'beige_unix': beige_unix}


def iso_to_unix(iso_string):
    date_time = datetime.fromisoformat(iso_string)
    return calendar.timegm(date_time.utctimetuple())


def get_alliance_loot_value(loot_note):
    alliance_name = re.findall(r"(?<=% of )(.*)(?='s )", loot_note)
    string_list = re.findall(r'[\d]+', (loot_note.split("taking",1)[1]).replace(',', '')) 
    x = [int(i) for i in string_list]
    loot_value = x[0] + (x[1]*3500) + (x[2]*3500) + (x[3]*3000) + (x[4]*3500) + (x[5]*3500) + (x[6]*4200) + (x[7]*3200) + (x[8]*2000) + (x[9]*4400) + (x[10]*2700) + (x[11]*130)
    return (alliance_name[0], int(loot_value))



def utc_from_tz(offset):
    target_time_utc = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=-offset)
    timestamp = int(target_time_utc.timestamp())
    return timestamp



continents = {'na': 'North America',
              'sa':'South America',
              'as': 'Asia',
              'an': 'Antarctica',
              'eu': 'Europe',
              'af': 'Africa',
              'au': 'Australia'}


bool_dict = {True: "🟢", False: "🔴"}



async def nations_autocomplete(ctx: discord.AutocompleteContext):
    search_term = ctx.value.lower()
    nations = [f"{nation['nation_id']} - {nation['leader_name']} of {nation['nation_name']}" 
            for nation in tiny_nations.all() 
            if search_term in f"{nation['nation_id']} {nation['leader_name']} {nation['nation_name']}".lower()]
    return nations[:25]



async def alliances_autocomplete(ctx: discord.AutocompleteContext):
    search_term = ctx.value.lower()
    alliances = [
        f"{alliance['alliance_id']} - {alliance['name']} ({alliance['acronym']})"
        for alliance in tiny_alliances.all()
        if search_term in f"{alliance['alliance_id']} {alliance['name']} {alliance['acronym']}".lower()
    ]
    return alliances[:10]


async def resources_autocomplete(ctx: discord.AutocompleteContext):
    resources = ["FOOD", "COAL", "OIL", "URANIUM", "LEAD", "IRON", "BAUXITE", "GASOLINE", "MUNITIONS", "STEEL", "ALUMINUM", "CREDIT"]
    return [resource for resource in resources if ctx.value.lower() in resource.lower()]


attacks = {
    "Ground": {"cost": 3, "damage": 10},
    "Airstrike": {"cost": 4, "damage": 12},
    "Naval": {"cost": 4, "damage": 14},
    "Missiles": {"cost": 8, "damage": 18},
    "Nukes": {"cost": 12, "damage": 25},
}

def calculate_combination_stats(combination):
    total_cost = sum([attacks[a]["cost"] for a in combination])
    total_damage = sum([attacks[a]["damage"] for a in combination])
    return {"combination": combination, "total_cost": total_cost, "total_damage": total_damage}

def efficient_combinations(resistance):
    attack_types = list(attacks.keys())
    max_length = resistance // min([attacks[a]["damage"] for a in attack_types]) + 1
    combinations = [comb for i in range(1, max_length + 1) 
                    for comb in combinations_with_replacement(attack_types, i)]
    valid_combinations = [comb for comb in combinations 
                          if sum([attacks[a]["damage"] for a in comb]) >= resistance]
    valid_combinations_stats = [calculate_combination_stats(comb) for comb in valid_combinations]
    sorted_combinations = sorted(valid_combinations_stats, 
                                 key=lambda comb_stats: (comb_stats["total_cost"], -comb_stats["total_damage"]))[:5]
    counts = [dict(Counter(comb_stats["combination"])) for comb_stats in sorted_combinations]
    return list(zip(counts, sorted_combinations))


######################## loops and tasks ############################



@tasks.loop(minutes=4)
async def tinydb_update():
    now = datetime.now(timezone.utc)
    if now.hour == 0 and now.minute < 10:
        tiny_alliances.truncate()
        tiny_nations.truncate()
        types = ['nations', 'alliances']
        yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')
        csv_dir = Path('csv')
        for type in types:
            url = f"https://politicsandwar.com/data/{type}/{type}-{yesterday}.csv.zip"
            zip_filename = f"{type}-{yesterday}.csv.zip"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        with open(csv_dir / zip_filename, 'wb') as f:
                            f.write(await response.read())
                        with zipfile.ZipFile(csv_dir / zip_filename, 'r') as zip_ref:
                            zip_ref.extractall(csv_dir)
                        df = pd.read_csv(csv_dir / f"{type}-{yesterday}.csv")
                        tinydb.table(type).insert_multiple(df.to_dict(orient='records'))
        for filename in os.listdir(csv_dir):
            file_path = os.path.join(csv_dir, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)




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
    channel = client.get_channel(312420656312614912)
    subscription = await kit.subscribe("nation", "create")
    async with aiohttp.ClientSession() as session:
        async for nation in subscription:
            await asyncio.sleep(0.2)
            data = {'key': api_key, 'to': f'{nation.id}', 'subject': 'Have you considered piracy?', 'message': message}
            async with session.post("https://politicsandwar.com/api/send-message", data = data) as r:
                if r.status == 200:
                    await channel.send(f'Sent message to {nation.leader_name} of {nation.nation_name} ({nation.id})')
                else:
                    await channel.send(f'Could not send message to {nation.leader_name} of {nation.nation_name} ({nation.id})')




async def off_war_alert():
    channel = client.get_channel(514689777778294785)
    subscription = await kit.subscribe("war","create", filters={"att_alliance_id": [913]})
    async with aiohttp.ClientSession() as session:
        async for war in subscription:
            await asyncio.sleep(0.2)
            async with session.post(graphql, json={'query':f'''{{nations(id:{[war["att_id"],war["def_id"]]}){{data{{
      id nation_name leader_name alliance_id
      alliance{{name}}
      alliance_position offensive_wars_count
      defensive_wars_count war_policy num_cities score espionage_available soldiers tanks aircraft ships nukes missiles
      spies missile_launch_pad nuclear_research_facility nuclear_launch_facility iron_dome vital_defense_system
      space_program spy_satellite pirate_economy advanced_pirate_economy
    }}
  }}
}}'''}) as r:
                    json_obj = await r.json()
                    if json_obj["data"]["nations"]["data"]:
                        nations = json_obj["data"]["nations"]["data"]
                        for nation in nations:
                            if nation["id"] == str(war["att_id"]):
                                attacker = nation
                            elif nation["id"] == str(war["def_id"]):
                                defender = nation
                        try:
                            a_alliance = attacker["alliance"]["name"]
                        except:
                            a_alliance = 'None'
                        try:
                            d_alliance = defender["alliance"]["name"]
                        except:
                            d_alliance = 'None'
                        embed = discord.Embed(title=f'{a_alliance} {attacker["alliance_position"]} on {d_alliance} {defender["alliance_position"]}',
                                              url=f'https://politicsandwar.com/nation/war/timeline/war={war["id"]}', description=f'''
[{attacker["nation_name"]}](https://politicsandwar.com/nation/id={attacker["id"]}) declared a(n) {str(war["war_type"]).split(".")[1].capitalize()} war on [{defender["nation_name"]}](https://politicsandwar.com/nation/id={defender["id"]})
Reason: `{war["reason"]}`

Score: `{attacker['score']}` on `{defender['score']}`
Cities: `{attacker["num_cities"]}` on `{defender["num_cities"]}`
War Policy: `{attacker["war_policy"]}` on `{defender["war_policy"]}`
Wars: `⬆️ {attacker["offensive_wars_count"]} | ⬇️ {attacker["defensive_wars_count"]}` on `⬆️ {defender["offensive_wars_count"]} | ⬇️ {defender["defensive_wars_count"]}`

**Attacker**
Military
`💂 {attacker["soldiers"]} | ⚙️ {attacker["tanks"]} | ✈️ {attacker["aircraft"]} | 🚢 {attacker["ships"]}\n🚀 {attacker["missiles"]} | ☢️ {attacker["nukes"]} | 🕵️ {attacker["spies"]}`
`Can be spied? : {bool_dict[attacker["espionage_available"]]}`
Projects
`Missiles: {bool_dict[attacker["missile_launch_pad"]]}{bool_dict[attacker["missile_launch_pad"]]}{bool_dict[attacker["space_program"]]} | Nukes: {bool_dict[attacker["nuclear_research_facility"]]}{bool_dict[attacker["nuclear_launch_facility"]]}`
`Spy Sat: {bool_dict[attacker["spy_satellite"]]} | ID: {bool_dict[attacker["iron_dome"]]} | VDS: {bool_dict[attacker["vital_defense_system"]]}`
`Pirate Eco: {bool_dict[attacker["pirate_economy"]]} | Adv. Pirate Eco: {bool_dict[attacker["advanced_pirate_economy"]]}`

**Defender**
Military
`💂 {defender["soldiers"]} | ⚙️ {defender["tanks"]} | ✈️ {defender["aircraft"]} | 🚢 {defender["ships"]}\n🚀 {defender["missiles"]} | ☢️ {defender["nukes"]} | 🕵️ {attacker["spies"]}`
`Can be spied? : {bool_dict[defender["espionage_available"]]}`
Projects
`Missiles: {bool_dict[defender["missile_launch_pad"]]}{bool_dict[defender["missile_launch_pad"]]}{bool_dict[defender["space_program"]]} | Nukes: {bool_dict[defender["nuclear_research_facility"]]}{bool_dict[defender["nuclear_launch_facility"]]}`
`Spy Sat: {bool_dict[defender["spy_satellite"]]} | ID: {bool_dict[defender["iron_dome"]]} | VDS: {bool_dict[defender["vital_defense_system"]]}`
`Pirate Eco: {bool_dict[defender["pirate_economy"]]} | Adv. Pirate Eco: {bool_dict[defender["advanced_pirate_economy"]]}`
                                              ''', color=3066993)
                        await channel.send(embed=embed)


async def def_war_alert():
    channel = client.get_channel(514689777778294785)
    subscription = await kit.subscribe("war","create", filters={"def_alliance_id": [913]})
    async with aiohttp.ClientSession() as session:
        async for war in subscription:
            await asyncio.sleep(0.2)
            async with session.post(graphql, json={'query':f'''{{nations(id:{[war["att_id"],war["def_id"]]}){{data{{
      id nation_name leader_name alliance_id
      alliance{{name}}
      alliance_position offensive_wars_count
      defensive_wars_count war_policy num_cities score espionage_available soldiers tanks aircraft ships nukes missiles
      spies missile_launch_pad nuclear_research_facility nuclear_launch_facility iron_dome vital_defense_system
      space_program spy_satellite pirate_economy advanced_pirate_economy
    }}
  }}
}}'''}) as r:
                    json_obj = await r.json()
                    if json_obj["data"]["nations"]["data"]:
                        nations = json_obj["data"]["nations"]["data"]
                        for nation in nations:
                            if nation["id"] == str(war["att_id"]):
                                attacker = nation
                            elif nation["id"] == str(war["def_id"]):
                                defender = nation
                        try:
                            a_alliance = attacker["alliance"]["name"]
                        except:
                            a_alliance = 'None'
                        try:
                            d_alliance = defender["alliance"]["name"]
                        except:
                            d_alliance = 'None'
                        embed = discord.Embed(title=f'{a_alliance} {attacker["alliance_position"]} on {d_alliance} {defender["alliance_position"]}',
                                              url=f'https://politicsandwar.com/nation/war/timeline/war={war["id"]}', description=f'''
[{attacker["nation_name"]}](https://politicsandwar.com/nation/id={attacker["id"]}) declared a(n) {str(war["war_type"]).split(".")[1].capitalize()} war on [{defender["nation_name"]}](https://politicsandwar.com/nation/id={defender["id"]})
Reason: `{war["reason"]}`

Score: `{attacker['score']}` on `{defender['score']}`
Cities: `{attacker["num_cities"]}` on `{defender["num_cities"]}`
War Policy: `{attacker["war_policy"]}` on `{defender["war_policy"]}`
Wars: `⬆️ {attacker["offensive_wars_count"]} | ⬇️ {attacker["defensive_wars_count"]}` on `⬆️ {defender["offensive_wars_count"]} | ⬇️ {defender["defensive_wars_count"]}`

**Attacker**
Military
`💂 {attacker["soldiers"]} | ⚙️ {attacker["tanks"]} | ✈️ {attacker["aircraft"]} | 🚢 {attacker["ships"]}\n🚀 {attacker["missiles"]} | ☢️ {attacker["nukes"]} | 🕵️ {attacker["spies"]}`
`Can be spied? : {bool_dict[attacker["espionage_available"]]}`
Projects
`Missiles: {bool_dict[attacker["missile_launch_pad"]]}{bool_dict[attacker["missile_launch_pad"]]}{bool_dict[attacker["space_program"]]} | Nukes: {bool_dict[attacker["nuclear_research_facility"]]}{bool_dict[attacker["nuclear_launch_facility"]]}`
`Spy Sat: {bool_dict[attacker["spy_satellite"]]} | ID: {bool_dict[attacker["iron_dome"]]} | VDS: {bool_dict[attacker["vital_defense_system"]]}`
`Pirate Eco: {bool_dict[attacker["pirate_economy"]]} | Adv. Pirate Eco: {bool_dict[attacker["advanced_pirate_economy"]]}`

**Defender**
Military
`💂 {defender["soldiers"]} | ⚙️ {defender["tanks"]} | ✈️ {defender["aircraft"]} | 🚢 {defender["ships"]}\n🚀 {defender["missiles"]} | ☢️ {defender["nukes"]} | 🕵️ {attacker["spies"]}`
`Can be spied? : {bool_dict[defender["espionage_available"]]}`
Projects
`Missiles: {bool_dict[defender["missile_launch_pad"]]}{bool_dict[defender["missile_launch_pad"]]}{bool_dict[defender["space_program"]]} | Nukes: {bool_dict[defender["nuclear_research_facility"]]}{bool_dict[defender["nuclear_launch_facility"]]}`
`Spy Sat: {bool_dict[defender["spy_satellite"]]} | ID: {bool_dict[defender["iron_dome"]]} | VDS: {bool_dict[defender["vital_defense_system"]]}`
`Pirate Eco: {bool_dict[defender["pirate_economy"]]} | Adv. Pirate Eco: {bool_dict[defender["advanced_pirate_economy"]]}`
                                              ''', color=15158332)
                        await channel.send(embed=embed)
                        if type(db.discord_users.find_one({'nation_id':int(defender["id"])})) is dict:
                            account = db.discord_users.find_one({'nation_id':int(defender["id"])})
                            await channel.send(f"You have been attacked <@{account['_id']}>")



@tasks.loop(minutes=30)
async def captains_update():
    crew_channel = client.get_channel(1255666123509071932)
    admiralty_channel = client.get_channel(220580210251137024)
    async with aiohttp.ClientSession() as session:
        async with session.post(graphql, json={'query': f'''
{{
  nations(alliance_id:913, first:250){{
    data{{
      id nation_name leader_name discord_id alliance_position num_cities score domestic_policy color update_tz vacation_mode_turns
      beige_turns last_active offensive_wars_count defensive_wars_count war_policy soldiers tanks aircraft ships nukes missiles
      spies missile_launch_pad nuclear_research_facility nuclear_launch_facility central_intelligence_agency
      propaganda_bureau space_program spy_satellite pirate_economy advanced_pirate_economy}}}}}}'''}) as r:
            json_obj = await r.json()
            idnations = json_obj['data']['nations']['data']
            nations = [{**{k: v for k, v in item.items() if k != "id"}, "_id": int(item["id"])} for item in idnations]
            
            captains = [nation for nation in nations if nation['alliance_position'] != 'APPLICANT']
            captains_ids = [captain["_id"] for captain in captains]
            existing_captains = db.captains.find({})
            existing_captains_ids = [captain["_id"] for captain in existing_captains]
            
            applicants = [nation for nation in nations if nation['alliance_position'] == 'APPLICANT']
            applicants_ids = [applicant["_id"] for applicant in applicants]
            existing_applicants = db.applicants.find({})
            existing_applicants_ids = [applicant["_id"] for applicant in existing_applicants]


            for old_captain in existing_captains:
                if old_captain["_id"] not in captains_ids:
                    await admiralty_channel.send(f"Captain {old_captain['leader_name']} of [{old_captain['nation_name']}](https://politicsandwar.com/nation/id={old_captain['_id']}) ({old_captain['_id']}) has left the alliance.")
            
            for old_applicant in existing_applicants:
                if old_applicant['_id'] not in applicants_ids:
                    if old_applicant['_id'] not in captains_ids:
                        await admiralty_channel.send(f"Applicant {old_applicant['leader_name']} of [{old_applicant['nation_name']}](https://politicsandwar.com/nation/id={old_applicant['_id']}) ({old_applicant['_id']}) has revoked their application.")
            
            for applicant in applicants:
                if applicant['_id'] not in existing_applicants_ids:
                    if applicant['_id'] not in existing_captains_ids:
                        await admiralty_channel.send(f"{applicant['leader_name']} of [{applicant['nation_name']}](https://politicsandwar.com/nation/id={applicant['_id']}) ({applicant['_id']}) has applied to join the alliance.")
            
            await crew_channel.purge()
            sorted_captains = sorted(captains, key=lambda captain: captain['score'], reverse=True)
            for captain in sorted_captains:
                if captain["vacation_mode_turns"] > 0:
                    dcolor = 15158332
                else:
                    dcolor = 1146986
                discord_user = db.discord_users.find_one({"nation_id": captain["_id"]})
                if discord_user:
                    discord_id = client.get_user(discord_user["_id"]).display_name
                else:
                    discord_id = "No ID in DB"
                embed = discord.Embed(title=f'{captain["leader_name"]} of {captain["nation_name"]}', url=f'https://politicsandwar.com/nation/id={captain["_id"]}', description=f'''
`ID: {captain["_id"]} | Score: {captain["score"]} | 🏙️ {captain["num_cities"]}`
`Active: {humanize.naturaltime(datetime.fromisoformat(captain["last_active"]))} | {captain["war_policy"].capitalize()}`
`{(captain["domestic_policy"].replace('_', ' ')).capitalize()} | {captain["color"].capitalize()} | Beige: {captain["beige_turns"]} turns`
`VM: {captain["vacation_mode_turns"]} turns | Discord : {discord_id}`

Off range: `{round((captain["score"] * 0.75),2)} to {round((captain["score"] * 2.5),2)}`
Def range: `{round((captain["score"] / 2.5),2)} to {round((captain["score"] / 0.75),2)}`
Spy range: `{round((captain["score"] / 2.5),2)} to {round((captain["score"] * 2.5),2)}`
Reset : <t:{utc_from_tz(captain["update_tz"])}:t>
Wars : `⬆️ {captain["offensive_wars_count"]} | ⬇️ {captain["defensive_wars_count"]}`

`💂 {captain["soldiers"]} | ⚙️ {captain["tanks"]} | ✈️ {captain["aircraft"]} | 🚢 {captain["ships"]}\n🚀 {captain["missiles"]} | ☢️ {captain["nukes"]} | 🕵️ {captain["spies"]}`

`Missiles: {bool_dict[captain["missile_launch_pad"]]}{bool_dict[captain["missile_launch_pad"]]}{bool_dict[captain["space_program"]]} | Nukes: {bool_dict[captain["nuclear_research_facility"]]}{bool_dict[captain["nuclear_launch_facility"]]}`
`IA: {bool_dict[captain["central_intelligence_agency"]]} | PB: {bool_dict[captain["propaganda_bureau"]]} | Spy Sat: {bool_dict[captain["spy_satellite"]]}`
`Pirate Eco: {bool_dict[captain["pirate_economy"]]} | Adv. Pirate Eco: {bool_dict[captain["advanced_pirate_economy"]]}`
                                    ''', color=dcolor)
                await crew_channel.send(embed=embed)
                                      


            db.captains.delete_many({})
            db.captains.insert_many(captains)
            db.applicants.delete_many({})
            db.applicants.insert_many(applicants)



@tasks.loop(minutes = 15)
async def menu():
    channel = client.get_channel(858725272279187467) #menu channel
    misc = db.misc.find_one({'_id':True})
    async with aiohttp.ClientSession() as session:
        async with session.post(graphql, json={'query':f"{{warattacks(orderBy:{{column:ID, order:DESC}}, min_id:{misc['last_menu_id']}, first:500){{data{{id date type loot_info war{{id war_type att_id def_id}}defender{{id nation_name leader_name score num_cities beige_turns vacation_mode_turns last_active alliance_id soldiers tanks aircraft ships}}}}}}}}"}) as r:
            json_obj = await r.json()
            attacks = json_obj["data"]["warattacks"]["data"]
            for attack in attacks:
                if attack["type"] == "VICTORY":
                    raid = get_raid_value(attack)
                    if raid['loot_value'] > 35000000:
                        defender = attack["defender"]
                        embed = discord.Embed(title=f"{defender['nation_name']}", url=f'https://politicsandwar.com/nation/id={defender["id"]}', description=f'''
Estimated Loot : **{"${:,.2f}".format(raid["loot_value"])}**
Beiged : <t:{raid["beige_unix"]}:R>
Last Active : <t:{iso_to_unix(defender["last_active"])}:R>
City Count : {defender["num_cities"]}
Military : `💂 {defender["soldiers"]} | ⚙️ {defender["tanks"]} | ✈️ {defender["aircraft"]} | 🚢 {defender["ships"]}`
Defensive Range : `{round((float(defender['score']) / 2.75),2)} to {round((float(defender['score']) / 0.75),2)}`
VM/Beige : `VM: {defender["vacation_mode_turns"]} turns | Beige: {defender["beige_turns"]} turns.` out of beige <t:{(raid["beige_unix"])+(defender["beige_turns"]*7200)}:R>
[War Link.](https://politicsandwar.com/nation/war/timeline/war={attack["war"]["id"]})
[Nation's war page.](https://politicsandwar.com/nation/id={defender["id"]}&display=war)
Set beige alert with : `/beige_alert add`
                                            ''')
                        await channel.send(embed=embed)

                if attack["type"] == "ALLIANCELOOT":
                    alliance = get_alliance_loot_value(attack["loot_info"])
                    if alliance[1] > 30000000:
                        embed = discord.Embed(title='Alliance loot', description=f'''
`{alliance[0]}`'s bank was looted for:
**{"${:,.2f}".format(alliance[1])}**
[Visit war page.](https://politicsandwar.com/nation/war/timeline/war={attack["war"]["id"]})
                        ''')
                        await channel.send(embed=embed)
            last_menu_id = int(attacks[0]["id"])+1
            db.misc.update_one({'_id':True}, {"$set": {'last_menu_id':last_menu_id}})



@tasks.loop(minutes = 2)
async def big_bank_scanner():
    channel = client.get_channel(858725272279187467) #menu channel
    misc = db.misc.find_one({'_id':True})
    async with aiohttp.ClientSession() as session:
        async with session.post(graphql, json={'query':f"{{bankrecs(orderBy:{{column:ID, order:DESC}}, first:30, stype:2, min_id:{misc['last_big_tx']}){{data{{id date note money coal oil uranium iron bauxite lead gasoline munitions steel aluminum food receiver_id receiver{{nation_name last_active score num_cities soldiers tanks aircraft ships}}}}}}}}"}) as r:
            json_obj = await r.json()
            transactions = json_obj['data']['bankrecs']['data']
            if len(transactions) > 0:
                for transaction in transactions:
                    withdrawal_value = transaction['money'] + (transaction['coal']*3500) + (transaction['oil']*3500) + (transaction['uranium']*3200) + (transaction['iron']*3500) + (transaction['bauxite']*3700) + (transaction['lead']*4200) + (transaction['gasoline']*3800) + (transaction['munitions']*2000) + (transaction['steel']*4200) + (transaction['aluminum']*2700) + (transaction['food']*130)
                    if withdrawal_value > 500000000 and "defeated" not in transaction["note"]:
                        embed = discord.Embed(title=f"Bank transaction", description=f'''
[{transaction["receiver"]["nation_name"]}](https://politicsandwar.com/nation/id={transaction["receiver_id"]}) received a withdrawal <t:{iso_to_unix(transaction["date"])}:R> of value:
**{"${:,.2f}".format(withdrawal_value)}**
Note : {transaction["note"]}
Last active <t:{iso_to_unix(transaction["receiver"]["last_active"])}:R>
City count: {transaction['receiver']['num_cities']}
Defensive Range : `{round((float(transaction['receiver']['score']) / 2.75),2)} to {round((float(transaction['receiver']['score']) / 0.75),2)}`
Military : `💂 {transaction['receiver']["soldiers"]} | ⚙️ {transaction['receiver']["tanks"]} | ✈️ {transaction['receiver']["aircraft"]} | 🚢 {transaction['receiver']["ships"]}`
[Visit bank page.](https://politicsandwar.com/nation/id={transaction["receiver_id"]}&display=bank)
''')
                        await channel.send(embed=embed)
                last_big_tx = int(transactions[0]['id']) + 1
                db.misc.update_one({'_id':True}, {"$set": {'last_big_tx':last_big_tx}})




@tasks.loop(seconds=30)
async def alerts():
    misc = db.misc.find_one({'_id':True})
    targets = list(misc['beige_alert_targets'])
    if len(targets) > 0:
        async with aiohttp.ClientSession() as session:
            async with session.post(beige_alerts_graphql, json={'query':f'''
{{
  nations(id:{targets}, first:200, color:[
    "Black","Aqua","Blue",
    "Brown","Green","Lime",
    "Maroon","Olive","Orange",
    "Pink","Purple","Red",
    "White","Yellow"]){{
    data{{
      id
      nation_name
    }}
  }}
}}'''}) as r:
                json_obj = await r.json()
                nations = json_obj["data"]["nations"]["data"]
                if nations:
                    for nation in nations:
                        target = db.beige_alerts.find_one({'_id':int(nation['id'])})
                        if target:
                            subscribed_captains = target['subscribed_captains']
                            for captain in subscribed_captains:
                                user = client.get_user(captain)
                                await user.send(f'''[{nation['nation_name']}](https://politicsandwar.com/nation/id={nation['id']}) has left beige! 
[Click here to go directly to war page](https://politicsandwar.com/nation/war/declare/id={nation['id']})''')
                            db.beige_alerts.delete_one(target)
                        targets.remove(int(nation['id']))
                        db.misc.update_one(
                        {'_id': True}, 
                        {"$set": {'beige_alert_targets':targets}}
                        )
                        



####################### commands ############################


@client.command()
@commands.is_owner()
async def ping(ctx):
    await ctx.send(f'Pong! {round(client.latency*1000)}ms')



@client.slash_command(description="Register your nation with jack, Admiralty can register any nation.")
async def register(ctx, nation_id:int, user:discord.User=None, admin:bool=False):
    await ctx.defer()
    if admin == False and user == None:
        if db.discord_users.find_one({'_id':ctx.author.id}):
            await ctx.respond('You\'re already registered.')
        elif db.discord_users.find_one({'nation_id':nation_id}):
            await ctx.respond('This nation is already registered.')
        else:
            async with aiohttp.ClientSession() as session:
                async with session.post(graphql, json={'query':f'''
                                                       {{
                                                           nations(id:{nation_id}){{
                                                           data{{
                                                            discord
                                                            discord_id
                                                                }}
                                                                    }}
                                                       }}'''
                                                       }) as r:
                    json_obj = await r.json()
                    nation = json_obj["data"]["nations"]["data"]
                    if len(nation) > 0:
                        username = nation[0]["discord"]
                        if username == str(ctx.author.name):
                            db.discord_users.insert_one({'_id':ctx.author.id, 'nation_id':nation_id})
                            await ctx.respond('Registration successful! you\'ve been verified.')
                            await ctx.author.add_roles(discord.utils.get(ctx.author.guild.roles, name='Jack Approves! ✅'))
                        else:
                            await ctx.respond(f'Verification failed, your username does not match with in-game username. {ctx.author.name} != {username}')
                    else:
                        await ctx.respond('Nation not found.')
    elif admin == True and user != None:    
        role = discord.utils.get(ctx.guild.roles, name="Admiralty")
        if role in ctx.author.roles:
            if db.discord_users.find_one({'_id':user.id}):
                await ctx.respond('User is already registered.')
            elif db.discord_users.find_one({'nation_id':nation_id}):
                await ctx.respond('This nation is already registered.')
            else:
                try:
                    db.discord_users.insert_one({'_id':ctx.author.id, 'nation_id':nation_id})
                    await ctx.respond('Registration successful! user has been verified.')
                    await user.add_roles(discord.utils.get(user.guild.roles, name='Jack Approves! ✅'))
                except:
                    await ctx.respond('Something went wrong...')
        else:
            await ctx.respond(f'admin mode is for admiralty only.')
    else:
        await ctx.respond(f'Error: Invalid arguments.')



@client.slash_command(description="Unregister your nation with jack, Admiralty can unregister any nation.")
async def unregister(ctx, user:discord.User=None, nation_id:int=None, admin:bool=False):
    await ctx.defer()
    if admin == False and user == None and nation_id == None:
        if db.discord_users.find_one({'_id':ctx.author.id}):
            db.discord_users.delete_one({'_id':ctx.author.id})
            await ctx.respond('Unregistration successful!')
        else:
            await ctx.respond('You are not registered.')
    elif admin == True and user != None and nation_id == None:
        role = discord.utils.get(ctx.guild.roles, name="Admiralty")
        if role in ctx.author.roles:
            if db.discord_users.find_one({'_id':user.id}):
                db.discord_users.delete_one({'_id':user.id})
                await ctx.respond('Unregistration successful!')
            else:
                await ctx.respond('User is not registered.')
        else:
            await ctx.respond(f'admin mode is for admiralty only.')
    elif admin == True and user == None and nation_id != None:
        role = discord.utils.get(ctx.guild.roles, name="Admiralty")
        if role in ctx.author.roles:
            if db.discord_users.find_one({'nation_id':nation_id}):
                db.discord_users.delete_one({'nation_id':nation_id})
                await ctx.respond('Unregistration successful!')
            else:
                await ctx.respond('Nation is not registered.')
        else:
            await ctx.respond(f'admin mode is for admiralty only.')
    else:
        await ctx.respond(f'Error: Invalid arguments.')



@client.slash_command(description="Update a user's verification details.")
async def update_verification(ctx, user:discord.User, nation_id:int):
    role = discord.utils.get(ctx.guild.roles, name="Admiralty")
    if role in ctx.author.roles:
        if type(db.discord_users.find_one({'_id':user.id})) is dict:
            filter = { '_id':user.id }
            db.discord_users.update_one(filter, {"$set": {'username':user.name, 'nation_id':nation_id}})
            await ctx.respond("Success!, the verification details for this user have been updated.")
        elif db.discord_users.find_one({'_id':user.id}) == None:
            await ctx.respond('The user is not verified yet.')
        else:
            await ctx.respond('Something went wrong...')
    else:
        await ctx.respond(f'This command is only for Admiralty.')


@client.slash_command(description="Get information about yourself, regiser if you haven't already.")
async def me(ctx):
    await ctx.defer()
    account = db.discord_users.find_one({'_id':ctx.author.id})
    if account: parameters = f"id:{account['nation_id']}"
    else: parameters = f'discord_id:"{str(ctx.author.id)}"'
    async with aiohttp.ClientSession() as session:
        async with session.post(graphql, json={'query': f'''
{{
  nations({parameters}){{
    data{{
      id nation_name leader_name alliance_position
      alliance{{
        id name average_score rank
      }}
      continent war_policy domestic_policy color num_cities score flag vacation_mode_turns beige_turns
      last_active date soldiers tanks aircraft ships missiles nukes spies discord
      discord_id alliance_seniority offensive_wars_count defensive_wars_count
    }}
  }}
}}                                               
                                               '''}) as r:
            json_obj = await r.json()
            if json_obj["data"]["nations"]["data"]:
                nat_dict = json_obj["data"]["nations"]["data"][0]
                embed = discord.Embed(title=f'{nat_dict["nation_name"]}', url=f'https://politicsandwar.com/nation/id={nat_dict["id"]}', description=f'''
{nat_dict["leader_name"]} | <@{nat_dict["discord_id"]}>

**Alliance**
[{nat_dict["alliance"]["name"]}](https://politicsandwar.com/alliance/id={nat_dict["alliance"]["id"]}) ``{nat_dict["alliance_position"].capitalize()} | {nat_dict["alliance_seniority"]} days``
``Rank: {nat_dict["alliance"]["rank"]} | Avg Score: {int(nat_dict["alliance"]["average_score"])}``

**General**
``ID: {nat_dict["id"]} | Score: {nat_dict["score"]} | 🏙️ {nat_dict["num_cities"]}``
``Active: {humanize.naturaltime(datetime.fromisoformat(nat_dict["last_active"]))} | {humanize.naturaldelta(datetime.now(timezone.utc) - datetime.fromisoformat(nat_dict["date"]))} old``
``{continents[nat_dict["continent"]]} | {nat_dict["war_policy"].capitalize()} | {(nat_dict["domestic_policy"].replace('_', ' ')).capitalize()}``
``{nat_dict["color"].capitalize()} | VM: {nat_dict["vacation_mode_turns"]} turns | Beige: {nat_dict["beige_turns"]} turns``

**Range**
``⬆️ {round((nat_dict["score"] * 0.75),2)} to {round((nat_dict["score"] * 2.5),2)}``
``⬇️ {round((nat_dict["score"] / 2.5),2)} to {round((nat_dict["score"] / 0.75),2)}``
``🕵️ {round((nat_dict["score"] / 2.5),2)} to {round((nat_dict["score"] * 2.5),2)}``

**Wars**
``⬆️ {nat_dict["offensive_wars_count"]} | ⬇️ {nat_dict["defensive_wars_count"]}``

**Military**
``💂 {nat_dict["soldiers"]} | ⚙️ {nat_dict["tanks"]} | ✈️ {nat_dict["aircraft"]} | 🚢 {nat_dict["ships"]}\n🚀 {nat_dict["missiles"]} | ☢️ {nat_dict["nukes"]} 🕵️ {nat_dict["spies"]}``
                                      ''')

                embed.set_image(url=f'{nat_dict["flag"]}')
                embed.set_footer(text="DM Sam Cooper for help or to report a bug                  .", icon_url='https://i.ibb.co/qg5vp8w/dp-cropped.jpg')
                await ctx.respond(embed=embed)
            else:
                await ctx.respond("Could not find you or your nation.")



@client.slash_command(description="Find and get information about a nation.")
async def nation(ctx, nation: discord.Option(str, "Choose nation", autocomplete=nations_autocomplete)): # type: ignore
    await ctx.defer()
    nation_id = re.search(r'^\d+(?=\s*-)', nation).group()
    async with aiohttp.ClientSession() as session:
        async with session.post(graphql, json={'query': f'''
{{
  nations(id:{int(nation_id)}){{
    data{{
      id nation_name leader_name alliance_position
      alliance{{
        id name average_score rank
      }}
      continent war_policy domestic_policy color num_cities score flag vacation_mode_turns beige_turns
      last_active date soldiers tanks aircraft ships missiles nukes spies discord
      discord_id alliance_seniority offensive_wars_count defensive_wars_count
    }}
  }}
}}                                               
                                               '''}) as r:
            json_obj = await r.json()
            if json_obj["data"]["nations"]["data"]:
                nat_dict = json_obj["data"]["nations"]["data"][0]
                embed = discord.Embed(title=f'{nat_dict["nation_name"]}', url=f'https://politicsandwar.com/nation/id={nat_dict["id"]}', description=f'''
{nat_dict["leader_name"]} | <@{nat_dict["discord_id"]}>

**Alliance**
[{nat_dict["alliance"]["name"]}](https://politicsandwar.com/alliance/id={nat_dict["alliance"]["id"]}) ``{nat_dict["alliance_position"].capitalize()} | {nat_dict["alliance_seniority"]} days``
``Rank: {nat_dict["alliance"]["rank"]} | Avg Score: {int(nat_dict["alliance"]["average_score"])}``

**General**
``ID: {nat_dict["id"]} | Score: {nat_dict["score"]} | 🏙️ {nat_dict["num_cities"]}``
``Active: {humanize.naturaltime(datetime.fromisoformat(nat_dict["last_active"]))} | {humanize.naturaldelta(datetime.now(timezone.utc) - datetime.fromisoformat(nat_dict["date"]))} old``
``{continents[nat_dict["continent"]]} | {nat_dict["war_policy"].capitalize()} | {(nat_dict["domestic_policy"].replace('_', ' ')).capitalize()}``
``{nat_dict["color"].capitalize()} | VM: {nat_dict["vacation_mode_turns"]} turns | Beige: {nat_dict["beige_turns"]} turns``

**Range**
``⬆️ {round((nat_dict["score"] * 0.75),2)} to {round((nat_dict["score"] * 2.5),2)}``
``⬇️ {round((nat_dict["score"] / 2.5),2)} to {round((nat_dict["score"] / 0.75),2)}``
``🕵️ {round((nat_dict["score"] / 2.5),2)} to {round((nat_dict["score"] * 2.5),2)}``

**Wars**
``⬆️ {nat_dict["offensive_wars_count"]} | ⬇️ {nat_dict["defensive_wars_count"]}``

**Military**
``💂 {nat_dict["soldiers"]} | ⚙️ {nat_dict["tanks"]} | ✈️ {nat_dict["aircraft"]} | 🚢 {nat_dict["ships"]}\n🚀 {nat_dict["missiles"]} | ☢️ {nat_dict["nukes"]} 🕵️ {nat_dict["spies"]}``
                                      ''')

                embed.set_image(url=f'{nat_dict["flag"]}')
                embed.set_footer(text="DM Sam Cooper for help or to report a bug                  .", icon_url='https://i.ibb.co/qg5vp8w/dp-cropped.jpg')
                await ctx.respond(embed=embed)
            else:
                await ctx.respond("Could not find this nation.")



@client.slash_command(description="Find a discord user's nation or a nation's discord user.")
async def whois(ctx, user: discord.User=None, nation_id:int=None):
    await ctx.defer()
    if user == None and nation_id == None:
        await ctx.respond("You must specify either a user or a nation.")
    elif user != None and nation_id != None:
        await ctx.respond("You only need to specify one of the two.")
    elif user != None and nation_id == None:
        account = db.discord_users.find_one({'_id':user.id})
        if account: parameter = f"id: {account['nation_id']}"
        else: parameter = f'discord: "{str(user.name)}"'
        async with aiohttp.ClientSession() as session:
            async with session.post(graphql, json={'query': f'''
{{
nations({parameter}){{
    data{{
    id nation_name leader_name alliance_position
    alliance{{
        id name average_score rank
    }}
    continent war_policy domestic_policy color num_cities score flag vacation_mode_turns beige_turns
    last_active date soldiers tanks aircraft ships missiles nukes spies discord
    discord_id alliance_seniority offensive_wars_count defensive_wars_count
    }}
}}
}}                                               
                                                '''}) as r:
                json_obj = await r.json()
                if json_obj["data"]["nations"]["data"]:
                    nat_dict = json_obj["data"]["nations"]["data"][0]
                    embed = discord.Embed(title=f'{nat_dict["nation_name"]}', url=f'https://politicsandwar.com/nation/id={nat_dict["id"]}', description=f'''
{nat_dict["leader_name"]} | <@{nat_dict["discord_id"]}>

**Alliance**
[{nat_dict["alliance"]["name"]}](https://politicsandwar.com/alliance/id={nat_dict["alliance"]["id"]}) ``{nat_dict["alliance_position"].capitalize()} | {nat_dict["alliance_seniority"]} days``
``Rank: {nat_dict["alliance"]["rank"]} | Avg Score: {int(nat_dict["alliance"]["average_score"])}``

**General**
``ID: {nat_dict["id"]} | Score: {nat_dict["score"]} | 🏙️ {nat_dict["num_cities"]}``
``Active: {humanize.naturaltime(datetime.fromisoformat(nat_dict["last_active"]))} | {humanize.naturaldelta(datetime.now(timezone.utc) - datetime.fromisoformat(nat_dict["date"]))} old``
``{continents[nat_dict["continent"]]} | {nat_dict["war_policy"].capitalize()} | {(nat_dict["domestic_policy"].replace('_', ' ')).capitalize()}``
``{nat_dict["color"].capitalize()} | VM: {nat_dict["vacation_mode_turns"]} turns | Beige: {nat_dict["beige_turns"]} turns``

**Range**
``⬆️ {round((nat_dict["score"] * 0.75),2)} to {round((nat_dict["score"] * 2.5),2)}``
``⬇️ {round((nat_dict["score"] / 2.5),2)} to {round((nat_dict["score"] / 0.75),2)}``
``🕵️ {round((nat_dict["score"] / 2.5),2)} to {round((nat_dict["score"] * 2.5),2)}``

**Wars**
``⬆️ {nat_dict["offensive_wars_count"]} | ⬇️ {nat_dict["defensive_wars_count"]}``

**Military**
``💂 {nat_dict["soldiers"]} | ⚙️ {nat_dict["tanks"]} | ✈️ {nat_dict["aircraft"]} | 🚢 {nat_dict["ships"]}\n🚀 {nat_dict["missiles"]} | ☢️ {nat_dict["nukes"]} 🕵️ {nat_dict["spies"]}``
                                        ''')

                    embed.set_image(url=f'{nat_dict["flag"]}')
                    embed.set_footer(text="DM Sam Cooper for help or to report a bug                  .", icon_url='https://i.ibb.co/qg5vp8w/dp-cropped.jpg')
                    await ctx.respond(embed=embed)
                else:
                    await ctx.respond("Could not find this user.")
    elif user == None and nation_id != None:
        account = db.discord_users.find_one({'nation_id':nation_id})
        if account:
            user = await client.fetch_user(account["_id"])
            await ctx.respond(f'''
Username : `{user.display_name}`
Global name : `{user.name}`
ID : `{user.id}`
        ''')
        elif account == None:
            async with aiohttp.ClientSession() as session:
                async with session.post(graphql, json={'query': f'''
{{
nations(id:{nation_id}){{
  data{{
    discord_id
  }}
}}
}}
                '''}) as r:
                            json_obj = await r.json()
                            if json_obj["data"]["nations"]["data"]:
                                discord_id = json_obj["data"]["nations"]["data"][0]["discord_id"]
                                user = await client.fetch_user(int(discord_id))
                                await ctx.respond(f'''
Username : `{user.display_name}`
Global name : `{user.name}`
ID : `{user.id}`
        ''')
        else:
            await ctx.respond("Could not find this user.")
    else:
        await ctx.respond("There was an error with your arguments.")




@client.slash_command(description="Find and get information about an alliance.")
async def alliance(ctx, alliance: discord.Option(str, "Choose alliance", autocomplete=alliances_autocomplete)): # type: ignore
    await ctx.defer()
    alliance_id = re.search(r'^\d+(?=\s*-)', alliance).group()
    async with aiohttp.ClientSession() as session:
        async with session.post(graphql, json={'query': f'''
{{
  alliances(id: {alliance_id}) {{
    data {{
      id name acronym score color date average_score
      treaties{{ treaty_type alliance1_id alliance2_id approved}}
      flag discord_link wiki_link rank
    }}}}}}
'''}) as r:
            json_obj = await r.json()
            if json_obj["data"]["alliances"]["data"]:
                alliance_dict = json_obj["data"]["alliances"]["data"][0]
                embed = discord.Embed(title=f'{alliance_dict["name"]} ({alliance_dict["acronym"]})', url=f'https://politicsandwar.com/alliance/id={alliance_dict["id"]}', description=f'''
**General**
``ID: {alliance_dict["id"]}``
``Founded: {humanize.naturaltime(datetime.fromisoformat(alliance_dict["date"]))} | Avg Score: {int(alliance_dict["average_score"])} | Rank: {alliance_dict["rank"]}``
[Discord]({alliance_dict["discord_link"]}) | [Wiki]({alliance_dict["wiki_link"]})
                                      ''')
                embed.set_image(url=f'{alliance_dict["flag"]}')
                embed.set_footer(text="DM Sam Cooper for help or to report a bug                  .", icon_url='https://i.ibb.co/qg5vp8w/dp-cropped.jpg')
                await ctx.respond(embed=embed)
            else:
                await ctx.respond("Could not find this alliance.")




@client.slash_command(description="Find potential counters for a nation.")
async def counter(ctx, 
                  nation:discord.Option(str, "Choose nation to be countered", autocomplete=nations_autocomplete),
                  alliance:discord.Option(str, "Choose alliance to find counters from", autocomplete=alliances_autocomplete)):
    await ctx.defer()
    nation_id = re.search(r'^\d+(?=\s*-)', nation).group()
    alliance_id = re.search(r'^\d+(?=\s*-)', alliance).group()
    async with aiohttp.ClientSession() as session:
        async with session.post(graphql, json={'query': f'''
{{
  nations(id:{nation_id}){{
    data{{
    id nation_name leader_name alliance_id war_policy
    num_cities score last_active soldiers tanks
    aircraft ships missiles nukes spies
    }}}}}}
        '''}) as r:
            json_obj = await r.json()
            if json_obj["data"]["nations"]["data"]:
                enemy = json_obj["data"]["nations"]["data"][0]
                score = enemy["score"]
                min_score = round((score / 2.5),2)
                max_score = round((score / 0.75),2)
                async with session.post(graphql, json={'query': f'''
{{
  nations(alliance_id:{alliance_id}, min_score:{min_score}, max_score:{max_score}, vmode:false, alliance_position:[2,3,4,5]){{
    data{{
    id nation_name leader_name alliance_id war_policy
    num_cities score last_active soldiers tanks
    aircraft ships missiles nukes spies}}}}}}
                '''}) as r2:
                    json_obj = await r2.json()
                    if json_obj["data"]["nations"]["data"]:
                        in_range_members = json_obj["data"]["nations"]["data"]
                        for d in in_range_members: d['mil_score'] = float(d['soldiers']) * 0.001 + float(
                            d['tanks']) * 0.008 + float(d['aircraft']) * 0.4 + float(d['ships']) * 0.60 + float(
                            d['num_cities'] * 4.0 + float(d['score'] * 0.1))
                        counters = sorted(in_range_members, key = lambda i: i['mil_score'],reverse=True)
                        if len(counters) >= 5:
                            n = 5
                        else:
                            n = len(counters)
                        enemy_embed = discord.Embed(title='Enemy', description=f'''
[{enemy["leader_name"]} of {enemy["nation_name"]}](https://politicsandwar.com/nation/id={enemy["id"]})
`🏙️ {enemy["num_cities"]} | NS: {enemy["score"]} | {enemy["war_policy"]}`
`💂 {enemy["soldiers"]} | ⚙️ {enemy["tanks"]} | ✈️ {enemy["aircraft"]} | 🚢 {enemy["ships"]}\n🚀 {enemy["missiles"]} | ☢️ {enemy["nukes"]}`
                                                    ''')
                        await ctx.send(embed=enemy_embed)
                        for x in counters[0:n]:
                            counter_embed = discord.Embed(title=f"Counter {counters.index(x) + 1}", description=f'''
[{x["leader_name"]} of {x["nation_name"]}](https://politicsandwar.com/nation/id={x["id"]})
🏙️ `{x["num_cities"]} | NS: {x["score"]} | {x["war_policy"]}`
`💂 {x["soldiers"]} | ⚙️ {x["tanks"]} | ✈️ {x["aircraft"]} | 🚢 {x["ships"]}`
                                                    ''')
                            await ctx.send(embed=counter_embed)
                        await ctx.respond(f"Posted {n} counters from {alliance}.")
                    else:
                        await ctx.respond("There was an error fetching data about possible counters.")
            else:
                await ctx.respond("There was an error fetching data about this nation.")
        


@client.slash_command(description="See warchest information of a captain, restricted to Mentors and above.")
async def warchest(ctx, nation_id:int=None, user:discord.User=None):
    admiralty = discord.utils.get(ctx.guild.roles, name="Admiralty")
    mentor = discord.utils.get(ctx.guild.roles, name="Mentor")
    if admiralty in ctx.author.roles or mentor in ctx.author.roles:
        await ctx.defer(ephemeral=True)
        try:
            if user != None and nation_id == None:
                user_nation = db.discord_users.find_one({"_id": user.id})
                if user_nation: 
                    parameter = f"id: {user_nation['nation_id']}, alliance_position:[2,3,4,5], alliance_id:913"
                else:
                    parameter = f'discord_id:"{str(user.id)}", alliance_position:[2,3,4,5], alliance_id:913'
            elif nation_id != None and user == None:
                parameter = f"id:{nation_id}, alliance_position:[2,3,4,5], alliance_id:913"
            async with aiohttp.ClientSession() as session:
                async with session.post(graphql, json={'query': f'''
    {{
    nations({parameter}){{
    data{{
        id nation_name money credits food coal oil uranium 
        lead iron bauxite gasoline munitions steel aluminum
    }}}}}}
                                                        '''}) as r:
                    json_obj = await r.json()
                    if json_obj["data"]["nations"]["data"]:
                        nation = json_obj["data"]["nations"]["data"][0]
                        embed = discord.Embed(title=f'{nation["nation_name"]} Warchest', url=f'https://politicsandwar.com/nation/id={nation["id"]}', description=f'''
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
    ''')
                        await ctx.followup.send(embed=embed)
                    else:
                        await ctx.respond("Could not find this nation.", ephemeral=True)
        except:
                await ctx.respond("There was an error.", ephemeral=True)
    else:
        await ctx.respond('You do not have permission to use this command', ephemeral=True)




@client.slash_command(description="Find the fastest way to beige someone at given resistance.")
async def resistance(ctx, resistance:int):
    combinations = efficient_combinations(resistance)
    embed = discord.Embed(title=f'Fastest beige for {resistance} resistance.', description=f'''
MAPs needed : **{combinations[0][1]['total_cost']}**
{' | '.join("{}: {}".format(k, v) for k, v in combinations[0][0].items())}

MAPs needed : **{combinations[1][1]['total_cost']}**
{' | '.join("{}: {}".format(k, v) for k, v in combinations[1][0].items())}

MAPs needed : **{combinations[2][1]['total_cost']}**
{' | '.join("{}: {}".format(k, v) for k, v in combinations[2][0].items())}

MAPs needed : **{combinations[3][1]['total_cost']}**
{' | '.join("{}: {}".format(k, v) for k, v in combinations[3][0].items())}

MAPs needed : **{combinations[4][1]['total_cost']}**
{' | '.join("{}: {}".format(k, v) for k, v in combinations[4][0].items())}
                              ''')
    await ctx.respond(embed=embed)





@client.slash_command(description="Find the current market prices of all resources.")
async def market(ctx, resource: discord.Option(str, "Choose resource to find prices of", autocomplete=resources_autocomplete, required=True)):
    async with aiohttp.ClientSession() as session:
        async with session.post(graphql, json={'query': f'''
{{
  top_trade_info{{
    resources(resource:[{resource}]){{
      average_price
      best_buy_offer{{
        offer_resource offer_amount price
      }}
      best_sell_offer{{
        offer_resource offer_amount price
      }}}}}}}}
                '''}) as r:
                    json_obj = await r.json()
                    if json_obj["data"]["top_trade_info"]["resources"]:
                        resources = json_obj["data"]["top_trade_info"]["resources"]
                        embed = discord.Embed(title="Market Prices", description=f'''
**{resource.capitalize()}**
Average price : {"${:,.2f}".format(resources[0]["average_price"])}
Best buy offer : {"{:,.2f}".format(resources[0]["best_buy_offer"]["offer_amount"])} for {"${:,.2f}".format(resources[0]["best_buy_offer"]["price"])}
Best sell offer : {"{:,.2f}".format(resources[0]["best_sell_offer"]["offer_amount"])} for {"${:,.2f}".format(resources[0]["best_sell_offer"]["price"])}
''')
                        await ctx.respond(embed=embed)
                    else:
                        await ctx.respond("Could not find this nation.")




@client.slash_command(description="An example pirate build with 900 infra")
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




@client.slash_command(description="Calculates the total bank contents by a bank loot note.")
async def bank(ctx, loot:str):
    nums = re.findall(r'\b\d{1,3}(?:,\d{3})*(?:.\d+)?\b', loot)
    resources = {'percent': float(nums[0]), "money":int(re.sub('\$|\,', '', nums[1])), "food":int(nums[12].replace(',', '')), "coal":int(nums[2].replace(',', '')), "oil":int(nums[3].replace(',', '')), "uranium":int(nums[4].replace(',', '')), "lead":int(nums[7].replace(',', '')), "iron":int(nums[5].replace(',', '')), "bauxite":int(nums[6].replace(',', '')), "gasoline":int(nums[8].replace(',', '')), "munitions":int(nums[9].replace(',', '')), "steel":int(nums[10].replace(',', '')), "aluminum":int(nums[11].replace(',', ''))}
    bank = {"money":resources["money"]*(100/resources["percent"]), "food":resources["food"]*(100/resources["percent"]), "coal":resources["coal"]*(100/resources["percent"]), "oil":resources["oil"]*(100/resources["percent"]), "uranium":resources["uranium"]*(100/resources["percent"]), "lead":resources["lead"]*(100/resources["percent"]), "iron":resources["iron"]*(100/resources["percent"]), "bauxite":resources["bauxite"]*(100/resources["percent"]), "gasoline":resources["gasoline"]*(100/resources["percent"]), "munitions":resources["munitions"]*(100/resources["percent"]), "steel":resources["steel"]*(100/resources["percent"]), "aluminum":resources["aluminum"]*(100/resources["percent"])}    
    
    embed = discord.Embed(title="Bank Contents", description=f'''
Money : {"${:,.2f}".format(bank['money'])}
Food : {"{:,.2f}".format(bank['food'])}
Coal : {"{:,.2f}".format(bank['coal'])}
Oil : {"{:,.2f}".format(bank['oil'])}
Uranium : {"{:,.2f}".format(bank['uranium'])}
Lead : {"{:,.2f}".format(bank['lead'])}
Iron : {"{:,.2f}".format(bank['iron'])}
Bauxite : {"{:,.2f}".format(bank['bauxite'])}
Gasoline : {"{:,.2f}".format(bank['gasoline'])}
Munitions : {"{:,.2f}".format(bank['munitions'])}
Steel : {"{:,.2f}".format(bank['steel'])}
Aluminum : {"{:,.2f}".format(bank['aluminum'])}    
''')
    await ctx.send(embed=embed)




beige_alert = discord.SlashCommandGroup("beige_alert", "Commands to manage beige alerts")

@beige_alert.command(description="Add a nation to the beige alert list")
async def add(ctx, nation:discord.Option(str, "Choose nation to add to beige alert list", autocomplete=nations_autocomplete)):
    await ctx.defer()
    captain_role = discord.utils.get(ctx.guild.roles, name="Captain")
    if captain_role in ctx.author.roles:
        if db.discord_users.find_one({'_id':ctx.author.id}):
            nation_id = int(re.search(r'^\d+(?=\s*-)', nation).group())
            nation_name = re.search(r"\d+\s*-\s*(.*)", nation).group(1)
            misc = db.misc.find_one({'_id':True})
            existing_targets = misc['beige_alert_targets']
            if len(existing_targets) < 200:
                if nation_id not in existing_targets:
                    existing_targets.append(nation_id)
                    db.beige_alerts.insert_one({'_id':nation_id, 'name':nation_name, 'subscribed_captains':[ctx.author.id]})
                    db.misc.update_one({'_id':True}, {"$set": {'beige_alert_targets':existing_targets}})
                    await ctx.respond(f'Added {nation} to your beige alert list.')

                elif nation_id in existing_targets:
                    alert = db.beige_alerts.find_one({'_id':nation_id})
                    if ctx.author.id not in alert['subscribed_captains']:
                        alert['subscribed_captains'].append(ctx.author.id)
                        db.beige_alerts.update_one({'_id':nation_id}, {"$set": {'subscribed_captains':alert['subscribed_captains']}})
                        await ctx.respond(f'Added you to in the list for {nation}.')
                    else:
                        await ctx.respond(f'You are already subscribed to {nation}.')
                else:
                    await ctx.respond(f'An error occurred.')

            else:
                await ctx.respond(f'I have reached the maximum number of beige alerts.')
        
        else:
            await ctx.respond('You need to register your nation with jack before you can use this command.')
    else:
        await ctx.respond(f'This command is only for Arrgh Captains.')




@beige_alert.command(description="Search through your beige alerts and remove if needed.")
async def view_or_remove(ctx, target:discord.Option(str, "By default shows first 25, start typing to search.", autocomplete=targets_autocomplete)):
    if target == "No active alerts":
        await ctx.respond("You have no active alerts to remove.")
    else:
        target_id = int(re.search(r'^\d+(?=\s*-)', target).group())
        alert = db.beige_alerts.find_one({'_id': target_id})

        if alert:
            subscribed_captains = alert['subscribed_captains']

            if ctx.author.id in subscribed_captains:
                if len(subscribed_captains) > 1:
                    subscribed_captains.remove(ctx.author.id)
                    db.beige_alerts.update_one(
                        {'_id': target_id}, 
                        {"$set": {'subscribed_captains': subscribed_captains}}
                    )
                    await ctx.respond(f"Removed your subscription to {target}.")
                else:
                    misc = db.misc.find_one({'_id': True})
                    existing_targets = misc['beige_alert_targets']
                    existing_targets.remove(target_id)
                    
                    db.misc.update_one(
                        {'_id': True}, 
                        {"$set": {'beige_alert_targets': existing_targets}}
                    )
                    db.beige_alerts.delete_one({'_id': target_id})
                    await ctx.respond(f"Removed {target} from your beige alert list.")
                alerts_cache.pop(ctx.interaction.user.id, None)
            else:
                await ctx.respond("You are not subscribed to this target.")
        else:
            await ctx.respond("Target not found.")

client.add_application_command(beige_alert)



@client.slash_command(description="Calculate the war ranges of a nation or of any score.")
async def score(ctx, nation:discord.Option(str, "Choose nation to find war range of", autocomplete=nations_autocomplete, required=False, default=None), score:float=None):
    if score == None and nation == None:
        await ctx.respond("You must specify either a nation or a score.")
    elif score != None and nation != None:
        await ctx.respond("You can only specify one of the two.")
    elif score == None and nation != None:
        nation_id = re.search(r'^\d+(?=\s*-)', nation).group()
        async with aiohttp.ClientSession() as session:
            async with session.post(graphql, json={'query': f'''
{{
  nations(id:{nation_id}){{
    data{{
    id nation_name score
    }}
  }}
}} '''}) as r:
                json_obj = await r.json()
                nation = json_obj["data"]["nations"]["data"]
                if nation:
                    await ctx.respond(f'''
{nation[0]["nation_name"]}
Score: {nation[0]["score"]}
Off range: {round((nation[0]["score"] * 0.75),2)} to {round((nation[0]["score"] * 2.5),2)}
Def range: {round((nation[0]["score"] / 2.5),2)} to {round((nation[0]["score"] / 0.75),2)}
Spy range: {round((nation[0]["score"] / 2.5),2)} to {round((nation[0]["score"] * 2.5),2)}
''')
                else:
                    await ctx.respond("Could not find this nation.")

    elif score != None and nation == None:
        await ctx.respond(f'''
Score: {round(score,2)}
Off range: {round((score * 0.75),2)} to {round((score * 2.5),2)}
Def range: {round((score / 2.5),2)} to {round((score / 0.75),2)}
Spy range: {round((score / 2.5),2)} to {round((score * 2.5),2)}
''')




client.run(token)