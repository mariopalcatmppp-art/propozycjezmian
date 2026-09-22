import os
import random
import discord
from discord import app_commands
from discord.ext import commands

# Configuration and Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Dictionary for counting warnings per user
user_warnings = {}

# Dictionary to keep track of active roll channels
active_rolls = {}


@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user.name} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"Zsynchronizowano {len(synced)} komend(y) slash.")
    except Exception as e:
        print(f"Błąd podczas synchronizacji komend: {e}")


# --- SLASH COMMANDS ---


@bot.tree.command(name="ping", description="Sprawdź opóźnienie bota.")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"Pong! 🏓 Opóźnienie wynosi: {latency} ms.")


@bot.tree.command(name="clear", description="Usuwa określoną liczbę wiadomości z kanału.")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        await interaction.response.send_message(
            "Liczba wiadomości musi być większa niż 0.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(
        f"Pomyślnie usunięto {len(deleted)} wiadomości.", ephemeral=True
    )


@clear.error
async def clear_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "Nie masz uprawnień do zarządzania wiadomościami.", ephemeral=True
        )


@bot.tree.command(name="warn", description="Udziela ostrzeżenia użytkownikowi.")
@app_commands.checks.has_permissions(kick_members=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "Brak powodu"):
    if member.bot:
        await interaction.response.send_message("Nie możesz dać ostrzeżenia botowi.", ephemeral=True)
        return

    user_warnings[member.id] = user_warnings.get(member.id, 0) + 1
    count = user_warnings[member.id]

    embed = discord.Embed(
        title="⚠️ Ostrzeżenie",
        color=discord.Color.gold()
    )
    embed.add_field(name="Użytkownik", value=member.mention, inline=False)
    embed.add_field(name="Powód", value=reason, inline=False)
    embed.add_field(name="Liczba ostrzeżeń", value=str(count), inline=False)

    await interaction.response.send_message(embed=embed)


@warn.error
async def warn_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("Nie masz uprawnień do ostrzegania członków.", ephemeral=True)


@bot.tree.command(name="warnings", description="Sprawdza liczbę ostrzeżeń użytkownika.")
async def warnings(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    count = user_warnings.get(member.id, 0)

    embed = discord.Embed(
        title="📜 Historia ostrzeżeń",
        description=f"Użytkownik {member.mention} posiada **{count}** ostrzeżeń.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="clearwarns", description="Czyści wszystkie ostrzeżenia użytkownika.")
@app_commands.checks.has_permissions(kick_members=True)
async def clearwarns(interaction: discord.Interaction, member: discord.Member):
    if member.id in user_warnings:
        del user_warnings[member.id]
        await interaction.response.send_message(f"Wyczyszczono ostrzeżenia dla {member.mention}.")
    else:
        await interaction.response.send_message(f"Użytkownik {member.mention} nie posiada żadnych ostrzeżeń.", ephemeral=True)


@bot.tree.command(name="kick", description="Wyrzuca użytkownika z serwera.")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Brak powodu"):
    if member.top_role >= interaction.user.top_role and interaction.guild.owner_id != interaction.user.id:
        await interaction.response.send_message("Nie możesz wyrzucić członka z wyższą lub równą rolą.", ephemeral=True)
        return

    await member.kick(reason=reason)
    await interaction.response.send_message(f"Użytkownik {member.mention} został wyrzucony. Powód: {reason}")


@kick.error
async def kick_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("Nie masz uprawnień do wyrzucania członków.", ephemeral=True)


@bot.tree.command(name="ban", description="Banuje użytkownika z serwera.")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Brak powodu"):
    if member.top_role >= interaction.user.top_role and interaction.guild.owner_id != interaction.user.id:
        await interaction.response.send_message("Nie możesz zbanować członka z wyższą lub równą rolą.", ephemeral=True)
        return

    await member.ban(reason=reason)
    await interaction.response.send_message(f"Użytkownik {member.mention} został zbanowany. Powód: {reason}")


@ban.error
async def ban_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("Nie masz uprawnień do banowania członków.", ephemeral=True)


@bot.tree.command(name="userinfo", description="Wyświetla informacje o użytkowniku.")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    roles = [role.mention for role in target.roles if role.name != "@everyone"]

    embed = discord.Embed(
        title=f"Informacje o {target.name}",
        color=target.color
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="ID", value=str(target.id), inline=True)
    embed.add_field(name="Konto utworzono", value=target.created_at.strftime("%d-%m-%Y %H:%M"), inline=True)
    embed.add_field(name="Dołączono na serwer", value=target.joined_at.strftime("%d-%m-%Y %H:%M") if target.joined_at else "Brak danych", inline=True)
    embed.add_field(name=f"Role ({len(roles)})", value=", ".join(roles) if roles else "Brak ról", inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="serverinfo", description="Wyświetla informacje o serwerze.")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(
        title=f"Informacje o {guild.name}",
        color=discord.Color.green()
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(name="ID Serwera", value=str(guild.id), inline=True)
    embed.add_field(name="Właściciel", value=guild.owner.mention if guild.owner else "Nieznany", inline=True)
    embed.add_field(name="Liczba członków", value=str(guild.member_count), inline=True)
    embed.add_field(name="Liczba kanałów", value=str(len(guild.channels)), inline=True)
    embed.add_field(name="Data utworzenia", value=guild.created_at.strftime("%d-%m-%Y %H:%M"), inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="avatar", description="Wyświetla awatar wybranego użytkownika.")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    embed = discord.Embed(
        title=f"Awatar użytkownika {target.name}",
        color=target.color
    )
    embed.set_image(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="roll", description="Losuje liczbę z podanego zakresu.")
async def roll(interaction: discord.Interaction, min_val: int = 1, max_val: int = 100):
    if min_val >= max_val:
        await interaction.response.send_message("Minimalna wartość musi być mniejsza od maksymalnej.", ephemeral=True)
        return

    result = random.randint(min_val, max_val)
    await interaction.response.send_message(f"🎲 Wylosowano liczbę ({min_val}-{max_val}): **{result}**")


# --- BOT RUNNER ---

token = os.getenv("DISCORD_TOKEN")

if not token:
    raise ValueError("Nie znaleziono zmiennej środowiskowej DISCORD_TOKEN. Upewnij się, że została ustawiona w panelu Render.")

bot.run(token)
