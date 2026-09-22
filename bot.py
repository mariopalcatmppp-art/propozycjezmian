import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime
import os
import threading
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
        return  # Wyłączenie zalewania konsoli logami HTTP

def run_http_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHTTPRequestHandler)
    print(f"Serwer HTTP uruchomiony na porcie {port}")
    server.serve_forever()

# Uruchomienie serwera HTTP w osobnym wątku
threading.Thread(target=run_http_server, daemon=True).start()

# ==============================================================================
# ⚙️ KONFIGURACJA BOTA
# ==============================================================================

TOKEN = os.environ.get("TOKEN", "MTU1MDc5NTk0MjM3NzE2NDgzMA.GtYpNN.WlLzQxxCarQsFG9ltBuPKbdVaI5avjGfmgd-Tk")
ADMIN_PASSWORD = "123supermaja!"

# Baza danych w pamięci RAM
proposals_db = {}

# ==============================================================================
# 💡 SYSTEM PROPOZYCJI (MODALE I PRZYCISKI)
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
        embed.set_footer(text="Głosowanie jest anonimowe dla społeczności.")

        view = ProposalPublicView()
        await interaction.response.send_message("✅ Twoja propozycja została opublikowana!", ephemeral=True)
        msg = await interaction.channel.send(embed=embed, view=view)

        proposals_db[msg.id] = {
            "author": interaction.user.mention,
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
        if not data:
            await interaction.response.send_message("❌ Nie odnaleziono propozycji w bazie.", ephemeral=True)
            return

        user_id = interaction.user.id
        data["przeciw"].discard(user_id)
        data["za"].add(user_id)
        await self.update_proposal_msg(interaction)

    @discord.ui.button(label="👎 Przeciw (0)", style=discord.ButtonStyle.secondary, custom_id="prop_vote_przeciw")
    async def vote_przeciw(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = proposals_db.get(interaction.message.id)
        if not data:
            await interaction.response.send_message("❌ Nie odnaleziono propozycji w bazie.", ephemeral=True)
            return

        user_id = interaction.user.id
        data["za"].discard(user_id)
        data["przeciw"].add(user_id)
        await self.update_proposal_msg(interaction)

    @discord.ui.button(label="🔍 Kto głosował? (Tylko Admin)", style=discord.ButtonStyle.primary, custom_id="prop_admin_inspect")
    async def admin_inspect(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = proposals_db.get(interaction.message.id)
        if not data:
            await interaction.response.send_message("❌ Brak danych w bazie.", ephemeral=True)
            return

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🔒 Ta opcja jest widoczna wyłącznie dla Właściciela!", ephemeral=True)
            return

        za_list = ", ".join([f"<@{uid}>" for uid in data["za"]]) or "Brak"
        przeciw_list = ", ".join([f"<@{uid}>" for uid in data["przeciw"]]) or "Brak"

        embed = discord.Embed(title="🕵️ Tajny Wgląd Admina – Lista Głosujących", color=discord.Color.dark_purple())
        embed.add_field(name=f"👍 Głosowali ZA ({len(data['za'])}):", value=za_list, inline=False)
        embed.add_field(name=f"👎 Głosowali PRZECIW ({len(data['przeciw'])}):", value=przeciw_list, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🟢 Akceptuj", style=discord.ButtonStyle.success, custom_id="prop_admin_accept", row=1)
    async def admin_accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🔒 Brak uprawnień administratora!", ephemeral=True)
            return
        await self.set_status(interaction, "🟢 ZAAKCEPTOWANA", discord.Color.green())

    # POPRAWIONE: Użyto Style.secondary zamiast Style.warning
    @discord.ui.button(label="🟡 W weryfikacji", style=discord.ButtonStyle.secondary, custom_id="prop_admin_verify", row=1)
    async def admin_verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🔒 Brak uprawnień administratora!", ephemeral=True)
            return
        await self.set_status(interaction, "🟡 W TRAKCIE WERYFIKACJI", discord.Color.gold())

    @discord.ui.button(label="🔴 Odrzuć", style=discord.ButtonStyle.danger, custom_id="prop_admin_reject", row=1)
    async def admin_reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("🔒 Brak uprawnień administratora!", ephemeral=True)
            return
        await self.set_status(interaction, "🔴 ODRZUCONA", discord.Color.red())

    async def update_proposal_msg(self, interaction: discord.Interaction):
        data = proposals_db[interaction.message.id]
        embed = interaction.message.embeds[0]
        
        self.children[0].label = f"👍 Za ({len(data['za'])})"
        self.children[1].label = f"👎 Przeciw ({len(data['przeciw'])})"
        
        embed.set_field_at(1, name="Głosy", value=f"👍 Za: **{len(data['za'])}** | 👎 Przeciw: **{len(data['przeciw'])}**", inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

    async def set_status(self, interaction: discord.Interaction, status_text: str, color: discord.Color):
        embed = interaction.message.embeds[0]
        embed.color = color
        embed.set_field_at(0, name="Status", value=status_text, inline=False)
        await interaction.response.edit_message(embed=embed, view=self)


# ==============================================================================
# 🛡️ MODALE I FUNKCJE MODERACYJNE ADMINA
# ==============================================================================

class BanModal(discord.ui.Modal, title="🔨 Banowanie Użytkownika"):
    user_id = discord.ui.TextInput(label="ID Użytkownika", placeholder="Wklej ID osoby do zbanowania...", required=True)
    reason = discord.ui.TextInput(label="Powód bana", placeholder="Wpisz powód...", required=False, default="Złamanie regulaminu")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            target = await interaction.guild.fetch_member(int(self.user_id.value))
            await target.ban(reason=self.reason.value)
            await interaction.response.send_message(f"✅ Użytkownik {target.mention} został zbanowany. Powód: {self.reason.value}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd podczas banowania: {e}", ephemeral=True)

class KickModal(discord.ui.Modal, title="🥾 Wyrzucanie (Kick) Użytkownika"):
    user_id = discord.ui.TextInput(label="ID Użytkownika", placeholder="Wklej ID osoby...", required=True)
    reason = discord.ui.TextInput(label="Powód wyrzucenia", placeholder="Wpisz powód...", required=False, default="Wyrzucony przez Admina")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            target = await interaction.guild.fetch_member(int(self.user_id.value))
            await target.kick(reason=self.reason.value)
            await interaction.response.send_message(f"✅ Użytkownik {target.mention} został wyrzucony z serwera.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd podczas wyrzucania: {e}", ephemeral=True)

class MuteModal(discord.ui.Modal, title="🔇 Wyciszanie (Timeout) Użytkownika"):
    user_id = discord.ui.TextInput(label="ID Użytkownika", placeholder="Wklej ID...", required=True)
    duration = discord.ui.TextInput(label="Czas w minutach", placeholder="Np. 10", required=True)
    reason = discord.ui.TextInput(label="Powód", placeholder="Wpisz powód...", required=False, default="Przerwa od czatu")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            target = await interaction.guild.fetch_member(int(self.user_id.value))
            minutes = int(self.duration.value)
            until = datetime.timedelta(minutes=minutes)
            await target.timeout(until, reason=self.reason.value)
            await interaction.response.send_message(f"✅ Użytkownik {target.mention} został wyciszony na **{minutes}** minut.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Błąd wyciszania: {e}", ephemeral=True)

class ClearChatModal(discord.ui.Modal, title="🧹 Czyszczenie Wiadomości"):
    amount = discord.ui.TextInput(label="Liczba wiadomości do usunięcia", placeholder="Np. 20", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            count = int(self.amount.value)
            await interaction.response.defer(ephemeral=True)
            deleted = await interaction.channel.purge(limit=count)
            await interaction.followup.send(f"✅ Usunięto **{len(deleted)}** wiadomości.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Błąd czyszczenia: {e}", ephemeral=True)


# ==============================================================================
# 🛠️ PANEL ADMINISTRATORA (PRZYCISKI)
# ==============================================================================

class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔨 Banuj", style=discord.ButtonStyle.danger, custom_id="adm_ban", row=0)
    async def btn_ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BanModal())

    @discord.ui.button(label="🥾 Wyrzuć (Kick)", style=discord.ButtonStyle.danger, custom_id="adm_kick", row=0)
    async def btn_kick(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(KickModal())

    @discord.ui.button(label="🔇 Wycisz (Timeout)", style=discord.ButtonStyle.secondary, custom_id="adm_mute", row=0)
    async def btn_mute(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MuteModal())

    @discord.ui.button(label="🧹 Wyczyść Czat", style=discord.ButtonStyle.primary, custom_id="adm_clear", row=1)
    async def btn_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ClearChatModal())

    @discord.ui.button(label="📌 Przycisk Propozycji (/push)", style=discord.ButtonStyle.success, custom_id="adm_push_prop", row=1)
    async def btn_push_prop(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="💡 Chcesz coś ulepszyć na serwerze?",
            description="Kliknij poniższy przycisk, aby wysłać swoją propozycję! Społeczność będzie mogła na nią zagłosować.",
            color=discord.Color.gold()
        )
        await interaction.channel.send(embed=embed, view=ProposalTriggerView())
        await interaction.response.send_message("✅ Wysłąno panel propozycji na obecny kanał!", ephemeral=True)

    @discord.ui.button(label="📊 Statystyki Projektu", style=discord.ButtonStyle.primary, custom_id="adm_stats", row=2)
    async def btn_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        embed = discord.Embed(title="📊 Statystyki Projektu", color=discord.Color.blue())
        embed.add_field(name="Serwer", value=guild.name, inline=True)
        embed.add_field(name="Liczba Członków", value=str(guild.member_count), inline=True)
        embed.add_field(name="Ping Bota", value=f"{round(interaction.client.latency * 1000)} ms", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ==============================================================================
# 🤖 KOD GŁÓWNY BOTA
# ==============================================================================

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
    print(f"Zalogowano jako {bot.user} (ID: {bot.user.id})")
    await bot.change_presence(activity=discord.Game(name="Użyj /help do zabawy!"))


# --- UKRYTA KOMENDA ADMINA ---
@bot.tree.command(name="admin", description="Dostęp do ukrytego panelu administratora")
@app_commands.describe(haslo="Hasło autoryzacyjne")
async def admin(interaction: discord.Interaction, haslo: str):
    if haslo == ADMIN_PASSWORD:
        embed = discord.Embed(
            title="🛠️ Ukryty Panel Administratora",
            description="Witaj w prywatnym centrum zarządzania serwerem i moderacją. Żaden użytkownik nie widzi tej wiadomości.",
            color=discord.Color.dark_red()
        )
        await interaction.response.send_message(embed=embed, view=AdminPanelView(), ephemeral=True)
    else:
        await interaction.response.send_message("❌ Niepoprawne hasło!", ephemeral=True)


# --- PUBLICZNE KOMENDY ROZRYWKOWE ---
@bot.tree.command(name="help", description="Wyświetla listę wszystkich dostępnych komend")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Centrum Pomocy i Rozrywki",
        description="Oto spis wszystkich komend dostępnych dla każdego użytkownika:",
        color=discord.Color.blue()
    )
    embed.add_field(name="🎲 /kostka", value="Rzuca kością sześciościenną.", inline=True)
    embed.add_field(name="🪙 /moneta", value="Rzuca monetą (Orzeł czy Reszka).", inline=True)
    embed.add_field(name="🔮 /kulka [pytanie]", value="Zapytaj magiczną kulkę 8-Ball.", inline=True)
    embed.add_field(name="✂️ /kamien_papier [wybor]", value="Zagraj z botem w Kamień, Papier, Nożyce.", inline=True)
    embed.add_field(name="❤️ /statek_milosny [osoba1] [osoba2]", value="Kalkulator dopasowania pary.", inline=True)
    embed.add_field(name="🖼️ /avatar [uzytkownik]", value="Wyświetla zdjęcie profilowe.", inline=True)
    embed.add_field(name="😄 /mem", value="Generuje losowy żart.", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="kostka", description="Rzuć kością 6-ścienną")
async def kostka(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎲 **{interaction.user.display_name}** wyrzuca: **{random.randint(1, 6)}**!")

@bot.tree.command(name="moneta", description="Rzuć monetą")
async def moneta(interaction: discord.Interaction):
    await interaction.response.send_message(f"🪙 Wynik rzutu: **{random.choice(['Orzeł', 'Reszka'])}**!")

@bot.tree.command(name="kulka", description="Zapytaj magiczną kulkę 8-Ball")
async def kulka(interaction: discord.Interaction, pytanie: str):
    odpowiedzi = ["Tak!", "Nie.", "Prawdopodobnie.", "Moim zdaniem nie.", "Zapytaj później."]
    await interaction.response.send_message(f"❓ **Pytanie:** {pytanie}\n🔮 **Odpowiedź:** {random.choice(odpowiedzi)}")

@bot.tree.command(name="kamien_papier", description="Gra w Kamień, Papier, Nożyce")
@app_commands.choices(wybor=[
    app_commands.Choice(name="Kamień 🪨", value="Kamień"),
    app_commands.Choice(name="Papier 📄", value="Papier"),
    app_commands.Choice(name="Nożyce ✂️", value="Nożyce")
])
async def kamien_papier(interaction: discord.Interaction, wybor: app_commands.Choice[str]):
    bot_choice = random.choice(["Kamień", "Papier", "Nożyce"])
    user_choice = wybor.value
    if user_choice == bot_choice:
        res = "🤝 Remis!"
    elif (user_choice == "Kamień" and bot_choice == "Nożyce") or (user_choice == "Papier" and bot_choice == "Kamień") or (user_choice == "Nożyce" and bot_choice == "Paper"):
        res = "🎉 Wygrałeś!"
    else:
        res = "💻 Bot wygrał!"
    await interaction.response.send_message(f"Twój wybór: **{user_choice}** | Bot: **{bot_choice}**\nWynik: **{res}**")

@bot.tree.command(name="statek_milosny", description="Kalkulator dopasowania")
async def statek_milosny(interaction: discord.Interaction, osoba1: discord.Member, osoba2: discord.Member):
    procent = random.randint(0, 100)
    await interaction.response.send_message(f"❤️ Dopasowanie **{osoba1.display_name}** i **{osoba2.display_name}** wynosi **{procent}%**!")

@bot.tree.command(name="avatar", description="Pobierz avatar użytkownika")
async def avatar(interaction: discord.Interaction, uzytkownik: discord.Member = None):
    target = uzytkownik or interaction.user
    embed = discord.Embed(title=f"Avatar użytkownika {target.display_name}")
    embed.set_image(url=target.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="mem", description="Losowy żart")
async def mem(interaction: discord.Interaction):
    zarty = [
        "Dlaczego programiści wolą ciemny motyw? Bo światło przyciąga robaki (b
