#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  bridge.py — le pont Discord → Jira                       (09/09/2026)
#
#  CE QU'IL FAIT, ET RIEN D'AUTRE :
#    1. Un pilote ouvre un post dans #bugs ou #idées      → un ticket Jira
#       naît, avec le texte, l'auteur, le lien du fil et les tags en
#       labels. Le bot répond dans le fil avec la clé du ticket.
#    2. Toutes les N minutes, il relit les statuts Jira    → le tag de
#       statut du post Discord suit. C'est le seul canal par lequel un
#       pilote apprend que son bug est traité.
#    3. Un post dans #prévu-vs-observé                     → PAS de ticket.
#       Il est journalisé dans un .jsonl, pour la synthèse hebdomadaire.
#       Un retour terrain isolé n'est pas actionnable ; c'est le recoupement
#       qui l'est, et le recoupement ne se fait pas dans un backlog.
#
#  ⚠️ IL NE MODÈRE PAS, NE SUPPRIME RIEN, N'ÉCRIT JAMAIS DANS UN SALON
#  PUBLIC autre que le fil qu'un pilote vient d'ouvrir. Tout le reste de
#  sa parole va dans #flux-jira, qui est privé.
#
#  ⚠️ LE PONT EST UNIDIRECTIONNEL POUR LE CONTENU, BIDIRECTIONNEL POUR LE
#  STATUT. Discord crée le ticket ; Jira commande le tag. Jamais l'inverse :
#  un pilote ne doit pas pouvoir marquer son propre bug « Corrigé » (c'est
#  pour ça que les tags de statut sont `moderated` côté Discord).
#
#  Secrets : ~/.balise-watch-discord.env (chmod 600), chargé par run.sh.
#  État    : /var/lib/bw-discord-bridge/etat.json (correspondance fil↔ticket)
# ══════════════════════════════════════════════════════════════════════
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import discord

# ─────────────────────────────────────────────────────────── configuration
def _env(nom: str, defaut: str | None = None, *, requis: bool = False) -> str:
    v = os.environ.get(nom, defaut)
    if requis and not v:
        print(f"❌ variable manquante : {nom}", file=sys.stderr)
        sys.exit(78)  # EX_CONFIG — comme run-poller.sh, inutile de relancer
    return v or ""


DISCORD_TOKEN = _env("BW_DISCORD_TOKEN", requis=True)
JIRA_SITE     = _env("BW_JIRA_SITE", "https://balisewatch.atlassian.net")
JIRA_EMAIL    = _env("BW_JIRA_EMAIL", requis=True)
JIRA_TOKEN    = _env("BW_JIRA_TOKEN", requis=True)
JIRA_PROJET   = _env("BW_JIRA_PROJET", "KAN")

FORUM_BUGS   = int(_env("BW_FORUM_BUGS",   "1547197502179119144"))
FORUM_IDEES  = int(_env("BW_FORUM_IDEES",  "1547197506117574746"))
FORUM_TERRAIN= int(_env("BW_FORUM_TERRAIN","1547197494986023085"))
SALON_FLUX   = int(_env("BW_SALON_FLUX",   "1547197453759938581"))

ETAT_DIR   = pathlib.Path(_env("BW_ETAT_DIR", "/var/lib/bw-discord-bridge"))
ETAT_FIC   = ETAT_DIR / "etat.json"
TERRAIN_FIC= ETAT_DIR / "observations.jsonl"

PERIODE_SYNC = int(_env("BW_PERIODE_SYNC", "300"))   # secondes

# Type de ticket par forum
TYPE_PAR_FORUM = {FORUM_BUGS: "Bug", FORUM_IDEES: "Story"}

# Jira → nom du tag Discord à poser. Ce qui n'est pas listé ne bouge rien.
STATUT_VERS_TAG = {
    "À faire":           {"bugs": "Confirmé",  "idees": "Retenue"},
    "En cours":          {"bugs": "En cours",  "idees": "En cours"},
    "En cours de revue": {"bugs": "En cours",  "idees": "En cours"},
    "Mise en prod":      {"bugs": "En cours",  "idees": "En cours"},
    "Terminé":           {"bugs": "Corrigé",   "idees": "Livrée"},
}
TAGS_STATUT = {"Nouveau", "Confirmé", "En cours", "Corrigé", "Non reproductible",
               "À trier", "Retenue", "Livrée", "Hors périmètre"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%d/%m %H:%M:%S",
)
log = logging.getLogger("pont")


# ───────────────────────────────────────────────────────────────── état
class Etat:
    """Correspondance fil Discord ↔ ticket Jira. Écriture atomique :
    une coupure au mauvais moment ne doit pas laisser un fichier tronqué,
    sinon on reperd la correspondance et les tags cessent de suivre."""

    def __init__(self, chemin: pathlib.Path):
        self.chemin = chemin
        self.data: dict[str, Any] = {"fils": {}}
        if chemin.exists():
            try:
                self.data = json.loads(chemin.read_text("utf-8"))
                self.data.setdefault("fils", {})
            except Exception as e:
                log.error("état illisible (%s) — on repart à vide", e)

    def enregistrer(self):
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.chemin.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), "utf-8")
        os.replace(tmp, self.chemin)

    def lier(self, fil_id: int, cle: str, famille: str):
        self.data["fils"][str(fil_id)] = {
            "ticket": cle, "famille": famille,
            "statut": None, "cree": int(time.time()),
        }
        self.enregistrer()

    def deja_traite(self, fil_id: int) -> bool:
        return str(fil_id) in self.data["fils"]

    def liens(self) -> dict[str, dict]:
        return self.data["fils"]


# ───────────────────────────────────────────────────────────────── Jira
class Jira:
    def __init__(self):
        jeton = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_TOKEN}".encode()).decode()
        self._auth = "Basic " + jeton

    def _appel(self, methode: str, chemin: str, corps: dict | None = None,
               essais: int = 4) -> Any:
        url = JIRA_SITE.rstrip("/") + chemin
        data = json.dumps(corps).encode() if corps is not None else None
        derniere = None
        for n in range(essais):
            req = urllib.request.Request(url, data=data, method=methode)
            req.add_header("Authorization", self._auth)
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json")
            # ⚠️ Jamais l'User-Agent par défaut d'urllib : Cloudflare le
            # refuse en 403 devant l'API Discord (constaté depuis le VPS
            # le 09/09), et rien ne dit qu'Atlassian ne le fera pas un jour.
            req.add_header("User-Agent", "BaliseWatchBridge/1.0 (+https://balise-watch.app)")
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    brut = r.read()
                    return json.loads(brut) if brut else None
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:400]
                derniere = f"HTTP {e.code} — {detail}"
                if e.code in (429, 500, 502, 503, 504) and n < essais - 1:
                    time.sleep(2 ** n * 2)
                    continue
                break
            except Exception as e:              # réseau, DNS, timeout
                derniere = str(e)
                if n < essais - 1:
                    time.sleep(2 ** n * 2)
                    continue
        raise RuntimeError(f"Jira {methode} {chemin} : {derniere}")

    # -- Atlassian Document Format : le minimum viable ------------------
    @staticmethod
    def _adf(blocs: list[tuple[str, str]]) -> dict:
        """blocs = [("titre"|"para"|"code", texte), ...]"""
        content = []
        for genre, texte in blocs:
            if not texte:
                continue
            if genre == "titre":
                content.append({"type": "heading", "attrs": {"level": 3},
                                "content": [{"type": "text", "text": texte[:250]}]})
            elif genre == "code":
                content.append({"type": "codeBlock", "attrs": {},
                                "content": [{"type": "text", "text": texte[:30000]}]})
            else:
                content.append({"type": "paragraph",
                                "content": [{"type": "text", "text": texte[:30000]}]})
        if not content:
            content = [{"type": "paragraph", "content": []}]
        return {"type": "doc", "version": 1, "content": content}

    def creer(self, *, resume: str, type_ticket: str, corps_texte: str,
              auteur: str, url_fil: str, labels: list[str]) -> str:
        champs = {
            "project": {"key": JIRA_PROJET},
            "summary": resume[:250],
            "issuetype": {"name": type_ticket},
            "labels": labels[:20],
            "description": self._adf([
                ("para", f"Remonté par {auteur} sur le Discord."),
                ("para", url_fil),
                ("titre", "Le message d'origine"),
                ("code", corps_texte or "(message vide)"),
            ]),
        }
        r = self._appel("POST", "/rest/api/3/issue", {"fields": champs})
        return r["key"]

    def commenter(self, cle: str, texte: str):
        self._appel("POST", f"/rest/api/3/issue/{cle}/comment",
                    {"body": self._adf([("para", texte)])})

    def statuts(self, cles: list[str]) -> dict[str, str]:
        """Statut courant de chaque ticket, par paquets de 50."""
        out: dict[str, str] = {}
        for i in range(0, len(cles), 50):
            lot = cles[i:i + 50]
            jql = f'project = {JIRA_PROJET} AND key in ({",".join(lot)})'
            q = urllib.parse.urlencode({"jql": jql, "fields": "status",
                                        "maxResults": 50})
            try:
                r = self._appel("GET", f"/rest/api/3/search/jql?{q}")
            except RuntimeError:                # instances plus anciennes
                r = self._appel("GET", f"/rest/api/3/search?{q}")
            for t in (r or {}).get("issues", []):
                out[t["key"]] = t["fields"]["status"]["name"]
        return out


# ─────────────────────────────────────────────────────────────── outils
def nettoyer(texte: str, limite: int = 6000) -> str:
    texte = re.sub(r"<@!?\d+>", "@pilote", texte or "")
    return texte[:limite]


def slug(nom: str) -> str:
    """Nom de tag Discord → label Jira (Jira n'aime ni espaces ni accents)."""
    table = str.maketrans("àâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ", "aaaeeeeiioouuucAAAEEEEIIOOUUUC")
    n = nom.translate(table).lower()
    n = re.sub(r"[^a-z0-9]+", "-", n).strip("-")
    return n or "sans-tag"


# ──────────────────────────────────────────────────────────────── le bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.Client(intents=intents)
etat = Etat(ETAT_FIC)
jira = Jira()


async def flux(msg: str):
    """Le journal visible dans #flux-jira. Ne doit jamais faire tomber le bot."""
    log.info(msg)
    try:
        salon = bot.get_channel(SALON_FLUX) or await bot.fetch_channel(SALON_FLUX)
        await salon.send(msg[:1990], allowed_mentions=discord.AllowedMentions.none())
    except Exception as e:
        log.warning("journal indisponible : %s", e)


@bot.event
async def on_ready():
    log.info("connecté comme %s", bot.user)
    await flux(f"▶️ Pont démarré — {len(etat.liens())} fil(s) suivi(s).")
    bot.loop.create_task(boucle_sync())


@bot.event
async def on_thread_create(fil: discord.Thread):
    # Discord peut renvoyer l'évènement deux fois (reconnexion) : on garde
    # la correspondance comme garde-fou, jamais un doublon de ticket.
    if etat.deja_traite(fil.id):
        return
    parent = fil.parent_id
    if parent not in (FORUM_BUGS, FORUM_IDEES, FORUM_TERRAIN):
        return

    await asyncio.sleep(2)          # laisse le message d'ouverture arriver
    try:
        premier = await fil.fetch_message(fil.id)
        corps = nettoyer(premier.content)
        if premier.attachments:
            corps += "\n\nPièces jointes :\n" + "\n".join(
                a.url for a in premier.attachments)
    except Exception:
        corps = ""

    auteur = getattr(fil.owner, "display_name", None) or f"utilisateur {fil.owner_id}"
    tags = [t.name for t in getattr(fil, "applied_tags", [])]

    # ---- retour terrain : on journalise, on ne crée pas de ticket -----
    if parent == FORUM_TERRAIN:
        try:
            ETAT_DIR.mkdir(parents=True, exist_ok=True)
            with TERRAIN_FIC.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "date": int(time.time()), "fil": str(fil.id),
                    "titre": fil.name, "auteur": auteur,
                    "tags": tags, "texte": corps,
                }, ensure_ascii=False) + "\n")
            await flux(f"🌦️ Retour terrain journalisé — « {fil.name} » ({auteur}).")
        except Exception as e:
            await flux(f"⚠️ Retour terrain NON journalisé — {e}")
        return

    # ---- bugs et idées : un ticket -----------------------------------
    famille = "bugs" if parent == FORUM_BUGS else "idees"
    type_ticket = TYPE_PAR_FORUM[parent]
    labels = ["discord", famille] + [slug(t) for t in tags if t not in TAGS_STATUT]

    try:
        cle = await asyncio.to_thread(
            jira.creer,
            resume=fil.name, type_ticket=type_ticket, corps_texte=corps,
            auteur=auteur, url_fil=fil.jump_url, labels=labels,
        )
    except Exception as e:
        await flux(f"❌ Ticket NON créé pour « {fil.name} » ({auteur}) — {e}")
        return

    etat.lier(fil.id, cle, famille)
    lien = f"{JIRA_SITE.rstrip('/')}/browse/{cle}"

    try:
        await fil.send(
            f"Merci {auteur}, c'est enregistré sous **{cle}**.\n"
            f"Le tag de statut de ce post suivra l'avancement — tu n'as rien à faire.",
            allowed_mentions=discord.AllowedMentions.none())
    except Exception as e:
        log.warning("accusé de réception impossible : %s", e)

    await poser_tag(fil, "Nouveau" if famille == "bugs" else "À trier")
    await flux(f"✅ {cle} créé — « {fil.name} » ({auteur})\n{lien}")


async def poser_tag(fil: discord.Thread, nom_tag: str) -> bool:
    """Remplace le tag de statut, garde les tags de module."""
    forum = fil.parent
    if forum is None:
        return False
    cible = discord.utils.get(forum.available_tags, name=nom_tag)
    if cible is None:
        log.warning("tag « %s » absent du forum %s", nom_tag, forum.name)
        return False
    garde = [t for t in fil.applied_tags if t.name not in TAGS_STATUT]
    if any(t.id == cible.id for t in fil.applied_tags):
        return False                              # déjà posé, rien à faire
    try:
        await fil.edit(applied_tags=(garde + [cible])[:5])   # Discord : 5 max
        return True
    except Exception as e:
        log.warning("tag non posé sur %s : %s", fil.id, e)
        return False


async def boucle_sync():
    """Relit les statuts Jira et met les tags Discord en accord."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            await synchroniser()
        except Exception as e:
            log.exception("boucle de synchronisation : %s", e)
        await asyncio.sleep(PERIODE_SYNC)


async def synchroniser():
    liens = etat.liens()
    if not liens:
        return
    cles = [v["ticket"] for v in liens.values()]
    try:
        courants = await asyncio.to_thread(jira.statuts, cles)
    except Exception as e:
        log.warning("statuts Jira illisibles : %s", e)
        return

    change = False
    for fil_id, info in list(liens.items()):
        statut = courants.get(info["ticket"])
        if not statut or statut == info.get("statut"):
            continue
        nom_tag = STATUT_VERS_TAG.get(statut, {}).get(info["famille"])
        info["statut"] = statut
        change = True
        if not nom_tag:
            continue
        try:
            fil = bot.get_channel(int(fil_id)) or await bot.fetch_channel(int(fil_id))
        except Exception:
            log.info("fil %s introuvable (supprimé ?) — on le laisse", fil_id)
            continue
        if await poser_tag(fil, nom_tag):
            await flux(f"🔄 {info['ticket']} → *{statut}* — tag « {nom_tag} » posé.")
            if statut == "Terminé":
                try:
                    await fil.send(
                        "C'est corrigé et déployé. Si ça persiste chez toi, "
                        "pense à recharger l'app (elle garde parfois une "
                        "version en cache) — et redis-le ici si ça ne suffit pas.",
                        allowed_mentions=discord.AllowedMentions.none())
                except Exception:
                    pass
    if change:
        etat.enregistrer()


if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN, log_handler=None)
    except discord.LoginFailure:
        print("❌ token Discord refusé", file=sys.stderr)
        sys.exit(78)
