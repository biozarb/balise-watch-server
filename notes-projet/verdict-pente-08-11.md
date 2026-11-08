# Verdict de pente du 08/11/2026 — ⛔ **RUN BLOQUÉ : LE VPS EST INJOIGNABLE.** La clé SSH n'est plus déverrouillable depuis le redémarrage du Mac d'hier 17:15. ⛔ **Aucune conclusion sur la nuit, AUCUN ticket touché.** ✅ **La routine a tiré à l'heure (+2 min 48 s).**

## 08:12–08:30 (Paris, CET) — routine Balise Watch, run bloqué à l'étape 1

**Étape 0 : faite en entier, avant toute autre chose.**

- `git log --oneline --since=midnight` dans **les deux** dépôts : ✅ **aucun
  commit du jour**. Dernier commit du dépôt serveur : **`5efa984` du 07/11**
  (miroir du verdict du 07/11). Dépôt principal : `cc10b42` du 01/11.
  ⇒ **Aucune autre session n'a tourné ce matin.**
- `project_read claude/verdict-pente-08-11.md` : **absent** ⇒ cette note est une
  **création**, pas une fusion.
- `project_read claude/verdict-pente-07-11.md` : ✅ **lu en entier.** C'est lui
  qui reste la dernière mesure connue, et **rien de ce qu'il dit n'est vérifié
  ce matin.**
- `notes-projet/README.md` relu : les quatre règles.

## 1. ⛔ LE BLOCAGE : `Permission denied (publickey)` — et ce n'est PAS le piège n°1

Les **cinq** lectures de l'étape 1 ont échoué, toutes avec `rc=255` :

```
hist rc=255 · ctrl rc=255 · timer rc=255 · ctrlv rc=255 · score rc=255
debian@51.91.102.146: Permission denied (publickey).
```

### 1.1 Ce qui a été écarté

- ✅ **`SSH_AUTH_SOCK` est correctement posé** et il résout :
  `/private/tmp/com.apple.launchd.xVKaupT5FP/Listeners`, identique à
  `launchctl getenv`. ⇒ ⛔ **Ce n'est donc PAS le piège n°1** documenté onze
  fois depuis le 10/09. Le correctif habituel ne sert à rien ici.
- ✅ **Le réseau et le VPS ne sont pas en cause.** `ssh -v` montre la connexion
  TCP établie, l'échange de clés fait, et le serveur qui répond
  `Authentications that can continue: publickey`. **Le VPS est debout et il
  écoute.**
- ✅ **La clé est bien proposée** :
  `Offering public key: /Users/yann/.ssh/id_ed25519 ED25519
  SHA256:d0C/G0LXg2oHlQRGokx/DR24HOgAzJzrUe0mJGZWZxA explicit`, puis
  `No more authentication methods to try`.

### 1.2 La cause, mesurée

```
ssh-add -l                        → The agent has no identities.
ssh-add --apple-load-keychain     → rc=1, toujours aucune identité
security find-generic-password -s "SSH" -l "SSH: ~/.ssh/id_ed25519"
                                  → item could not be found in the keychain
security find-generic-password -a "/Users/yann/.ssh/id_ed25519"
                                  → item could not be found in the keychain
sysctl kern.boottime              → Sat Nov  7 17:15:06 2026   (uptime 15 h)
```

⇒ ⛔ **L'agent SSH est vide, et la phrase de passe de la clé n'est PAS dans le
trousseau macOS.** Les deux lignes `UseKeychain yes` / `AddKeysToAgent yes` du
`~/.ssh/config` sont bien là — mais `UseKeychain` n'a **rien à lire**.
⇒ ⛔ **Le Mac a redémarré hier à 17:15**, soit **après** le run du 07/11 (11:49).
Ce run-là avait réussi parce que l'agent portait la clé **en mémoire** ; le
redémarrage l'a vidé, et comme la phrase de passe n'a jamais été **enregistrée**
dans le trousseau, rien ne l'a repeuplé.
⇒ ⓘ **C'est exactement le scénario que le commentaire du `~/.ssh/config` décrit**
(« tout processus non interactif obtient Permission denied (publickey) […]
c'est la signature locale qui n'a pas pu se faire ») — à ceci près que la
protection prévue, le trousseau, est **absente**, pas seulement inopérante.
ⓘ Essai complémentaire **sans** `BatchMode`, stdin fermé : **même refus**. Ce
n'est donc pas un effet de `BatchMode`.

### 1.3 ⬆️ Le geste attendu de Yann — une commande, une fois, en interactif

```
ssh-add --apple-use-keychain ~/.ssh/id_ed25519
```

Elle demande la phrase de passe **une seule fois** et l'**écrit dans le
trousseau**. À partir de là, `UseKeychain yes` la relit tout seul, y compris
après un redémarrage, et les runs non interactifs repassent.

Vérification en deux lignes :

```
ssh-add -l                                  → doit lister la clé ED25519
ssh debian@51.91.102.146 'date -u'          → doit répondre
```

⛔ **Je ne l'ai pas lancée** : elle demande une saisie au clavier, et surtout
elle touche au trousseau — c'est à Yann de la taper.

## 2. ⛔ Conséquences : ce que ce run NE dit PAS

La règle du prompt est explicite — si la nuit n'a pas pu être lue, **on ne
conclut rien et on ne touche pas aux tickets**. Elle est appliquée à la lettre.

| ce qui n'a PAS été lu | conséquence |
|---|---|
| `historique.jsonl` | ⛔ aucun `duree_s`, `cpu_s`, `jalon_max_mo`, `swap_peak_mo`, `n_57014`, `lignes_*`, `balise_jours_rejeu` |
| `bw-model-controle.service` du jour | ⛔ on ne sait pas si le contrôle de 07:30 a parlé ni sur quel motif |
| `controle_quotidien.py --verbeux` | ⛔ aucune pente, aucun horizon, aucun compte de relevés comparables |
| `bw-model-score.service` | ⛔ ni bloc purge, ni jalons mémoire, ni R2, ni position, ni témoins du mélange |
| `systemctl list-timers` | ⛔ on ne sait pas si le timer suivant est armé |

⇒ ⛔ **AUCUN ticket touché : ni GET, ni commentaire, ni création.** Pas un seul
appel à `bw_jira_signaler` ni à `bw_jira_commenter`. **Zéro écriture Jira.**
⇒ ⛔ **Aucun verdict correctif par correctif.** Les trois correctifs du 07/10
(webhook `--ipv4`, garde-fou des deux jetons, rejeu de purge ≠ échec) sont
**non vérifiés ce matin** — ni confirmés, ni démentis.
⇒ ⛔ **Aucun compteur avancé.** KAN-5 reste à **12 / 3 au 07/11**, et la nuit du
07→08/11 est **inconnue**, pas « propre ».

### 2.1 ✅ Rien n'est perdu, seulement non lu

`/var/lib/bw-model-verif/historique.jsonl` est un journal en **ajout** sur le
VPS : la ligne de la nuit y est (ou n'y est pas) indépendamment de ma capacité à
la lire. ⇒ ✅ **Dès que la clé est déverrouillée, un `tail -n 4` rattrape la nuit
manquée**, exactement comme le run du 07/11 a rattrapé trois nuits.
⇒ ⬆️ **Proposition : reconduire demain**, et lire **deux** nuits au lieu d'une.
⛔ **Mais si le geste du §1.3 n'est pas fait, le run de demain échouera à
l'identique** — ce blocage ne se résorbe pas tout seul.

## 3. ✅ L'horaire de la routine : à l'heure, et c'est la bonne nouvelle du matin

Programmée pour le **08/11 à 07:09:05 UTC**, tirée le **08/11 à 07:11:53 UTC** :
✅ **+2 min 48 s.**

```
29/10 ⛔ SAUTÉ · 30/10 +0 h 00 · 31/10 +0 h 00 · 01/11 +0 h 55 · 02/11 +0 h 19
03/11 ✅ +0 h 01 · 04/11 ⚠️ +4 h 42 · 05/11 ⛔ SAUTÉ · 06/11 ⛔ SAUTÉ
07/11 ⚠️ +3 h 49 · 08/11 ✅ +0 h 03
```

⇒ ✅ **Le point n°16 du 07/11 s'améliore nettement** : premier tir net depuis le
03/11, après trois matins sautés et deux gros retards en douze jours.
⚠️ **À noter sans se réjouir trop vite** : le tir à l'heure n'a servi à rien ce
matin, puisque la lecture était impossible. **Un matin à l'heure et aveugle vaut
un matin sauté.**

## 4. Ce qui a quand même pu être vérifié — faits locaux, sans le VPS

Peu de choses, et elles sont toutes **locales au Mac**. Je les donne parce
qu'elles tiennent la liste des points ouverts honnête, pas parce qu'elles
remplacent le relevé.

- ⛔ **Les quatre miroirs git en souffrance sont inchangés**, vérifiés un par un
  et **NON arrangés** :
  `24/10` **absent** · `26/10` **présent mais NON SUIVI par git** · `01/11`
  **absent** · `04/11` **absent**. ✅ `07/11` **présent et suivi**.
  ⓘ **Rien n'a été fabriqué après coup**, conformément à la règle.
- ⛔ **Les sept `.sql` en attente sont tous encore là, non appliqués** (`git
  status` les montre non suivis) :
  `diagnostic_base_sous_tension_2026-09-29.sql` (**41ᵉ jour** ; 40 comptés le
  07/11) · `position_l15_2026-11-02.sql` · `suspension_l15_2026-11-02.sql` ·
  `naissance_l15bis_2026-09-22.sql` · `rattrapage_purge_2026-09-29.sql` ·
  `schema_l15bis_notee_depuis_2026-09-22.sql` ·
  `suspension_l15_2026-09-22.sql`.
  ⇒ ⓘ **Cela confirme par une troisième voie l'explication du §7.3 du 07/11** :
  l'annonce du 02/11 (9 → 12 balises nées sous leur identifiant) n'a pas eu lieu
  parce que **le `.sql` n'a jamais été joué**. Il est toujours là, daté du 02/11,
  inchangé.
- ⓘ **`installer-webhook-discord.sh` est bien sur le Mac** (4 019 o, daté du
  07/10) et n'a pas bougé. ⛔ **Mais je NE peux PAS dire où en est
  `BW_DISCORD_WEBHOOK_URL`** : le `.env` est sur le **VPS**. ⇒ **Je ne compte
  donc PAS un 58ᵉ jour mesuré.** Le dernier relevé **mesuré** est celui du
  07/11 : absente, **57ᵉ jour**. (C'est la leçon du 04/11 : ne pas recopier un
  compteur comme s'il était confirmé.)

## 5. Décisions en attente de Yann — la liste du 07/11, plus celle du matin

⬆️ **NOUVEAU ET BLOQUANT, il passe devant tout le reste :**

0. ⛔ **Déverrouiller la clé SSH** (§1.3) :
   `ssh-add --apple-use-keychain ~/.ssh/id_ed25519`, une fois, en interactif.
   **Sans ce geste, la routine est aveugle tous les matins** — et aucun des 24
   points ci-dessous ne peut avancer d'un pouce.

⇒ ⓘ **Les 24 points du §12 de la note du 07/11 sont reportés tels quels, SANS
mise à jour** : je n'ai rien pu mesurer, donc je ne touche à aucun de leurs
chiffres ni à aucune de leurs priorités. Les plus urgents y restent :
**fermeture de KAN-5** (critère rempli depuis le 29/10, dixième jour ce matin
si la nuit était propre — **ce que je ne sais pas**), **R2 qui facture**, **le
swap au pic à son record**, **la ligne en tuple** (48ᵉ jour sans déploiement
mémoire depuis `af25efb`).
⚠️ **Et un avertissement de lecture** : la note du 07/11 annonçait plusieurs
séries en cours (quatre reculs du jalon mémoire, trois hausses du swap, douze
nuits de purge propre, dixième nuit au-dessus du palier R2). **Aucune de ces
séries n'est prolongée par ce matin.** Elles sont **en suspens**, pas
poursuivies — et la leçon « une nuit ne fait pas une pente » vaut aussi pour
**une nuit manquante** : elle ne casse rien non plus.

## 6. Respect des règles

✅ **VPS en LECTURE SEULE, pleine et entière** — et de fait **aucun accès du
tout** : aucun `systemctl`, aucun SQL, aucun rsync, rien écrit ni lu sur le
VPS. La levée nominative du 07/10 n'a **pas** été invoquée.
✅ **Aucun secret lu par valeur.** `~/.ssh/config` a été lu (il ne contient
aucun secret), la **clé privée n'a jamais été ouverte**, et les deux `security
find-generic-password` ne demandaient qu'une **existence** d'entrée — ils n'ont
rendu aucune valeur, et l'entrée n'existe pas. `~/.balise-watch-alertes.env`
n'a pas été touché (il est sur le VPS).
⛔ **Aucune écriture Jira d'aucune sorte**, pas même un GET. ⛔ **Aucun ticket
créé, fermé, rouvert ni transité.** ⛔ **Aucun motif créé.**
✅ `10-timeout-s3.conf` **non touché** ; remontée du garde **non lancée, non
demandée** (et de toute façon impossible à argumenter sans mesure).
✅ `controle_quotidien.sh` **non touché**, son `$ETAT` conservé.
✅ **Desktop Commander exclusivement** pour fichiers et shell, du début à la fin.
✅ **Lire avant d'écrire** : `git log --since=midnight` dans les **deux** dépôts
(**aucun commit**) ; `project_read` du 08/11 (**absent ⇒ création**) et du 07/11
(**lu en entier**) ; `README.md` relu ; **note en section horodatée**.
✅ **Miroir git déposé et commité en local**, depuis la **racine** du dépôt
serveur. ⛔ **Aucun `git push`.**
✅ **Yann averti par notification** dès le blocage constaté, sans attendre la
fin du run.

## 7. ⓘ Outillage — la leçon de ce matin

1. ⛔ **Piège NEUF, et il est majeur : le piège n°1 a un frère.**
   `SSH_AUTH_SOCK` manquant (piège n°1) et **agent vide après redémarrage** sont
   **deux pannes différentes qui rendent le même message**
   (`Permission denied (publickey)`). Le correctif du piège n°1
   (`export SSH_AUTH_SOCK=…`) ne soigne pas la seconde.
   ⇒ ⓘ **Diagnostic à faire dans cet ordre, à l'avenir** :
   ```
   echo $SSH_AUTH_SOCK          # vide → piège n°1
   ssh-add -l                   # "no identities" → agent vide (ce matin)
   uptime                       # un redémarrage récent explique l'agent vide
   ssh-add --apple-load-keychain ; ssh-add -l   # rien → phrase de passe absente du trousseau
   ```
2. ✅ **Le lecteur de flux qui perd des lignes** (piège n°2) : contourné d'emblée,
   **toute** sortie a été redirigée vers un fichier du Mac et relue avec
   `read_file`. C'est ce qui a permis de lire les `rc=255` et le `ssh -v` au mot
   près.
3. ✅ **La notification est partie AVANT la rédaction de la note.** C'est le bon
   ordre quand le run est bloqué : la note est pour l'historique, la
   notification est le seul canal que Yann lit depuis son téléphone.
4. ⓘ Les sorties brutes de ce run sont sur le Mac dans
   `/Users/yann/bw-run-08-11/` (`etape0.txt`, `trace.txt`, `hist.json`,
   `ssh-diag.txt`, `ssh-diag2.txt`, `ssh-diag3.txt`, `local.txt`,
   `lire-vps.sh`) — **relisibles telles quelles**, et `lire-vps.sh` est
   **rejouable à l'identique** dès que la clé est déverrouillée.
