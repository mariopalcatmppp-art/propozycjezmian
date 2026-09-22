import os
import json
import time
import random
import threading
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask

# ==========================================
# 1. SERWER HTTP DLA RENDER.COM (24/7)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot działa 24/7!"

def run_http():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_http)
    t.daemon = True
    t.start()

# ==========================================
# 2. KONFIGURACJA ZMIENNYCH ZE ŚRODOWISKA
# ==========================================
TOKEN = os.environ.get("DISCORD_TOKEN")
ADMIN_DISCORD_ID = int(os.environ.get("ADMIN_DISCORD_ID", "1539023712160981013"))
SUGGESTIONS_CHANNEL_ID = int(os.environ.get("SUGGESTIONS_CHANNEL_ID", "1550764675224969237"))

DATA_FILE = "user_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Błąd podczas odczytu danych: {e}")
            return {}
    return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Błąd podczas zapisu danych: {e}")

user_data = load_data()

def get_user_profile(user_id: str):
    if user_id not in user_data:
        user_data[user_id] = {
            "points": 100,
            "xp": 0,
            "level": 1,
            "last_daily": 0,
            "messages": 0
        }
        save_data(user_data)
    return user_data[user_id]

# Intenty bota
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        synced = await self.tree.sync()
        print(f"Zsynchronizowano {len(synced)} komend slash.")

bot = MyBot()

# ==========================================
# 3. ZDARZENIA BOTA (XP Z PISANIA + LOGI)
# ==========================================
@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user} (ID: {bot.user.id})")
    print("Bot jest w pełni gotowy!")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    profile = get_user_profile(user_id)
    
    # Naliczanie XP i punktów za aktywność
    profile["messages"] += 1
    xp_gained = random.randint(5, 15)
    profile["xp"] += xp_gained
    profile["points"] += 1

    # System poziomów (XP potrzebne = poziom * 100)
    needed_xp = profile["level"] * 100
    if profile["xp"] >= needed_xp:
        profile["level"] += 1
        profile["xp"] -= needed_xp
        try:
            await message.channel.send(f"🎉 Gratulacje {message.author.mention}! Awanseujesz na **{profile['level']} poziom**!")
        except Exception:
            pass

    save_data(user_data)
    await bot.process_commands(message)

# ==========================================
# 4. FORMULARZ PROPOZYCJI (MODAL)
# ==========================================
class SuggestionModal(discord.ui.Modal, title="Zgłoś propozycję zmiana/dodatku"):
    suggestion = discord.ui.TextInput(
        label="Twoja propozycja",
        style=discord.TextStyle.paragraph,
        placeholder="Opisz dokładnie, co chcesz zasugerować...",
        required=True,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.client.get_channel(SUGGESTIONS_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="💡 Nowa Propozycja",
                description=self.suggestion.value,
                color=discord.Color.gold()
            )
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.set_footer(text=f"ID Użytkownika: {interaction.user.id}")
            
            msg = await channel.send(embed=embed)
            await msg.add_reaction("👍")
            await msg.add_reaction("👎")
            
            await interaction.response.send_message("Twoja propozycja została pomyślnie wysłana!", ephemeral=True)
        else:
            await interaction.response.send_message("Nie znaleziono kanału do wysyłania propozycji. Sprawdź konfigurację ID kanału.", ephemeral=True)

# ==========================================
# 5. KOMENDY SLASH (APP COMMANDS)
# ==========================================

# --- PROPOZYCJA ---
@bot.tree.command(name="propozycja", description="Wyślij propozycję poprawek/zmian na serwerze")
async def propozycja(interaction: discord.Interaction):
    await interaction.response.send_modal(SuggestionModal())

# --- PROFIL UŻYTKOWNIKA ---
@bot.tree.command(name="profil", description="Sprawdź swoje punkty, poziom i statystyki")
async def profil(interaction: discord.Interaction, uzytkownik: discord.Member = None):
    target = uzytkownik or interaction.user
    profile = get_user_profile(str(target.id))
    
    embed = discord.Embed(title=f"📊 Profil: {target.display_name}", color=discord.Color.blue())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="🪙 Punkty", value=f"**{profile['points']}**", inline=True)
    embed.add_field(name="⭐ Poziom", value=f"**{profile['level']}**", inline=True)
    embed.add_field(name="✨ XP", value=f"{profile['xp']} / {profile['level'] * 100}", inline=True)
    embed.add_field(name="💬 Napisane wiadomości", value=f"**{profile['messages']}**", inline=False)
    
    await interaction.response.send_message(embed=embed)

# --- DAILY (DZIENNA NAGRODA) ---
@bot.tree.command(name="daily", description="Odbierz codzienną darmową porcję punktów")
async def daily(interaction: discord.Interaction):
    profile = get_user_profile(str(interaction.user.id))
    current_time = time.time()
    
    # 24h w sekundach = 86400
    if current_time - profile["last_daily"] < 86400:
        remaining = int(86400 - (current_time - profile["last_daily"]))
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await interaction.response.send_message(f"⏳ Odbierałeś już dzisiejszą nagrodę! Wróć za **{hours}h {minutes}m**.", ephemeral=True)
        return

    reward = random.randint(50, 150)
    profile["points"] += reward
    profile["last_daily"] = current_time
    save_data(user_data)
    
    await interaction.response.send_message(f"🎁 Odebrano codzienną nagrodę! Otrzymujesz **+{reward} punktów**.")

# --- RZUT MONETĄ (COINFLIP) ---
@bot.tree.command(name="moneta", description="Zagraj o punkty w rzut monetą")
@app_commands.choices(wybor=[
    app_commands.Choice(name="Orzeł", value="orzel"),
    app_commands.Choice(name="Reszka", value="reszka")
])
async def moneta(interaction: discord.Interaction, wybor: app_commands.Choice[str], kwota: int):
    if kwota <= 0:
        await interaction.response.send_message("Kwota musi być większa niż 0!", ephemeral=True)
        return

    profile = get_user_profile(str(interaction.user.id))
    if profile["points"] < kwota:
        await interaction.response.send_message("Masz za mało punktów na ten zakład!", ephemeral=True)
        return

    wynik = random.choice(["orzel", "reszka"])
    nazwa_wynik = "Orzeł 🦅" if wynik == "orzel" else "Reszka 🪙"

    if wybor.value == wynik:
        profile["points"] += kwota
        save_data(user_data)
        await interaction.response.send_message(f"🎉 Wypadł **{nazwa_wynik}**! Wygrywasz **+{kwota}** punktów! Masz teraz {profile['points']} punktów.")
    else:
        profile["points"] -= kwota
        save_data(user_data)
        await interaction.response.send_message(f"📉 Wypadł **{nazwa_wynik}**! Przegrywasz **-{kwota}** punktów. Masz teraz {profile['points']} punktów.")

# --- PING ---
@bot.tree.command(name="ping", description="Sprawdź opóźnienie bota")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Opóźnienie: **{latency}ms**")

# --- KOMENDA ADMINA: DODAJ PUNKTY ---
@bot.tree.command(name="addpoints", description="[ADMIN] Dodaj punkty wybranemu graczonowi")
async def addpoints(interaction: discord.Interaction, uzytkownik: discord.Member, kwota: int):
    if interaction.user.id != ADMIN_DISCORD_ID:
        await interaction.response.send_message("Nie masz uprawnień administratora do tej komendy!", ephemeral=True)
        return

    profile = get_user_profile(str(uzytkownik.id))
    profile["points"] += kwota
    save_data(user_data)
    
    await interaction.response.send_message(f"✅ Dodano **{kwota}** punktów dla {uzytkownik.mention}. Aktualny stan: **{profile['points']}**.")

# ==========================================
# 6. URUCHOMIENIE BOTA
# ==========================================
if __name__ == "__main__":
    keep_alive()
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("CRITICAL ERROR: Brak zmiennej środowiskowej DISCORD_TOKEN!")
        
