import discord
from discord.ext import commands, tasks
import json
import os
from keep_alive import keep_alive
keep_alive()

# ---------------- INTENTS ----------------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------- FILES ----------------
INVITES_FILE = "invites.json"
CONFIG_FILE = "config.json"

# ---------------- CONSTANTS ----------------
ROLES_BY_INVITES = {
    3: 1470110867667423252,
    5: 1470111167480463463,
    10: 1470111518615142441,
    15: 1470111729848418316
}

ANTI_SCAM_CHANNEL = 1467549018182652191
WELCOME_CHANNEL = 1467549003486073058

guild_invites = {}
message_count = {}

# ---------------- LOAD INVITES ----------------
if os.path.exists(INVITES_FILE):
    with open(INVITES_FILE, "r") as f:
        invites_data = json.load(f)
else:
    invites_data = {}

# ---------------- HELPERS ----------------
def ensure(uid):
    """Assure que l'utilisateur a toutes les clés nécessaires"""
    if uid not in invites_data:
        invites_data[uid] = {"total": 0, "left": 0}
    else:
        if "total" not in invites_data[uid]:
            invites_data[uid]["total"] = 0
        if "left" not in invites_data[uid]:
            invites_data[uid]["left"] = 0

def save():
    with open(INVITES_FILE, "w") as f:
        json.dump(invites_data, f, indent=4)

def real_invites(uid):
    ensure(uid)
    return invites_data[uid]["total"] - invites_data[uid]["left"]

# ---------------- READY ----------------
@bot.event
async def on_ready():
    print(f"{bot.user} connecté")
    for guild in bot.guilds:
        guild_invites[guild.id] = await guild.invites()
    auto_message.start()

# ---------------- ROLES ----------------
async def update_roles(member):
    uid = str(member.id)
    count = real_invites(uid)

    for needed, role_id in ROLES_BY_INVITES.items():
        role = member.guild.get_role(role_id)
        if not role:
            continue
        if count >= needed and role not in member.roles:
            await member.add_roles(role)
        elif count < needed and role in member.roles:
            await member.remove_roles(role)

# ---------------- AUTO MESSAGE ----------------
@tasks.loop(minutes=7)
async def auto_message():
    channel = bot.get_channel(ANTI_SCAM_CHANNEL)
    if channel:
        await channel.send(
            "# Pour ne pas vous faire scam prenez des middle man\n"
            "**Les staff ne prennent pas en charge les scams sans middle man**"
        )

# ---------------- MESSAGE ----------------
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await bot.process_commands(message)

# ---------------- MEMBER JOIN ----------------
@bot.event
async def on_member_join(member):
    guild = member.guild
    new_invites = await guild.invites()
    old_invites = guild_invites.get(guild.id, [])

    inviter = None
    for new in new_invites:
        for old in old_invites:
            if new.code == old.code and new.uses > old.uses:
                inviter = new.inviter

    guild_invites[guild.id] = new_invites

    if inviter:
        uid = str(inviter.id)
        ensure(uid)
        invites_data[uid]["total"] += 1
        save()

        inviter_member = guild.get_member(inviter.id)
        if inviter_member:
            await update_roles(inviter_member)

        channel = guild.get_channel(WELCOME_CHANNEL)
        if channel:
            await channel.send(
                f"{member.mention} a été invité par {inviter.mention} "
                f"et a maintenant **{real_invites(uid)}** invites"
            )

# ---------------- MEMBER LEAVE ----------------
@bot.event
async def on_member_remove(member):
    guild = member.guild
    old_invites = guild_invites.get(guild.id, [])
    new_invites = await guild.invites()
    guild_invites[guild.id] = new_invites

    for old in old_invites:
        new = discord.utils.get(new_invites, code=old.code)
        if new and new.uses < old.uses:
            uid = str(old.inviter.id)
            ensure(uid)
            invites_data[uid]["left"] += 1
            save()

            inviter_member = guild.get_member(old.inviter.id)
            if inviter_member:
                await update_roles(inviter_member)
            break

# ---------------- COMMANDS ----------------
@bot.command()
async def invites(ctx, member: discord.Member = None):
    member = member or ctx.author
    uid = str(member.id)
    ensure(uid)
    await ctx.send(
        f"{member.mention} a **{real_invites(uid)}** invites "
        f"({invites_data[uid]['total']} total | {invites_data[uid]['left']} left)"
    )

@bot.command()
async def add_invite(ctx, member: discord.Member, amount: int):
    uid = str(member.id)
    ensure(uid)
    invites_data[uid]["total"] += amount
    save()
    await update_roles(member)
    await ctx.send(f"{amount} invites ajoutées à {member.mention}")

@bot.command()
async def remove_invite(ctx, member: discord.Member, amount: int):
    uid = str(member.id)
    ensure(uid)
    invites_data[uid]["total"] = max(0, invites_data[uid]["total"] - amount)
    save()
    await update_roles(member)
    await ctx.send(f"{amount} invites retirées à {member.mention}")

@bot.command()
async def skip_timer(ctx):
    await auto_message.restart()
    await ctx.send("Timer du message automatique relancé !")

@bot.command()
async def leaderboard_invites(ctx):
    msg = "🏆 **Leaderboard Invites** 🏆\n"
    for uid, d in sorted(invites_data.items(), key=lambda x: real_invites(x[0]), reverse=True):
        member = ctx.guild.get_member(int(uid))
        if member:
            msg += f"{member.mention} — **{real_invites(uid)}** invites\n"
    await ctx.send(msg)

@bot.command()
async def reset_roles(ctx, *args):
    guild = ctx.guild
    if not args:
        for member in guild.members:
            for role_id in ROLES_BY_INVITES.values():
                role = guild.get_role(role_id)
                if role in member.roles:
                    await member.remove_roles(role)
        await ctx.send("Tous les rôles d'invites ont été retirés.")
        return

    target_role = None
    target_member = None
    for arg in args:
        if arg.startswith("<@&"):
            role_id = int(arg[3:-1])
            target_role = guild.get_role(role_id)
        elif arg.startswith("<@"):
            member_id = int(arg[2:-1].replace("!", ""))
            target_member = guild.get_member(member_id)

    if target_role and target_member:
        if target_role in target_member.roles:
            await target_member.remove_roles(target_role)
        await ctx.send(f"Le rôle {target_role.name} a été retiré à {target_member.mention}.")
    elif target_role:
        for member in guild.members:
            if target_role in member.roles:
                await member.remove_roles(target_role)
        await ctx.send(f"Le rôle {target_role.name} a été retiré à tout le monde.")
    elif target_member:
        for role_id in ROLES_BY_INVITES.values():
            role = guild.get_role(role_id)
            if role in target_member.roles:
                await target_member.remove_roles(role)
        await ctx.send(f"Tous les rôles d'invites ont été retirés à {target_member.mention}.")


@bot.command()
async def commandes(ctx):
    """Liste toutes les commandes disponibles avec leur fonction"""
    msg = (
        "**Liste des commandes SEK Bot :**\n\n"
        "`!invites [@pseudo]` — Montre le nombre d'invites du membre (ou toi si aucun membre mentionné)\n"
        "`!add_invite @pseudo X` — Ajoute X invites au membre mentionné\n"
        "`!remove_invite @pseudo X` — Retire X invites au membre mentionné\n"
        "`!leaderboard_invites` — Affiche le top des membres par nombre d'invites\n"
        "`!skip_timer` — Envoie immédiatement le message automatique du salon anti-scam\n"
        "`!reset_roles` — Supprime tous les rôles d'invites à tout le monde\n"
        "`!reset_roles @pseudo` — Supprime tous les rôles d'invites à la personne mentionnée\n"
        "`!reset_roles @role` — Supprime le rôle mentionné à tout le monde\n"
        "`!reset_roles @role @pseudo` — Supprime le rôle mentionné à la personne mentionnée\n"
        "`!commandes` — Affiche cette liste de commandes et leurs fonctions"
    )
    await ctx.send(msg)

# ---------------- TOKEN ----------------
with open(CONFIG_FILE) as f:
    token = json.load(f)["token"]
bot.run(os.getenv("TOKEN"))
bot.run(token)
