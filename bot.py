import os
import json
import time
import random
import threading
import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask

# --- UTRZYMANIE SERWERA HTTP DLA RENDERA (24/7) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot działa 24/7!"

def run_http():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- KONFIGURACJA ZMIENNYCH ---
TOKEN = 'MTU1MDc5NTk0MjM3NzE2NDgzMA.GxVBSZ.Vqof7aXhhN9XjBp-nInw-jYJvWN9sodDPQk3YQ'
ADMIN_DISCORD_ID = 1539023712160981013
SUGGESTIONS_CHANNEL_ID = 1550764675224969237
DATA_FILE = "user_data.json"

# Pamięć podręczna dla ostrzeżeń
user_warnings = {}

# --- BAZA DANYCH EKONOMII ---
def load_user_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_user_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

user_db = load_user_data()

def get_user_wallet(user_id: int):
    uid = str(user_id)
    if uid not in user_db:
        user_db[uid] = {
            "coins": 100,  # Startowe monety
            "last_daily": 0,
            "last_work": 0,
            "last_hustle": 0,
            "last_crime": 0
        }
        save_user_data(user_db)
    else:
        for key in ["last_work", "last_hustle", "last_crime"]:
            if key not in user_db[uid]:
                user_db[uid][key] = 0
    return user_db[uid]

# --- WIDOKI I MODALE (PROPOZYCJE I SAPER) ---

class SaperGameView(discord.ui.View):
    def __init__(self, user_id: int, bet: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.bet = bet
        self.multiplier = 1.0
        self.safe_tiles_found = 0
        self.mines = set(random.sample(range(9), 2))
        self.revealed = set()

        for i in range(9):
            btn = discord.ui.Button(label="❓", style=discord.ButtonStyle.secondary, custom_id=f"mine_{i}", row=i // 3)
            btn.callback = self.make_callback(i)
            self.add_item(btn)

    def make_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("To nie jest Twoja gra!", ephemeral=True)
                return

            if index in self.revealed:
                await interaction.response.send_message("To pole zostało już odkryte!", ephemeral=True)
                return

            self.revealed.add(index)

            if index in self.mines:
                for child in self.children:
                    child.disabled = True
                    idx = int(child.custom_id.split("_")[1])
                    if idx in self.mines:
                        child.label = "💥"
                        child.style = discord.ButtonStyle.danger
                
                embed = discord.Embed(
                    title="💥 BOOM! Trafiłeś na minę!",
                    description=f"Przegrałeś swoją stawkę **{self.bet} monet**!",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=self)
                self.stop()
            else:
                self.safe_tiles_found += 1
                self.multiplier += 0.4

                for child in self.children:
                    idx = int(child.custom_id.split("_")[1])
                    if idx == index:
                        child.label = "💎"
                        child.style = discord.ButtonStyle.success
                        child.disabled = True

                winnings = int(self.bet * self.multiplier)

                if self.safe_tiles_found == 7:
                    wallet = get_user_wallet(self.user_id)
                    wallet["coins"] += winnings
                    save_user_data(user_db)

                    embed = discord.Embed(
                        title="🏆 NIESAMOWITE! Odkryłeś wszystkie bezpieczne pola!",
                        description=f"Wygrywasz maksymalną nagrodę **{winnings} monet** (Mnożnik x{self.multiplier:.1f})!",
                        color=discord.Color.gold()
                    )
                    for child in self.children:
                        child.disabled = True
                    await interaction.response.edit_message(embed=embed, view=self)
                    self.stop()
                else:
                    embed = discord.Embed(
                        title="💎 Trafiłeś bezpieczne pole!",
                        description=f"Aktualny mnożnik: **x{self.multiplier:.1f}**\nMożliwa wygrana: **{winnings} monet**.\n\nKlikaj dalej!",
                        color=discord.Color.green()
                    )
                    await interaction.response.edit_message(embed=embed, view=self)

        return callback

class ModalOdrzucenia(discord.ui.Modal, title="Powód Odrzucenia Propozycji"):
    powod = discord.ui.TextInput(
        label="Powód odrzucenia",
        style=discord.TextStyle.paragraph,
        placeholder="Wpisz powód odrzucenia propozycji...",
        max_length=500,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.add_field(name="❌ Status", value=f"Odrzucona przez {interaction.user.mention}", inline=False)
        embed.add_field(name="📝 Powód odrzucenia", value=self.powod.value, inline=False)

        widok = discord.ui.View.from_message(interaction.message)
        for child in widok.children:
            child.disabled = True

        await interaction.message.edit(embed=embed, view=widok)
        await interaction.response.send_message("Propozycja została odrzucona.", ephemeral=True)

class WidokDecyzjiAdmina(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🟢 Akceptuj", style=discord.ButtonStyle.success, custom_id="admin_akceptuj")
    async def akceptuj_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != ADMIN_DISCORD_ID:
            await interaction.response.send_message("Tylko wyznaczony administrator może zarządzać propozycjami!", ephemeral=True)
            return

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.add_field(name="✅ Status", value=f"Zaakceptowana przez {interaction.user.mention}", inline=False)

        for child in self.children:
            child.disabled = True

        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.send_message("Propozycja została zaakceptowana!", ephemeral=True)

    @discord.ui.button(label="🔴 Odrzuć", style=discord.ButtonStyle.danger, custom_id="admin_odrzuc")
    async def odrzuc_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != ADMIN_DISCORD_ID:
            await interaction.response.send_message("Tylko wyznaczony administrator może zarządzać propozycjami!", ephemeral=True)
            return

        await interaction.response.send_modal(ModalOdrzucenia())

class ModalPropozycji(discord.ui.Modal, title="Nowa Propozycja"):
    tytul = discord.ui.TextInput(
        label="Tytuł propozycji",
        placeholder="Wpisz krótki tytuł...",
        max_length=100
    )
    opis = discord.ui.TextInput(
        label="Opis propozycji",
        style=discord.TextStyle.paragraph,
        placeholder="Opisz dokładnie swój pomysł...",
        max_length=2000
    )

    async def on_submit(self, interaction: discord.Interaction):
        kanal = interaction.client.get_channel(SUGGESTIONS_CHANNEL_ID)
        if not kanal:
            await interaction.response.send_message("Błąd: Nie znaleziono kanału propozycji w konfiguracji!", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"💡 Propozycja: {self.tytul.value}",
            description=self.opis.value,
            color=discord.Color.blue()
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)

        msg = await kanal.send(embed=embed, view=WidokDecyzjiAdmina())
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")

        await interaction.response.send_message("Twój pomysł został pomyślnie wysłany!", ephemeral=True)

class WidokPropozycji(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💡 Zgłoś propozycję", style=discord.ButtonStyle.primary, custom_id="przycisk_propozycji_v3")
    async def przycisk_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ModalPropozycji())

class WidokLinkuFilmu(discord.ui.View):
    def __init__(self, url: str):
        super().__init__(timeout=None)
        if not (url.startswith("http://") or url.startswith("https://")):
            url = f"https://{url}"
        self.add_item(discord.ui.Button(label="▶️ Przejdź do materiału", url=url, style=discord.ButtonStyle.link))

# --- GŁÓWNA KLASA BOTA ---
class BotPropozycji(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(WidokPropozycji())
        self.add_view(WidokDecyzjiAdmina())
        await self.tree.sync()

    async def on_ready(self):
        print(f"Zalogowano jako {self.user}")

bot = BotPropozycji()

# --- KOMENDY EKONOMII (WORK / HUSTLE / CRIME / RULETKA / SAPER / DAILY) ---

@bot.tree.command(name="work", description="Uczciwa praca – bezpieczny zysk co godzinę.")
async def work_slash(interaction: discord.Interaction):
    wallet = get_user_wallet(interaction.user.id)
    now = time.time()
    cooldown = 3600

    if now - wallet["last_work"] < cooldown:
        remaining = int((cooldown - (now - wallet["last_work"])) / 60)
        await interaction.response.send_message(f"⏳ Jesteś zmęczony pracą! Odpocznij jeszcze **{remaining} min.**", ephemeral=True)
        return

    jobs = ["Koszenie trawnika u sąsiada", "Wyprowadzanie psów", "Praca na zmywaku", "Układanie towaru w sklepie", "Roznoszenie ulotek"]
    job = random.choice(jobs)
    earnings = random.randint(50, 150)

    wallet["coins"] += earnings
    wallet["last_work"] = now
    save_user_data(user_db)

    embed = discord.Embed(
        title="💼 Uczciwa Praca",
        description=f"Zrobiłeś: **{job}**\nZarobiłeś: **+{earnings} monet 🪙**\nAktualny stan konta: **{wallet['coins']} monet**.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="hustle", description="Dodatkowa fucha – możliwość zysku lub straty co 2 godz.")
async def hustle_slash(interaction: discord.Interaction):
    wallet = get_user_wallet(interaction.user.id)
    now = time.time()
    cooldown = 7200

    if now - wallet["last_hustle"] < cooldown:
        remaining = int((cooldown - (now - wallet["last_hustle"])) / 60)
        await interaction.response.send_message(f"⏳ Musisz odczekać jeszcze **{remaining} min.** przed kolejną fuchą!", ephemeral=True)
        return

    wallet["last_hustle"] = now

    if random.random() < 0.6:
        scenarios = ["Handel kartami", "Naprawa komputera", "Odnowienie mebli", "Freelance w sieci"]
        scenario = random.choice(scenarios)
        profit = random.randint(100, 300)
        wallet["coins"] += profit
        save_user_data(user_db)
        embed = discord.Embed(title="📈 Udana Fucha!", description=f"**{scenario}**!\nZysk: **+{profit} monet 🪙**\nStan konta: **{wallet['coins']} monet**.", color=discord.Color.green())
    else:
        scenarios = ["Inwestycja w słaby projekt", "Zakup uszkodzonego sprzętu", "Nietrafiona wyprzedaż"]
        scenario = random.choice(scenarios)
        loss = random.randint(50, 150)
        wallet["coins"] = max(0, wallet["coins"] - loss)
        save_user_data(user_db)
        embed = discord.Embed(title="📉 Nietrafiony Hustle!", description=f"**{scenario}**!\nStrata: **-{loss} monet 🪙**\nStan konta: **{wallet['coins']} monet**.", color=discord.Color.orange())

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="crime", description="Przestępstwo – duży zysk lub ryzyko kary co 3 godz.")
async def crime_slash(interaction: discord.Interaction):
    wallet = get_user_wallet(interaction.user.id)
    now = time.time()
    cooldown = 10800

    if now - wallet["last_crime"] < cooldown:
        remaining = int((cooldown - (now - wallet["last_crime"])) / 60)
        await interaction.response.send_message(f"⏳ Ukrywasz się! Wróć za **{remaining} min.**", ephemeral=True)
        return

    wallet["last_crime"] = now

    if random.random() < 0.3:
        profit = random.randint(300, 800)
        wallet["coins"] += profit
        save_user_data(user_db)
        embed = discord.Embed(title="🥷 Udany Skok!", description=f"Zyskałeś: **+{profit} monet 🪙**\nStan konta: **{wallet['coins']} monet**.", color=discord.Color.purple())
    else:
        fine = random.randint(100, 400)
        wallet["coins"] = max(0, wallet["coins"] - fine)
        save_user_data(user_db)
        embed = discord.Embed(title="🚨 ZŁAPANY PRZEZ POLICJĘ!", description=f"Zapłacono mandat: **-{fine} monet 🪙**\nStan konta: **{wallet['coins']} monet**.", color=discord.Color.red())

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="dzienna_nagroda", description="Odbierz darmowe monety co 24 godziny.")
async def dzienna_nagroda_slash(interaction: discord.Interaction):
    wallet = get_user_wallet(interaction.user.id)
    now = time.time()
    cooldown = 86400

    if now - wallet["last_daily"] < cooldown:
        remaining = int((cooldown - (now - wallet["last_daily"])) / 3600)
        await interaction.response.send_message(f"⏳ Odbierałeś już swoją nagrodę! Wróć za **{remaining} godz.**", ephemeral=True)
        return

    reward = random.randint(100, 250)
    wallet["coins"] += reward
    wallet["last_daily"] = now
    save_user_data(user_db)

    embed = discord.Embed(title="🎁 Dzienna Nagroda!", description=f"Otrzymujesz **{reward} monet**! 🎉\nStan konta: **{wallet['coins']} monet**.", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stan_konta", description="Sprawdza stan konta monet.")
async def stan_konta_slash(interaction: discord.Interaction, uzytkownik: discord.Member = None):
    target = uzytkownik or interaction.user
    wallet = get_user_wallet(target.id)

    embed = discord.Embed(title=f"💰 Portfel: {target.display_name}", description=f"Liczba monet: **{wallet['coins']} 🪙**", color=discord.Color.gold())
    embed.set_thumbnail(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ruletka", description="Zagraj w ruletkę!")
@app_commands.describe(stawka="Ile monet chcesz obstawić?", kolor="Wybierz kolor")
@app_commands.choices(kolor=[
    app_commands.Choice(name="🔴 Czerwony (x2)", value="czerwony"),
    app_commands.Choice(name="⚫ Czarny (x2)", value="czarny"),
    app_commands.Choice(name="🟢 Zielony (x14)", value="zielony")
])
async def ruletka_slash(interaction: discord.Interaction, stawka: int, kolor: app_commands.Choice[str]):
    if stawka <= 0:
        await interaction.response.send_message("❌ Stawka musi być większa niż 0!", ephemeral=True)
        return

    wallet = get_user_wallet(interaction.user.id)
    if wallet["coins"] < stawka:
        await interaction.response.send_message(f"❌ Posiadasz tylko {wallet['coins']} monet.", ephemeral=True)
        return

    wallet["coins"] -= stawka
    roll = random.randint(0, 36)
    winning_color = "zielony" if roll == 0 else ("czarny" if roll % 2 == 0 else "czerwony")

    won = (kolor.value == winning_color)
    multiplier = 14 if winning_color == "zielony" else 2

    if won:
        winnings = stawka * multiplier
        wallet["coins"] += winnings
        embed = discord.Embed(title="🎰 RULETKA", description=f"Wypadło: **{winning_color.upper()}** ({roll})\n🎉 **WYGRANA!** +{winnings} monet!\nStan konta: **{wallet['coins']} monet**.", color=discord.Color.green())
    else:
        embed = discord.Embed(title="🎰 RULETKA", description=f"Wypadło: **{winning_color.upper()}** ({roll})\n❌ **PRZEGRANA!** -{stawka} monet.\nStan konta: **{wallet['coins']} monet**.", color=discord.Color.red())

    save_user_data(user_db)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="saper", description="Zagraj w Sapera!")
@app_commands.describe(stawka="Ile monet chcesz postawić?")
async def saper_slash(interaction: discord.Interaction, stawka: int):
    if stawka <= 0:
        await interaction.response.send_message("❌ Stawka musi być większa niż 0!", ephemeral=True)
        return

    wallet = get_user_wallet(interaction.user.id)
    if wallet["coins"] < stawka:
        await interaction.response.send_message(f"❌ Posiadasz tylko {wallet['coins']} monet.", ephemeral=True)
        return

    wallet["coins"] -= stawka
    save_user_data(user_db)

    view = SaperGameView(interaction.user.id, stawka)
    embed = discord.Embed(title="💣 Saper", description=f"Postawiłeś **{stawka} monet**.\nOdkrywaj diamenty 💎 i unikaj min!", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="top_punkty", description="Ranking najbogatszych graczy.")
async def top_punkty_slash(interaction: discord.Interaction):
    sorted_users = sorted(user_db.items(), key=lambda x: x[1].get("coins", 0), reverse=True)[:10]
    embed = discord.Embed(title="🏆 Ranking Najbogatszych Graczy", color=discord.Color.gold())
    
    desc = ""
    for idx, (uid, data) in enumerate(sorted_users, 1):
        member = interaction.guild.get_member(int(uid))
        name = member.display_name if member else f"Użytkownik ({uid})"
        desc += f"**{idx}.** {name} — **{data.get('coins', 0)} 🪙**\n"

    embed.description = desc or "Brak danych w rankingu."
    await interaction.response.send_message(embed=embed)

# --- KOMENDY SOCIAL & UTILITY & MODERACJA ---

@bot.tree.command(name="social", description="Odnośniki do mediów społecznościowych.")
async def social_slash(interaction: discord.Interaction):
    embed = discord.Embed(title="🌐 Nasze Media Społecznościowe", color=discord.Color.purple())
    embed.add_field(name="🎬 YouTube", value="[Przejdź na YouTube](https://youtube.com/@nkt_bez_cenzury?si=seIjd17VJTIwp4VZ)", inline=False)
    embed.add_field(name="🟢 Kick", value="[Przejdź na transmisję Kick](https://kick.com/firllii)", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ping", description="Sprawdź opóźnienie bota.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Opóźnienie: {round(bot.latency * 1000)} ms.")

@bot.tree.command(name="clear", description="Usuwa określoną liczbę wiadomości.")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        await interaction.response.send_message("Liczba musi być większa od 0.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"Usunięto {len(deleted)} wiadomości.", ephemeral=True)

@bot.tree.command(name="warn", description="Udziela ostrzeżenia użytkownikowi.")
@app_command
