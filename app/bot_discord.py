# -*- coding: utf-8 -*-
import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request

SERVEUR = os.environ.get("DNAREADER_SERVEUR", "").rstrip("/")
ADMIN = os.environ.get("DNAREADER_ADMIN", "")
JETON = os.environ.get("DISCORD_TOKEN", "")
GUILDE = os.environ.get("DISCORD_GUILD", "")
ROLE_ABONNE = os.environ.get("DISCORD_ROLE_ABONNE", "")

JOURS_ABONNE = 31
PERIODE = 6 * 3600
PREFIXE_COMMANDE = "!"


def _appelle(route: str, corps: dict) -> dict:
    if not SERVEUR or not ADMIN:
        return {"ok": False, "raison": "serveur ou jeton d'administration absent"}
    req = urllib.request.Request(
        SERVEUR + route, json.dumps({**corps, "admin": ADMIN}).encode(),
        {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"ok": False, "raison": f"refuse par le serveur ({e.code})"}
    except Exception as e:
        return {"ok": False, "raison": str(e)}


def boutique_etat() -> dict:
    if not SERVEUR:
        return {"ok": False, "raison": "serveur de licences non configure"}
    try:
        with urllib.request.urlopen(SERVEUR + "/boutique/etat", timeout=15) as r:
            d = json.loads(r.read().decode("utf-8"))
            d["ok"] = True
            return d
    except Exception as e:
        return {"ok": False, "raison": str(e)}


def note_de(membre) -> str:
    return "DNAR-" + membre.name


def cle_de(discord_id, jours=0) -> dict:
    return _appelle("/licence/discord",
                    {"note": str(discord_id), "jours": jours})


def coupe(discord_id) -> dict:
    return _appelle("/licence/discord/retirer", {"note": str(discord_id)})


def _jours(r) -> str:
    j = r.get("jours_restants")
    return f"{j:.0f} jour(s)" if isinstance(j, (int, float)) else "durée inconnue"


def demarre():
    try:
        import discord
        from discord import app_commands
    except ImportError:
        raise SystemExit(
            "discord.py n'est pas installé :\n"
            "    pip install -U discord.py")

    if not JETON:
        raise SystemExit("DISCORD_TOKEN n'est pas défini.")
    if not GUILDE or not ROLE_ABONNE:
        raise SystemExit("DISCORD_GUILD et DISCORD_ROLE_ABONNE sont nécessaires.")
    if not SERVEUR or not ADMIN:
        raise SystemExit("DNAREADER_SERVEUR et DNAREADER_ADMIN sont nécessaires.")

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    class PanneauBoutique(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="Comment je paie ?", emoji="\U0001F4B3",
                           style=discord.ButtonStyle.success,
                           custom_id="dnar:payer")
        async def payer(self, inter, bouton):
            await inter.response.defer(ephemeral=True)
            e = boutique_etat()
            if not e.get("ok") or not e.get("paypal_me"):
                await inter.followup.send(
                    "La boutique n'est pas ouverte pour l'instant — "
                    f"{e.get('raison') or 'le paiement n’est pas configuré'}.",
                    ephemeral=True)
                return
            lignes = [
                f"**Ta ligne de paiement — {e['prix']:.2f} {e['devise']}**",
                "",
                f"**1.** Ouvre {e['paypal_me']}",
                f"**2.** Montant : **{e['prix']:.2f} {e['devise']}**",
                "**3.** Colle **exactement** ceci dans la note / le message :",
                "```",
                note_de(inter.user),
                "```",
                "C'est cette note qui me dit à qui envoyer la clé. Sans elle, "
                "l'argent arrive et la clé ne part pas.",
                "",
                "Tu reçois ta clé **ici, en message privé**, dans la minute qui "
                "suit. Vérifie que tes MP sont ouverts pour ce serveur.",
                f"Un paiement = **{e.get('jours_par_paiement', 31)} jours**, "
                f"utilisable sur **{e.get('machines', 2)} machines**.",
            ]
            await inter.followup.send("\n".join(lignes), ephemeral=True)

        @discord.ui.button(label="J'ai payé, je n'ai rien reçu",
                           emoji="\U0001F914",
                           style=discord.ButtonStyle.secondary,
                           custom_id="dnar:souci")
        async def souci(self, inter, bouton):
            await inter.response.defer(ephemeral=True)
            r = cle_de(inter.user.id)
            if r.get("ok") and r.get("jours_restants", 0) > 0:
                await inter.followup.send(
                    f"Tu as bien une clé active — {_jours(r)} :\n"
                    f"```\n{r['cle']}\n```\n"
                    "Colle-la dans **Réglages → Clé d'accès**.", ephemeral=True)
                return
            await inter.followup.send(
                "Je ne trouve pas de clé active à ton nom. Deux causes, dans "
                "l'ordre de fréquence :\n\n"
                f"**1. La note du virement ne correspond pas.** Elle devait être "
                f"exactement `{note_de(inter.user)}`. Si tu as écrit ton pseudo "
                "d'affichage ou un surnom, je n'ai pas pu te retrouver.\n"
                "**2. Tes messages privés sont fermés.** La clé est peut-être "
                "déjà créée et n'a pas pu partir.\n\n"
                "Dans les deux cas, dis-le dans le salon avec une capture du "
                "reçu PayPal : **ta clé existe et ne se perd pas.**",
                ephemeral=True)

        @discord.ui.button(label="Télécharger", emoji="\U0001F4E5",
                           style=discord.ButtonStyle.secondary,
                           custom_id="dnar:telecharger")
        async def telecharger(self, inter, bouton):
            await inter.response.defer(ephemeral=True)
            e = boutique_etat()
            await inter.followup.send(
                f"**DNAreader** : {e.get('telechargement') or '(indisponible)'}\n\n"
                "Prends `DNAreader-Setup-x.y.z.exe`.\n"
                "L'application n'est pas signée : Windows affichera un "
                "avertissement SmartScreen — clique sur « Informations "
                "complémentaires » puis « Exécuter quand même ».\n\n"
                f"L'essai gratuit de **{e.get('essai_jours', 7)} jours** démarre "
                "tout seul : ni carte bancaire, ni compte à créer.",
                ephemeral=True)

    def panneau(e: dict):
        prix = f"{e['prix']:.2f} {e['devise']}" if e.get("ok") else "—"
        em = discord.Embed(
            title="DNAreader — lis le japonais de tes jeux",
            description=(
                "Une bulle se pose à côté du texte du jeu et donne le sens de "
                "chaque mot, **sans toucher au jeu**. Survole un mot, sa "
                "définition s'affiche ; le bouton `+` l'ajoute à ton vocabulaire."),
            color=0x4FD1C5)
        em.add_field(
            name="\U0001F193 Essai gratuit",
            value=(f"**{e.get('essai_jours', 7)} jours**, tout de suite.\n"
                   "Ni carte bancaire, ni compte à créer."),
            inline=True)
        em.add_field(
            name="\U0001F4B6 Ensuite",
            value=(f"**{prix}** pour {e.get('jours_par_paiement', 31)} jours\n"
                   f"sur {e.get('machines', 2)} machines."),
            inline=True)
        em.add_field(
            name="\U0001F4CB Comment ça se passe",
            value=(
                "**1.** *Télécharger* → tu installes, l'essai démarre seul.\n"
                "**2.** *Comment je paie ?* → je te donne ta ligne de paiement, "
                "toute faite.\n"
                "**3.** Tu paies sur PayPal en collant cette ligne en note.\n"
                "**4.** Tu reçois ta clé **en message privé**, dans la minute.\n"
                "**5.** Tu la colles dans **Réglages → Clé d'accès**. C'est fini."),
            inline=False)
        em.add_field(
            name="⚠️ Le seul piège",
            value=("La note du virement doit être **exactement** celle que le "
                   "bouton te donne. C'est elle qui me dit à qui envoyer la clé.\n"
                   "Et garde tes **MP ouverts** pour ce serveur, sinon la clé ne "
                   "peut pas arriver."),
            inline=False)
        if not e.get("ok") or not e.get("paypal_me"):
            em.add_field(
                name="\U0001F6A7 Vente fermée pour le moment",
                value=("L'essai gratuit et le téléchargement fonctionnent ; "
                       "le paiement n'est pas encore ouvert."),
                inline=False)
        em.set_footer(text="Tape /cle à tout moment pour retrouver ta clé.")
        return em

    class Bot(discord.Client):
        def __init__(self):
            super().__init__(intents=intents)
            self.arbre = app_commands.CommandTree(self)

        async def setup_hook(self):
            guilde = discord.Object(id=int(GUILDE))
            self.arbre.copy_global_to(guild=guilde)
            await self.arbre.sync(guild=guilde)
            self.add_view(PanneauBoutique())
            self.loop.create_task(revue_periodique(self))

    bot = Bot()

    @bot.event
    async def on_ready():
        print(f"[bot] connecté comme {bot.user} · guilde {GUILDE} "
              f"· rôle abonné {ROLE_ABONNE}", flush=True)

    @bot.event
    async def on_message(msg):
        if msg.author.bot or not msg.guild:
            return
        if msg.content.strip().lower() not in (PREFIXE_COMMANDE + "shop",
                                               PREFIXE_COMMANDE + "boutique"):
            return
        if not msg.author.guild_permissions.manage_guild:
            try:
                await msg.channel.send(
                    f"{msg.author.mention} — seule l'administration peut poser "
                    "le panneau. Pour acheter, utilise celui qui est déjà en "
                    "place, ou tape `/cle`.", delete_after=15)
            except Exception:
                pass
            return
        e = boutique_etat()
        await msg.channel.send(embed=panneau(e), view=PanneauBoutique())
        try:
            await msg.delete()
        except Exception:
            pass

    @bot.arbre.command(name="cle", description="Reçois ta clé DNAreader")
    async def cle(inter):
        await inter.response.defer(ephemeral=True)
        membre = inter.user
        abonne = any(str(r.id) == str(ROLE_ABONNE)
                     for r in getattr(membre, "roles", []))
        r = cle_de(membre.id, JOURS_ABONNE if abonne else 0)
        if not r.get("ok"):
            await inter.followup.send(
                f"Je n'ai pas pu récupérer ta clé : {r.get('raison')}",
                ephemeral=True)
            return
        if abonne:
            msg = (f"Voici ta clé DNAreader :\n```\n{r['cle']}\n```\n"
                   f"Elle est active tant que tu es abonné à la chaîne "
                   f"(actuellement {_jours(r)}).\n"
                   f"Colle-la dans **Réglages → Clé d'accès**.")
        elif r.get("jours_restants", 0) > 0:
            msg = (f"Voici ta clé DNAreader :\n```\n{r['cle']}\n```\n"
                   f"Il te reste {_jours(r)}.\n"
                   f"Colle-la dans **Réglages → Clé d'accès**.")
        else:
            msg = (f"Ta clé existe :\n```\n{r['cle']}\n```\n"
                   f"Elle n'est pas active pour l'instant. **Abonne-toi à la "
                   f"chaîne** et retape `/cle`, ou paie ton mois — le panneau "
                   f"de la boutique te donne la marche à suivre. Cette clé "
                   f"restera la tienne.")
        await inter.followup.send(msg, ephemeral=True)

    @bot.event
    async def on_member_update(avant, apres):
        avait = any(str(r.id) == str(ROLE_ABONNE) for r in avant.roles)
        a = any(str(r.id) == str(ROLE_ABONNE) for r in apres.roles)
        if a and not avait:
            r = cle_de(apres.id, JOURS_ABONNE)
            print(f"[bot] {apres} vient de s'abonner -> {r.get('cle')} "
                  f"({_jours(r)})", flush=True)
            try:
                await apres.send(
                    f"Merci pour l'abonnement — DNAreader est à toi :\n"
                    f"```\n{r['cle']}\n```\n"
                    f"Colle-la dans **Réglages → Clé d'accès**.")
            except Exception:
                pass

    bot.run(JETON)


async def revue_periodique(bot):
    import discord
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            guilde = bot.get_guild(int(GUILDE))
            if guilde is None:
                print("[bot] guilde introuvable : le bot y est-il invité ?",
                      flush=True)
            else:
                role = guilde.get_role(int(ROLE_ABONNE))
                if role is None:
                    print(f"[bot] rôle {ROLE_ABONNE} introuvable dans la guilde",
                          flush=True)
                else:
                    n = 0
                    for membre in role.members:
                        r = cle_de(membre.id, JOURS_ABONNE)
                        if r.get("ok"):
                            n += 1
                        else:
                            print(f"[bot] {membre} : {r.get('raison')}", flush=True)
                    print(f"[bot] revue : {n} abonné(s) à jour", flush=True)
        except Exception as e:
            print(f"[bot] revue impossible : {e}", flush=True)
        await asyncio.sleep(PERIODE)


if __name__ == "__main__":
    demarre()
