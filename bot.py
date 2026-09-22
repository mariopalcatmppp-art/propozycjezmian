import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime
import os
import threading
import psutil
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==============================================================================
# 🌐 WEBSERVER DLA RENDERA (Zapobiega uśpieniu usługi)
# ==============================================================================

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def log_message(self, format, *args):
        return

def run_http_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    print(f"Serwer HTTP uruchomiony na porcie {port}")
    server.serve_forever()

threading.Thread(target=run_http_server, daemon=True).start()

# ==============================================================================
# ⚙️ KONFIGURACJA I BAZY DANYCH W PAMIĘCI
# ==============================================================================

# UWAGA: token bierzemy WYŁĄCZNIE ze zmiennej środowiskowej.
# Ustaw go w Render -> Environment -> TOKEN. Nigdy nie wpisuj tokena w kodzie.
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise RuntimeError("Brak zmiennej środowiskowej TOKEN! Ustaw ją w Render -> Environment.")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "123supermaja!")

proposals_db = {}
user_economy = {}  # {user_id: {"balance": int, "level": int, "xp": int, "married": int, "cooldowns": {}}}
user_warns = {}    # {user_id: [powody/daty]}

def get_user_data(uid):
    if uid not in user_economy:
        user_economy[uid] = {"balance": 100, "level": 1, "xp": 0, "married": None, "cooldowns": {}}
    return user_economy[uid]

def add_xp(uid, amount):
    data = get_user_data(uid)
    data["xp"] += amount
    needed = data["level"] * 100
    if data["xp"] >= needed:
        data["xp"] -= needed
        data["level"] += 1
        return True
    return False

# ==============================================================================
# 💡 2. ZAAWANSOWANY SYSTEM PROPOZYCJI
# ==============================================================================

class NewProposalModal(discord.ui.Modal, title="💡 Zgłoś Nową Propozycję"):
    prop_title = discord.ui.TextInput(label="Tytuł propozycji", placeholder="Wpisz krótki tytuł...", required=True)
    prop_desc = discord.ui.TextInput(label="Opis propozycji", style=discord.TextStyle.paragraph, placeholder="Opisz swój pomysł...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"💡 Propozycja: {self.prop_title.value}",
            description=self.prop_desc.value,
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_author(name=f"Zgłoszono przez: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Status", value="⏳ Oczekuje na głosowanie", inline=False)
        embed.add_field(name="Głosy", value="👍 Za: **0** | 👎 Przeciw: **0**", inline=False)

        view = ProposalPublicView()
        await interaction.response.send_message("✅ Twoja propozycja została opublikowana!", ephemeral=True)
        msg = await interaction.channel.send(embed=embed, view=view)

        proposals_db[msg.id] = {
            "author": interaction.user.id,
            "title": self.prop_title.value,
            "desc": self.prop_desc.value,
            "za": set(),
            "przeciw": set()
        }

class ProposalTriggerView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💡 Zgłoś propozycję", style=discord.ButtonStyle.success, custom_id="trigger_proposal_btn")
    async def trigger_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(NewProposalModal())

class ProposalPublicView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="👍 Za (0)", style=discord.ButtonStyle.secondary, custom_id="prop_vote_za")
    async def vote_za(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = proposals_db.get(interaction.message.id)
        if not data: return await interaction.response.send_message("❌ Brak w bazie.", ephemeral=True)
        data["przeciw"].discard(interaction.user.id)
        data["za"].add(interaction.user.id)
        await self.update_msg(interaction, data)

    @discord.ui.button(label="👎 Przeciw (0)", style=discord.ButtonStyle.secondary, custom_id="prop_vote_przeciw")
    async def vote_przeciw(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = proposals_db.get(interaction.message.id)
        if not data: return await interaction.response.send_message("❌ Brak w bazie.", ephemeral=True)
        data["za"].discard(interaction.user.id)
        data["przeciw"].add(interaction.user.id)
        await self.update_msg(interaction, data)

    @discord.ui.button(label="🔍 Kto głosował?", style=discord.ButtonStyle.primary, custom_id="prop_admin_inspect")
    async def admin_inspect(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = proposals_db.get(interaction.message.id)
        if not data: return await interaction.response.send_message("❌ Brak w bazie.", ephemeral=True)
        za_l = ", ".join([f"<@{u}>" for u in data["za"]]) or "Brak"
        przeciw_l = ", ".join([f"<@{u}>" for u in data["przeciw"]]) or "Brak"
        embed = discord.Embed(title="🕵️ Kto głosował?", color=discord.Color.dark_purple())
        embed.add_field(name="ZA", value=za_l, inline=False)
        embed.add_field(name="PRZECIW", value=przeciw_l, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🟢 Akceptuj", style=discord.ButtonStyle.success, custom_id="prop_acc", row=1)
    async def acc(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("🔒 Brak uprawnień!", ephemeral=True)
        await self.set_status(interaction, "🟢 ZAAKCEPTOWANA", discord.Color.green())

    @discord.ui.button(label="🟡 Weryfikacja", style=discord.ButtonStyle.secondary, custom_id="prop_ver", row=1)
    async def ver(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("🔒 Brak uprawnień!", ephemeral=True)
        await self.set_status(interaction, "🟡 W TRAKCIE WERYFIKACJI", discord.Color.gold())

    @discord.ui.button(label="🔴 Odrzuć", style=discord.ButtonStyle.danger, custom_id="prop_rej", row=1)
    async def rej(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("🔒 Brak uprawnień!", ephemeral=True)
        await self.set_status(interaction, "🔴 ODRZUCONA", discord.Color.red())

    async def update_msg(self, interaction, data):
        embed = interaction.message.embeds[0]
        self.children[0].label = f"👍 Za ({len(data['za'])})"
        self.children[1].label = f"👎 Przeciw ({len(data['przeciw'])})"
        embed.set_field_at(1, name="Głosy", value=f"👍 Za: **{len(data['za'])}** | 👎 Przeciw: **{len(data['przeciw'])}**", inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    async def set_status(self, interaction, st, col):
        embed = interaction.message.embeds[0]
        embed.color = col
        embed.set_field_at(0, name="Status", value=st, inline=False)
        await interaction.response.edit_message(embed=embed, view=self)


# ==============================================================================
# 🛠️ 1. MODALE DLA UKRYTEGO PANELU ADMINA
# ==============================================================================

class AdminEcoModal(discord.ui.Modal, title="💰 Ekonomia Gracza"):
    mode = "add"
    target_id = discord.ui.TextInput(label="ID Gracza", required=True)
    amount = discord.ui.TextInput(label="Kwota monet", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            uid = int(self.target_id.value)
            amt = int(self.amount.value)
            data = get_user_data(uid)
            if self.mode == "add": data["balance"] += amt
            else: data["balance"] = max(0, data["balance"] - amt)
            await interaction.response.send_message(f"✅ Nowe saldo gracza <@{uid}>: **{data['balance']}** monet.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd: {e}", ephemeral=True)

class AdminLevelModal(discord.ui.Modal, title="⭐ Poziom / XP Gracza"):
    target_id = discord.ui.TextInput(label="ID Gracza", required=True)
    lvl = discord.ui.TextInput(label="Poziom", required=True)
    xp = discord.ui.TextInput(label="XP", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            uid, l, x = int(self.target_id.value), int(self.lvl.value), int(self.xp.value)
            data = get_user_data(uid)
            data["level"], data["xp"] = l, x
            await interaction.response.send_message(f"✅ Ustawiono Poziom {l}, XP {x} dla <@{uid}>.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd: {e}", ephemeral=True)

class AdminWarnModal(discord.ui.Modal, title="⚠️ Nadaj Ostrzeżenie"):
    target_id = discord.ui.TextInput(label="ID Gracza", required=True)
    reason = discord.ui.TextInput(label="Powód", required=False, default="Regulamin")

    async def on_submit(self, interaction: discord.Interaction):
        uid = int(self.target_id.value)
        if uid not in user_warns: user_warns[uid] = []
        user_warns[uid].append(self.reason.value)
        await interaction.response.send_message(f"⚠️ Nadano warn graczowi <@{uid}>. Razem warnów: {len(user_warns[uid])}", ephemeral=True)

class AnnouncementModal(discord.ui.Modal, title="📢 Kreator Ogłoszeń"):
    title_inp = discord.ui.TextInput(label="Tytuł ogłoszenia", required=True)
    desc_inp = discord.ui.TextInput(label="Treść", style=discord.TextStyle.paragraph, required=True)
    btn_url = discord.ui.TextInput(label="Link przycisku (opcjonalnie)", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title=self.title_inp.value, description=self.desc_inp.value, color=discord.Color.gold())
        view = None
        if self.btn_url.value:
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="🔗 Sprawdź", url=self.btn_url.value))
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Ogłoszenie wysłane!", ephemeral=True)

class AdminPunishModal(discord.ui.Modal, title="🔇 Kary (Timeout/Kick/Ban)"):
    action = "timeout"
    target_id = discord.ui.TextInput(label="ID Gracza", required=True)
    param = discord.ui.TextInput(label="Czas (minuty dla timeout) lub Powód", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            target = await interaction.guild.fetch_member(int(self.target_id.value))
            if self.action == "timeout":
                mins = int(self.param.value or 10)
                await target.timeout(datetime.timedelta(minutes=mins), reason="Panel Admina")
                await interaction.response.send_message(f"🔇 Wyciszono {target.mention} na {mins} min.", ephemeral=True)
            elif self.action == "kick":
                await target.kick(reason=self.param.value or "Wyrzucony")
                await interaction.response.send_message(f"🥾 Wyrzucono {target.mention}.", ephemeral=True)
            elif self.action == "ban":
                await target.ban(reason=self.param.value or "Zbanowany")
                await interaction.response.send_message(f"🔨 Zbanowano {target.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd kary: {e}", ephemeral=True)
            class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📊 Statystyki", style=discord.ButtonStyle.primary, row=0, custom_id="admin_stats")
    async def stats(self, interaction, btn):
        g = interaction.guild
        ram = psutil.Process().memory_info().rss / 1024 / 1024
        emb = discord.Embed(title="📊 Statystyki Projektu", color=discord.Color.blue())
        emb.add_field(name="RAM bota", value=f"{ram:.2f} MB")
        emb.add_field(name="Ping", value=f"{round(interaction.client.latency*1000)}ms")
        emb.add_field(name="Ludzie / Kanały", value=f"{g.member_count} / {len(g.channels)}")
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @discord.ui.button(label="📌 /push Propozycje", style=discord.ButtonStyle.success, row=0, custom_id="admin_push")
    async def push(self, interaction, btn):
        emb = discord.Embed(title="💡 Zgłoś pomysł!", description="Kliknij przycisk poniżej, aby wysłać propozycję.", color=discord.Color.gold())
        await interaction.channel.send(embed=emb, view=ProposalTriggerView())
        await interaction.response.send_message("✅ Wysłano przycisk propozycji na kanał!", ephemeral=True)

    @discord.ui.button(label="📢 Ogłoszenie", style=discord.ButtonStyle.secondary, row=0, custom_id="admin_ann")
    async def ann(self, interaction, btn):
        await interaction.response.send_modal(AnnouncementModal())

    @discord.ui.button(label="➕ Monety", style=discord.ButtonStyle.success, row=1, custom_id="admin_add_m")
    async def add_m(self, interaction, btn):
        m = AdminEcoModal(); m.title = "➕ Dodaj Monety"; m.mode = "add"
        await interaction.response.send_modal(m)

    @discord.ui.button(label="➖ Zabierz Monety", style=discord.ButtonStyle.danger, row=1, custom_id="admin_rem_m")
    async def rem_m(self, interaction, btn):
        m = AdminEcoModal(); m.title = "➖ Zabierz Monety"; m.mode = "remove"
        await interaction.response.send_modal(m)

    @discord.ui.button(label="⭐ Poziom / XP", style=discord.ButtonStyle.primary, row=1, custom_id="admin_lvl")
    async def lvl(self, interaction, btn):
        await interaction.response.send_modal(AdminLevelModal())

    @discord.ui.button(label="⚠️ Warny", style=discord.ButtonStyle.secondary, row=2, custom_id="admin_warn")
    async def warn(self, interaction, btn):
        await interaction.response.send_modal(AdminWarnModal())

    @discord.ui.button(label="🧹 Clear Warns", style=discord.ButtonStyle.secondary, row=2, custom_id="admin_clearw")
    async def clearw(self, interaction, btn):
        user_warns.clear()
        await interaction.response.send_message("✅ Wyczyściłem wszystkie ostrzeżenia w bazie!", ephemeral=True)

    @discord.ui.button(label="🔇 Timeout", style=discord.ButtonStyle.secondary, row=2, custom_id="admin_to")
    async def to(self, interaction, btn):
        m = AdminPunishModal(); m.action = "timeout"
        await interaction.response.send_modal(m)

    @discord.ui.button(label="🥾 Kick", style=discord.ButtonStyle.danger, row=3, custom_id="admin_kck")
    async def kck(self, interaction, btn):
        m = AdminPunishModal(); m.action = "kick"
        await interaction.response.send_modal(m)

    @discord.ui.button(label="🔨 Ban", style=discord.ButtonStyle.danger, row=3, custom_id="admin_bn")
    async def bn(self, interaction, btn):
        m = AdminPunishModal(); m.action = "ban"
        await interaction.response.send_modal(m)

    @discord.ui.button(label="🛑 Kill-Switch", style=discord.ButtonStyle.danger, row=3, custom_id="admin_kill")
    async def kill(self, interaction, btn):
        await interaction.response.send_message("🛑 Wyłączam bota bezpieczeństwem...", ephemeral=True)
        await interaction.client.close()
        



# ==============================================================================
# 🎰 3. HAZARD I MINI-GRY (PRZYCISKI I INTERAKCJE)
# ==============================================================================

class SaperView(discord.ui.View):
    def __init__(self, user_id, bet):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.bet = bet
        self.grid = random.sample(["💎"]*5 + ["💣"]*4, 9)
        self.revealed = [False]*9
        self.score = 0
        for i in range(9):
            self.add_item(SaperButton(i))

class SaperButton(discord.ui.Button):
    def __init__(self, idx):
        super().__init__(label="⬛", row=idx//3, custom_id=f"saper_{idx}")
        self.idx = idx

    async def callback(self, interaction: discord.Interaction):
        view: SaperView = self.view
        if interaction.user.id != view.user_id: return await interaction.response.send_message("Nie Twoja gra!", ephemeral=True)
        val = view.grid[self.idx]
        if val == "💣":
            self.label = "💣"; self.style = discord.ButtonStyle.danger; self.disabled = True
            for child in view.children: child.disabled = True
            get_user_data(view.user_id)["balance"] = max(0, get_user_data(view.user_id)["balance"] - view.bet)
            await interaction.response.edit_message(content=f"💥 Trafiłeś na minę! Straciłeś {view.bet} monet.", view=view)
        else:
            self.label = "💎"; self.style = discord.ButtonStyle.success; self.disabled = True
            view.score += 1
            if view.score >= 5:
                win = view.bet * 2
                get_user_data(view.user_id)["balance"] += win
                for child in view.children: child.disabled = True
                await interaction.response.edit_message(content=f"🎉 Wygrana! Zdobywasz {win} monet!", view=view)
            else:
                await interaction.response.edit_message(view=view)

class ZdrapkaView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.fields = random.choices(["💰", "💎", "❌"], k=3)
        for i in range(3):
            self.add_item(ZdrapkaBtn(i))

class ZdrapkaBtn(discord.ui.Button):
    def __init__(self, idx):
        super().__init__(label="❓", row=0, custom_id=f"zdr_{idx}")
        self.idx = idx

    async def callback(self, interaction):
        view = self.view
        if interaction.user.id != view.user_id: return await interaction.response.send_message("Nie Twoje!", ephemeral=True)
        res = view.fields[self.idx]
        self.label = res; self.disabled = True
        all_done = all(c.disabled for c in view.children)
        if all_done:
            data = get_user_data(view.user_id)
            if view.fields.count("💰") >= 2 or view.fields.count("💎") >= 2:
                data["balance"] += 150
                msg = "🎉 Zdrabandowa wygrana (+150 monet)!"
            else:
                msg = "😢 Nic z tego."
            await interaction.response.edit_message(content=msg, view=view)
        else:
            await interaction.response.edit_message(view=view)

# ==============================================================================
# 🛒 SKLEP, MAŁŻEŃSTWA, BOT
# ==============================================================================

shop_items = {
    "kolor_zolty": {"name": "Żółty nick (rola)", "cost": 500, "role_id": None},
    "vip": {"name": "Ranga VIP", "cost": 2000, "role_id": None}
}

marry_requests = {}

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(AdminPanelView())
        self.add_view(ProposalTriggerView())
        self.add_view(ProposalPublicView())
        await self.tree.sync()

bot = MyBot()

@bot.event
async def on_ready():
    print(f"Zalogowano jako {bot.user}")


# --- UKRYTY PANEL ADMINA ---
@bot.tree.command(name="admin", description="Ukryty panel administratora")
@app_commands.describe(haslo="Hasło administratora")
async def admin(interaction: discord.Interaction, haslo: str):
    if haslo == ADMIN_PASSWORD:
        emb = discord.Embed(title="🛠️ Ukryty Panel Admina", description="Wybierz operację:", color=discord.Color.dark_red())
        await interaction.response.send_message(embed=emb, view=AdminPanelView(), ephemeral=True)
    else:
        await interaction.response.send_message("❌ Złe hasło!", ephemeral=True)


# --- 3. HAZARD I MINI-GRY ---
@bot.tree.command(name="saper", description="Plansza 3x3 na przyciskach")
async def saper(interaction: discord.Interaction, stawka: int):
    data = get_user_data(interaction.user.id)
    if data["balance"] < stawka or stawka <= 0: return await interaction.response.send_message("❌ Brak środków!", ephemeral=True)
    await interaction.response.send_message(f"💣 Saper o stawkę {stawka}:", view=SaperView(interaction.user.id, stawka))

@bot.tree.command(name="ruletka", description="Gra na kolory (Czerwony, Czarny, Zielony)")
@app_commands.choices(kolor=[
    app_commands.Choice(name="Czerwony (2x)", value="red"),
    app_commands.Choice(name="Czarny (2x)", value="black"),
    app_commands.Choice(name="Zielony (14x)", value="green")
])
async def ruletka(interaction: discord.Interaction, stawka: int, kolor: app_commands.Choice[str]):
    data = get_user_data(interaction.user.id)
    if data["balance"] < stawka or stawka <= 0: return await interaction.response.send_message("❌ Brak środków!", ephemeral=True)
    roll = random.choices(["red", "black", "green"], weights=[45, 45, 10])[0]
    data["balance"] -= stawka
    if roll == kolor.value:
        mult = 14 if roll == "green" else 2
        win = stawka * mult
        data["balance"] += win
        res = f"🎉 Wylosowano {roll}! Wygrana: {win} monet."
    else:
        res = f"😢 Wylosowano {roll}. Przegrana."
    await interaction.response.send_message(res)

@bot.tree.command(name="zdrapka", description="Zdrapywanie 3 pól")
async def zdrapka(interaction: discord.Interaction):
    data = get_user_data(interaction.user.id)
    if data["balance"] < 50: return await interaction.response.send_message("❌ Koszt zdrapki to 50 monet!", ephemeral=True)
    data["balance"] -= 50
    await interaction.response.send_message("🎫 Zdrap 3 pola:", view=ZdrapkaView(interaction.user.id))

@bot.tree.command(name="moneta", description="CoinFlip o monety")
@app_commands.choices(wybor=[app_commands.Choice(name="Orzeł", value="orzel"), app_commands.Choice(name="Reszka", value="reszka")])
async def moneta_gam(interaction: discord.Interaction, stawka: int, wybor: app_commands.Choice[str]):
    data = get_user_data(interaction.user.id)
    if data["balance"] < stawka: return await interaction.response.send_message("❌ Brak monet!", ephemeral=True)
    res = random.choice(["orzel", "reszka"])
    data["balance"] -= stawka
    if res == wybor.value:
        data["balance"] += stawka * 2
        msg = f"🪙 Wypadł {res}! Wygrywasz {stawka*2}!"
    else:
        msg = f"🪙 Wypadł {res}. Przegrywasz."
    await interaction.response.send_message(msg)

@bot.tree.command(name="pojedynki", description="Pojedynek na monety z innym graczem")
async def pojedynki(interaction: discord.Interaction, uzytkownik: discord.Member, stawka: int):
    if uzytkownik.bot or uzytkownik == interaction.user: return await interaction.response.send_message("❌ Niepoprawny przeciwnik.", ephemeral=True)
    d1 = get_user_data(interaction.user.id); d2 = get_user_data(uzytkownik.id)
    if d1["balance"] < stawka or d2["balance"] < stawka: return await interaction.response.send_message("❌ Ktoś nie ma środków.", ephemeral=True)
    winner = random.choice([interaction.user, uzytkownik])
    loser = uzytkownik if winner == interaction.user else interaction.user
    get_user_data(winner.id)["balance"] += stawka
    get_user_data(loser.id)["balance"] -= stawka
    await interaction.response.send_message(f"⚔️ Pojedynek wygrywa {winner.mention}! Zyskuje {stawka} monet.")

@bot.tree.command(name="blackjack", description="Oczko na przyciskach")
async def blackjack(interaction: discord.Interaction, stawka: int):
    data = get_user_data(interaction.user.id)
    if data["balance"] < stawka: return await interaction.response.send_message("❌ Brak środków!", ephemeral=True)
    c1, c2 = random.randint(2,11), random.randint(2,11)
    await interaction.response.send_message(f"🃏 Blackjack o {stawka}. Twoje karty: **{c1}, {c2}** (Suma: {c1+c2}). (Uproszczona wersja beta)")


# --- 4. EKONOMIA, SKLEP I RELACJE ---
@bot.tree.command(name="work", description="Zarób monety")
async def work(interaction: discord.Interaction):
    uid = interaction.user.id
    data = get_user_data(uid)
    now = datetime.datetime.now().timestamp()
    if now - data["cooldowns"].get("work", 0) < 60:
        return await interaction.response.send_message("⏳ Poczekaj minutę!", ephemeral=True)
    data["cooldowns"]["work"] = now
    earn = random.randint(30, 90)
    data["balance"] += earn
    add_xp(uid, 15)
    await interaction.response.send_message(f"💼 Zarobiłeś **{earn}** monet!")

@bot.tree.command(name="hustle", description="Szybki biznes")
async def hustle(interaction: discord.Interaction):
    uid = interaction.user.id; data = get_user_data(uid)
    earn = random.randint(50, 150)
    data["balance"] += earn
    add_xp(uid, 25)
    await interaction.response.send_message(f"🔥 Hustle przyniosło **{earn}** monet!")

@bot.tree.command(name="crime", description="Ryzykowne kradzieże")
async def crime(interaction: discord.Interaction):
    uid = interaction.user.id; data = get_user_data(uid)
    if random.random() < 0.4:
        loss = random.randint(20, 80)
        data["balance"] = max(0, data["balance"] - loss)
        await interaction.response.send_message(f"🚨 Wpadłeś! Straciłeś {loss} monet.")
    else:
        gain = random.randint(100, 300)
        data["balance"] += gain
        await interaction.response.send_message(f"🕶️ Skok udany! Zyskasz {gain} monet.")

@bot.tree.command(name="daily", description="Codzienna nagroda")
async def daily(interaction: discord.Interaction):
    data = get_user_data(interaction.user.id)
    data["balance"] += 250
    await interaction.response.send_message("🎁 Odbierasz dzienną nagrodę (+250 monet)!")

@bot.tree.command(name="rob", description="Kradzież od gracza")
async def rob(interaction: discord.Interaction, uzytkownik: discord.Member):
    d1 = get_user_data(interaction.user.id); d2 = get_user_data(uzytkownik.id)
    if d2["balance"] < 50: return await interaction.response.send_message("❌ Ma za mało monet.", ephemeral=True)
    if random.random() < 0.5:
        amt = random.randint(10, min(100, d2["balance"]))
        d2["balance"] -= amt; d1["balance"] += amt
        await interaction.response.send_message(f"🥷 UKRADEO! Masz {amt} monet od {uzytkownik.mention}.")
    else:
        fine = 50; d1["balance"] = max(0, d1["balance"] - fine)
        await interaction.response.send_message(f"🚔 Policja złapała Cię na gorącym uczynku! -{fine} monet.")

@bot.tree.command(name="stan_konta", description="Sprawdź stan portfela")
async def stan_konta(interaction: discord.Interaction, uzytkownik: discord.Member = None):
    target = uzytkownik or interaction.user
    data = get_user_data(target.id)
    await interaction.response.send_message(f"💳 Stan konta **{target.display_name}**: **{data['balance']}** monet.")

@bot.tree.command(name="przelej", description="Przelej monety komuś")
async def przelej(interaction: discord.Interaction, uzytkownik: discord.Member, kwota: int):
    if kwota <= 0: return
    d1 = get_user_data(interaction.user.id); d2 = get_user_data(uzytkownik.id)
    if d1["balance"] < kwota: return await interaction.response.send_message("❌ Brak środków.", ephemeral=True)
    d1["balance"] -= kwota; d2["balance"] += kwota
    await interaction.response.send_message(f"💸 Przelano {kwota} monet do {uzytkownik.mention}.")

@bot.tree.command(name="shop", description="Wyświetl sklep")
async def shop(interaction: discord.Interaction):
    emb = discord.Embed(title="🛒 Sklep Serwerowy", color=discord.Color.green())
    for k, v in shop_items.items():
        emb.add_field(name=v["name"], value=f"Koszt: **{v['cost']}** monet (Kupuj przez `/buy {k}`)", inline=False)
    await interaction.response.send_message(embed=emb)

@bot.tree.command(name="buy", description="Kup przedmiot ze sklepu")
async def buy(interaction: discord.Interaction, przedmiot: str):
    if przedmiot not in shop_items: return await interaction.response.send_message("❌ Nie ma takiego przedmiotu.", ephemeral=True)
    item = shop_items[przedmiot]; data = get_user_data(interaction.user.id)
    if data["balance"] < item["cost"]: return await interaction.response.send_message("❌ Brak środków.", ephemeral=True)
    data["balance"] -= item["cost"]
    await interaction.response.send_message(f"✅ Zakupiono: **{item['name']}**!")

@bot.tree.command(name="marry", description="Oświadź się komuś")
async def marry(interaction: discord.Interaction, uzytkownik: discord.Member):
    marry_requests[uzytkownik.id] = interaction.user.id
    await interaction.response.send_message(f"💍 {interaction.user.mention} oświadcza się {uzytkownik.mention}! Napisz `/accept_marry` aby przyjąć.")

@bot.tree.command(name="accept_marry", description="Przyjmij oświadczyny")
async def accept_marry(interaction: discord.Interaction):
    uid = interaction.user.id
    if uid not in marry_requests: return await interaction.response.send_message("❌ Brak oświadczyn.", ephemeral=True)
    partner_id = marry_requests.pop(uid)
    get_user_data(uid)["married"] = partner_id
    get_user_data(partner_id)["married"] = uid
    await interaction.response.send_message(f"🥂 Jesteście małżeństwem z <@{partner_id}>!")

@bot.tree.command(name="divorce", description="Weź rozwód")
async def divorce(interaction: discord.Interaction):
    data = get_user_data(interaction.user.id)
    data["married"] = None
    await interaction.response.send_message("💔 Rozwód wzięty.")


# --- 5. POZIOMY, PROFIL I FUN ---
@bot.tree.command(name="profil", description="Karta profilu")
async def profil(interaction: discord.Interaction, uzytkownik: discord.Member = None):
    t = uzytkownik or interaction.user
    d = get_user_data(t.id)
    m_info = f"<@{d['married']}>" if d["married"] else "Brak"
    emb = discord.Embed(title=f"👤 Profil: {t.display_name}", color=discord.Color.blue())
    emb.add_field(name="Poziom", value=str(d["level"]))
    emb.add_field(name="XP", value=str(d["xp"]))
    emb.add_field(name="Monety", value=str(d["balance"]))
    emb.add_field(name="Małżeństwo", value=m_info)
    emb.set_thumbnail(url=t.display_avatar.url)
    await interaction.response.send_message(embed=emb)

@bot.tree.command(name="top", description="Ranking bogaczy i aktywnych")
async def top(interaction: discord.Interaction):
    sorted_u = sorted(user_economy.items(), key=lambda x: x[1]["balance"], reverse=True)[:5]
    desc = "\n".join([f"#{i+1} <@{u[0]}> – {u[1]['balance']} monet (Lvl {u[1]['level']})" for i, u in enumerate(sorted_u)]) or "Brak danych"
    emb = discord.Embed(title="🏆 TOP Bogaczy", description=desc, color=discord.Color.gold())
    await interaction.response.send_message(embed=emb)

@bot.tree.command(name="kulka", description="Magiczna kula 8-Ball")
async def kulka(interaction: discord.Interaction, pytanie: str):
    await interaction.response.send_message(f"❓ {pytanie}\n🔮 {random.choice(['Tak!', 'Nie.', 'Prawdopodobnie.'])}")

@bot.tree.command(name="kamien_papier", description="KPN")
@app_commands.choices(wybor=[
    app_commands.Choice(name="Kamień 🪨", value="Kamień"),
    app_commands.Choice(name="Papier 📄", value="Papier"),
    app_commands.Choice(name="Nożyce ✂️", value="Nożyce")
])
async def kpn(interaction: discord.Interaction, wybor: app_commands.Choice[str]):
    bc = random.choice(["Kamień", "Papier", "Nożyce"])
    res = "Remis!" if wybor.value == bc else ("Wygrywasz!" if (wybor.value=="Kamień" and bc=="Nożyce") or (wybor.value=="Papier" and bc=="Kamień") or (wybor.value=="Nożyce" and bc=="Papier") else "Przegrywasz!")
    await interaction.response.send_message(f"Ty: {wybor.value} | Bot: {bc} -> {res}")

@bot.tree.command(name="statek_milosny", description="Kalkulator dopasowania")
async def statek_milosny(interaction: discord.Interaction, osoba1: discord.Member, osoba2: discord.Member):
    await interaction.response.send_message(f"❤️ Dopasowanie {osoba1.display_name} i {osoba2.display_name}: **{random.randint(0,100)}%**")

@bot.tree.command(name="losuj", description="Losuj liczbę od-do")
async def losuj(interaction: discord.Interaction, start: int = 1, koniec: int = 100):
    await interaction.response.send_message(f"🎲 Wylosowano: **{random.randint(start, koniec)}**")

@bot.tree.command(name="avatar", description="Pobierz avatar")
async def avatar(interaction: discord.Interaction, uzytkownik: discord.Member = None):
    t = uzytkownik or interaction.user
    emb = discord.Embed(title=f"Avatar {t.display_name}").set_image(url=t.display_avatar.url)
    await interaction.response.send_message(embed=emb)

@bot.tree.command(name="mem", description="Losowy żart")
async def mem(interaction: discord.Interaction):
    zarty = [
        "Dlaczego programiści wolą ciemny motyw? Bo światło przyciąga robaki (bugi)! 🐛",
        "Pytanie: Ile programistów potrzeba do zmiany żarówki? Odpowiedź: Żadnego, to problem sprzętowy. 💡"
    ]
    await interaction.response.send_message(f"😄 {random.choice(zarty)}")


# --- URUCHOMIENIE BOTA ---
bot.run(TOKEN)
