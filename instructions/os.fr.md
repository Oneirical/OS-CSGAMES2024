# <a id="os"/>Systèmes d'exploitation

Nous avons infiltré le réseau de la verdure et avons installé des "file crawlers" sur leurs systèmes qui vont nous envoyé leurs fichiers. Votre mission est d'écrire un serveur qui recevra ces données et de les sauvegarder sur nos systèmes. Avec ceci, nous pourrons prédire les prochaines actions de l'ennemi!

Nous avons trouvé que le réseau de la verdure est un peu douteux, donc il pourrait y avoir de la perte de paquets, des paquets qui ne sont pas dans le bon ordre, et des inversements de bits (bit flip).

Vous pouvez utiliser un langage de programmation au choix. Nous avons fourni un un crawler de test (`crawler.py`). Vous pouvez vous réferer à son implémentation.

\* Par souci de simplicité, les exemples ci-dessous n'ont pas de bits de parité, et présument que l'ordre des octets (réseau et PC) est toujours gros-boutien.

## <a id="requests"/>Requêtes

**Les crawlers enverront toute transmission sur le port `7331`.**

**Les entiers sont envoyés dans l'ordre des octets du réseau (voir `man htonl` pour des détails).**

Chaque requête commence avec une entête de 10 octets:
* 2 octets: Le chiffre magique 0xC505
* 2 octets: Taille totale du paquet, incluant l'entête
* 2 octets: Identifiant du crawler
* 4 octets: Nom de la commande en ASCII

La taille de la charge utile (payload) est obtenue par `size - sizeof(header)`. Les paquets dans ce protocole ont une taille maximale de 508 octets, donc la charge utile a une taille maximale de 498 octets.

### <a id="upld"/>UPLD

Ceci est le premier paquet qu'un crawler enverra. Il signale le début d'un téléversement de fichier. Il contient le chemin de fichier dans la charge utile (sans terminer avec un octet nul).

```
[0x00000000]    C5 05 00 1B 00 01 55 50  4C 44 2F 76 61 72 2F 6C    |......UPLD/var/l|
[0x00000010]    6F 67 2F 61 75 74 68 2E  6C 6F 67                   |og/auth.log|
```

\* Des fichiers dupliqués peuvent être acceptés, au cas où ils seraient différents.

### <a id="mode"/>MODE

Ce paquet n'est pas nécessaire. S'il est envoyé, il précédera tous les paquets DATA. Il détermine comment le fichier sera téléversé. S'il n'est pas envoyé, le mode ['block'](#block) est présumé. Voir [ici](#modes) pour les détails.
```
[0x00000000]    C5 05 00 0F 00 01 4D 4F  44 45 62 6C 6F 63 6B       |......MODEblock|
```

### <a id="seqn"/>SEQN

Ce paquet n'est pas nécessaire. S'il est envoyé, il précédera tous les paquets DATA. Il contient le numéro de séquence initial. S'il n'est pas envoyé, 0 est présumé.

Voici un exemple avec 0x1111:

```
[0x00000000]    C5 05 00 08 00 01 53 45  51 4E 11 11                |......SEQN..|
```

### <a id="data"/>DATA

Ce type de paquet sera envoyé jusqu'à ce que le téléversement soit complété. Les 2 premiers octets contiennent l'identifiant du téléversement. Les 2 prochains octets contiennent le numéro de séquence. Un téléversement est complété avec un paquet DATA vide (le numéro de séquence et l'identifiant du téléversement sont toujours présents). Cet exemple a le numéro de séquence 8039 et l'identifiant 128:

```
[0x00000000]    C5 05 02 2F 00 01 44 41  54 41 00 80 1F 67 25 50    |.../....DATA.g%P|
[0x00000010]    44 46 2D 31 2E 36 0D 25  E2 E3 CF D3 0D 0A 32 39    |DF-1.6.%......29|
[0x00000020]    ...
```

## <a id="responses"/>Réponses

Le serveur doit répondre dans les cas suivants:
- Un nouveau téléversement est demandé (paquet `UPLD`)
- Des métadonnées de téléversement sont reçues (paquets `MODE` et `SEQN`)
- Lorsqu'une perte de paquets est détectée
- Lorsqu'une erreur est survenue

### <a id='upld_received'>Requête de téléversement reçue

Lorsque le serveur reçoit une requête de téléversement, il doit répondre avec la chaîne de caractères 'UPLOADING' suivi d'un identifiant de 2 octets. Le crawler continuera d'envoyer son paquet `UPLD` jusqu'à ce qu'il reçoive cette réponse. Cet exemple retourne 8039 comme identifiant:

```
[0x00000000]    55 50 4C 4F 41 44 49 4E  47 1F 67                   |UPLOADING.g|
```

### <a id="upld_end">Téléversement complété

Lorsque le serveur reçoit un paquet `DATA` vide, il soit répondre avec 'UPLOAD END' suivi du chemin de fichier envoyé dans la requête de téléversement.

```
[0x00000000]    55 50 4C 4F 41 44 20 45  42 44 2F 76 61 72 2F 6C    |......UPLD/var/l|
[0x00000010]    6F 67 2F 61 75 74 68 2E  6C 6F 67                   |og/auth.log|
```

### <a id='meta_received'>Métadonnées reçues

Lorsque le serveur reçoit un paquet de métadonnées, il doit répondre avec 'METADATA' suivi du type de métadonnée. Le crawler continuera d'envoyer son paquet jusqu'à ce qu'il reçoive cette réponse.

Réponse `SEQN`:

```
[0x00000000]    4D 45 54 41 44 41 54 41  53 45 51 4E                |METADATASEQN|
```

Réponse `MODE`:

```
[0x00000000]    4D 45 54 41 44 41 54 41  4D 4F 44 45                |METADATAMODE|
```

### <a id="loss"/>Perte de paquets

Pour signaler une perte de paquet(s), le serveur doit répondre avec 'LOSS' suivi du nombre de paquets perdus et des numéros de séquence. Par exemple, pour signaler la perte des paquets 2, 3, et 16 (donc le serveur a reçu les paquets 1. 4 à 15, et un numéro de séquence plus grand que 16), le serveur doit envoyer:

```
[0x00000000]    4C 4F 53 53 00 03 00 02  00 03 00 10                |LOSS........|
```

NB: Le nombre de paquets perdus et chaque numéro de séquence sont 2 octets de long.

Le serveur peut choisir de signaler une perte à chaque fois qu'il détecte une perte, ou bien accumuler une plus grande liste. Le crawler continuera d'écouter pour un moment suivant la terminaison de ses téléversements.

### <a id="errors"/>Erreurs

Cette réponse indique au client qu'une erreur est survenue. La charge utile est 'IAMERR' suivi de la taille totale du paquet (2 octets) et du message d'erreur. Ceci est pour les exceptions, des paquets invalides, n'importe quoi qui n'est pas couvert par une autre réponse. Si le paquet erroné a un numéro de séquence, il doit être ajouté à la charge utile.

Voici un exemple avec le message d'erreur "fail":

```
[0x00000000]    49 41 4D 45 52 52 00 0C  66 61 69 6C                |IAMERR..fail|
```

## <a id="modes"/>Modes

### <a id="block"/>Block

Ceci est le mode par défaut. Le crawler enverra autant de paquets que nécessaire afin de compléter le téléversement. Il divisera le fichier en morceaux et les enverra un à un, suivi d'un paquet `DATA` vide pour indiquer la fin du fichier.

Pour utiliser ce mode, le crawler enverra le paquet `MODE` suivi de 'block', ou tout simplement omettre le paquet `MODE`.

```
[0x00000000]    C5 05 00 0F 00 01 4D 4F  44 45 62 6C 6F 63 6B       |......MODEblock|
```

### <a id="compressed"/>Compressé

Ce mode est similaire au mode 'block', mais les données seront encodées par plage (RLE). Les [bits de parité](#parity) sont calculés et ajoutés _après_ que les données soient encodées. Les bits de parité peuvent être désactivés avec [une variable d'environnement](#helpme).

Pour utiliser ce mode, le crawler enverra le paquet `MODE` suivi de 'compressed'.

```
[0x00000000]    C5 05 00 14 00 01 4D 4F  44 45 63 6F 6D 70 72 65    |......MODEcompre|
[0x00000010]    73 73 65 64                                         |ssed|
```

Le codage par plage est une forme de compression sans perte dans laquelle des plages (une plage est une séquence de valeurs pareilles consécutives) de données sont encodées comme un décompte et une valeur. Considérons du texte noir sur un arrière-plan blanc. Il y aura des longues plages de pixels blancs (représentés par W) intercalées avec des petites plages de pixels noirs (représentés par B). La séquence de pixel suivante lorsqu'encodée par plage, deviendra:

```
WWWWWWWWWWWWBWWWWWWWWWWWWBBBWWWWWWWWWWWWWWWWWWWWWWWWBWWWWWWWWWWWWWW -> 12W1B12W3B24W1B14W
```

Les données originales prennent 67 caractères, mais compressées ne prennent que 18 caractères.

Le crawler encode les données comme des entiers et non du texte. La taille maximale d'une plage est de 256, donc le décompte rentre dans un octet; ajoute une autre paire de `(valeur, décompte)` si la plage est plus longue. Si le crawler envoyait l'exemple précédent dans un paquet `DATA`, il ressemblerait à:

```
[0x00000000]    C5 05 00 18 00 01 44 41  54 41 0C 57 01 42 0C 57    |......DATA.W.B.W|
[0x00000010]    03 42 18 57 01 42 0E 57                             |.B.W.B.W|
```

## <a id="parity" />Correction et détection d'erreurs

Les codes Hamming sont un type de code de correction d'erreurs. Les crawlers utilisent le code Hamming(255, 247) étendu, avec parité paire. Le terme "étendu" veut tout simplement dire qu'il y a un bit de parité global en extra. Il y a 256 bits totals (255 + 1 pour la parité globale) dans chaque bloc, avec 9 (8 + 1 pour la parité globale) bits de redondance (aux positions 0, 1, 2, 4, 8, 16, 32, 64, et 128). Ceci donne 247 (255 - 8 ou 256 - 9) bits de données.

<sub>Parité paire veut dire que le nombre de bits à 1 soit être divisible par 2 (d'où le nom 'paire').</sub>

- Le bit 0 couvre le bloc en entier, incluant les bits de parité
- Les bits de parité ont une position qui est une puissance de 2 (seulement 1 bit est à 1 lorsqu'écrit en binaire)
  - Ex: le bit 8 est un bit de parité, car 0b00001000 a une seul bit est mis à 1)
- Tous les autres bits sont des bits de données (2 ou plus de bits mis à 1)
  - Chaque bit de donnée est dans un ensemble unique de 2 bits de parité (ou plus de 2), déterminé par sa position
  - Ex: Bit 9 (1001) est couvert par les bits de parité 8 et 1
- Les bits de parité couvrent tous les bits où l'opération ET au niveau des bits (bitwise AND) de sa position et de la position du bit de donnée n'est pas zéro
  - Ex: Le bit de parité 32 couvrent les bits 32 à 63, 96 à 127, 160 à 191, 224 à 254 (où `bit_position & 32 != 0`)
- La combinaison de bits de parité donne la position du bit erroné

<sub>NB: Présumer qu'il n'y aura jamais plus de 2 bits erronés par bloc.</sub>

Les tables et formules pour Hamming(255, 247) étendu sont dans le fichier [extended_hamming_255_247.md](extended_hamming_255_247.md).

### <a id="parity_example" />Exemple

À titre d'exemple, regardons le code Hamming(15, 11) étendu, qui a un bloc de 16 bits, dont 11 bits de données.

` `|Col 1|Col 2|Col 3|Col 4
---|---|---|---|---
<b>Row 1</b>|G<sub>0000</sub>|P<sub>0001</sub>|P<sub>0010</sub>|D<sub>0011</sub>
<b>Row 2</b>|P<sub>0100</sub>|D<sub>0101</sub>|D<sub>0110</sub>|D<sub>0111</sub>
<b>Row 3</b>|P<sub>1000</sub>|D<sub>1001</sub>|D<sub>1010</sub>|D<sub>1011</sub>
<b>Row 4</b>|D<sub>1100</sub>|D<sub>1101</sub>|D<sub>1110</sub>|D<sub>1111</sub>

<sub>G: parité globale; couvre le bloc en entier</sub>
<sub>P: bit de parité; chacun couvre 2 colonnes et 2 rangées</sub>
<sub>D: bit de donnée; contient le message à transmettre</sub>

- P<sub>0001</sub> couvre les positions correspondant à `xxx1`: 3<sub>0011</sub>, 5<sub>0101</sub>, 7<sub>0111</sub>, 9<sub>1001</sub>, 11<sub>1011</sub>, 13<sub>1101</sub>, 15<sub>1111</sub>
- P<sub>0010</sub> couvre les positions correspondant à `xx1x`: 3<sub>0011</sub>, 6<sub>0110</sub>, 7<sub>0111</sub>, 10<sub>1010</sub>, 11<sub>1011</sub>, 14<sub>1110</sub>, 15<sub>1111</sub>
- P<sub>0100</sub> couvre les positions correspondant à `x1xx`: 5<sub>0101</sub>, 6<sub>0110</sub>, 7<sub>0111</sub>, 12<sub>1100</sub>, 13<sub>1101</sub>, 14<sub>1110</sub>, 15<sub>1111</sub>
- P<sub>1000</sub> couvre les positions correspondant à `1xxx`: 9<sub>1001</sub>, 10<sub>1010</sub>, 11<sub>1011</sub>, 12<sub>1100</sub>, 13<sub>1101</sub>, 14<sub>1110</sub>, 15<sub>1111</sub>
- G<sub>0000</sub> couvre toutes les positions, même les autres bits de parité

Si l'on regarde plus près, on peut voir un motif:
- P<sub>0001</sub> couvre les colonnes 2 et 4
- P<sub>0010</sub> couvre les colonnes 3 et 4
- P<sub>0100</sub> couvre les rangées 2 et 4
- P<sub>1000</sub> couvre les rangées 3 et 4

Ceci donne les formules suivantes:
- P<sub>0001</sub> = D<sub>0011</sub> ^ D<sub>0101</sub> ^ D<sub>0111</sub> ^ D<sub>1001</sub> ^ D<sub>1011</sub> ^ D<sub>1101</sub> ^ D<sub>1111</sub>
- P<sub>0010</sub> = D<sub>0011</sub> ^ D<sub>0110</sub> ^ D<sub>0111</sub> ^ D<sub>1010</sub> ^ D<sub>1011</sub> ^ D<sub>1110</sub> ^ D<sub>1111</sub>
- P<sub>0100</sub> = D<sub>0101</sub> ^ D<sub>0110</sub> ^ D<sub>0111</sub> ^ D<sub>1100</sub> ^ D<sub>1101</sub> ^ D<sub>1110</sub> ^ D<sub>1111</sub>
- P<sub>1000</sub> = D<sub>1001</sub> ^ D<sub>1010</sub> ^ D<sub>1011</sub> ^ D<sub>1100</sub> ^ D<sub>1101</sub> ^ D<sub>1110</sub> ^ D<sub>1111</sub>

Supposons que l'on veut envoyer les bits `11001011011`. Nous insérons les bits de données et avons:

` `|Col 1|Col 2|Col 3|Col 4
---|---|---|---|---
<b>Row 1</b>|G<sub>0000</sub>|P<sub>0001</sub>|P<sub>0010</sub>|1<sub>0011</sub>
<b>Row 2</b>|P<sub>0100</sub>|1<sub>0101</sub>|0<sub>0110</sub>|0<sub>0111</sub>
<b>Row 3</b>|P<sub>1000</sub>|1<sub>1001</sub>|0<sub>1010</sub>|1<sub>1011</sub>
<b>Row 4</b>|1<sub>1100</sub>|0<sub>1101</sub>|1<sub>1110</sub>|1<sub>1111</sub>

Après, nous calculons les bits de parité:
- P<sub>0001</sub> = 1<sub>0011</sub> ^ 1<sub>0101</sub> ^ 0<sub>0111</sub> ^ 1<sub>1001</sub> ^ 1<sub>1011</sub> ^ 0<sub>1101</sub> ^ 1<sub>1111</sub> = 1
- P<sub>0010</sub> = 1<sub>0011</sub> ^ 0<sub>0110</sub> ^ 0<sub>0111</sub> ^ 0<sub>1010</sub> ^ 1<sub>1011</sub> ^ 1<sub>1110</sub> ^ 1<sub>1111</sub> = 0
- P<sub>0100</sub> = 1<sub>0101</sub> ^ 0<sub>0110</sub> ^ 0<sub>0111</sub> ^ 1<sub>1100</sub> ^ 0<sub>1101</sub> ^ 1<sub>1110</sub> ^ 1<sub>1111</sub> = 0
- P<sub>1000</sub> = 1<sub>1001</sub> ^ 0<sub>1010</sub> ^ 1<sub>1011</sub> ^ 1<sub>1100</sub> ^ 0<sub>1101</sub> ^ 1<sub>1110</sub> ^ 1<sub>1111</sub> = 1

` `|Col 1|Col 2|Col 3|Col 4
---|---|---|---|---
<b>Row 1</b>|G<sub>0000</sub>|1<sub>0001</sub>|0<sub>0010</sub>|1<sub>0011</sub>
<b>Row 2</b>|0<sub>0100</sub>|1<sub>0101</sub>|0<sub>0110</sub>|0<sub>0111</sub>
<b>Row 3</b>|1<sub>1000</sub>|1<sub>1001</sub>|0<sub>1010</sub>|1<sub>1011</sub>
<b>Row 4</b>|1<sub>1100</sub>|0<sub>1101</sub>|1<sub>1110</sub>|1<sub>1111</sub>

Pour obtenir une parité paire à travers le bloc, G<sub>0000</sub> devrait être mis à 1. Notre bloc avec les bits de parité ressemble à:

` `|Col 1|Col 2|Col 3|Col 4
---|---|---|---|---
<b>Row 1</b>|1<sub>0000</sub>|1<sub>0001</sub>|0<sub>0010</sub>|1<sub>0011</sub>
<b>Row 2</b>|0<sub>0100</sub>|1<sub>0101</sub>|0<sub>0110</sub>|0<sub>0111</sub>
<b>Row 3</b>|1<sub>1000</sub>|1<sub>1001</sub>|0<sub>1010</sub>|1<sub>1011</sub>
<b>Row 4</b>|1<sub>1100</sub>|0<sub>1101</sub>|1<sub>1110</sub>|1<sub>1111</sub>

Quand on ajoute la parité à `11001011011`, on obtient `1101010011011011`.

#### <a id='parity_1_flip' />1 bit erroné

Supposons que le bit 3<sub>0011</sub> est renversé lors de la transmission et que nous recevons le bloc suivant:

` `|Col 1|Col 2|Col 3|Col 4
---|---|---|---|---
<b>Row 1</b>|1<sub>0000</sub>|1<sub>0001</sub>|0<sub>0010</sub>|0<sub>0011</sub>
<b>Row 2</b>|0<sub>0100</sub>|1<sub>0101</sub>|0<sub>0110</sub>|0<sub>0111</sub>
<b>Row 3</b>|1<sub>1000</sub>|1<sub>1001</sub>|0<sub>1010</sub>|1<sub>1011</sub>
<b>Row 4</b>|1<sub>1100</sub>|0<sub>1101</sub>|1<sub>1110</sub>|1<sub>1111</sub>

Vérifions nos équations ci-dessus:
- P<sub>0001</sub>: 1 = 0<sub>0011</sub> ^ 1<sub>0101</sub> ^ 0<sub>0111</sub> ^ 1<sub>1001</sub> ^ 1<sub>1011</sub> ^ 0<sub>1101</sub> ^ 1<sub>1111</sub> (!!!)
- P<sub>0010</sub>: 0 = 0<sub>0011</sub> ^ 0<sub>0110</sub> ^ 0<sub>0111</sub> ^ 0<sub>1010</sub> ^ 1<sub>1011</sub> ^ 1<sub>1110</sub> ^ 1<sub>1111</sub> (!!!)
- P<sub>0100</sub>: 0 = 1<sub>0101</sub> ^ 0<sub>0110</sub> ^ 0<sub>0111</sub> ^ 1<sub>1100</sub> ^ 0<sub>1101</sub> ^ 1<sub>1110</sub> ^ 1<sub>1111</sub>
- P<sub>1000</sub>: 1 = 1<sub>1001</sub> ^ 0<sub>1010</sub> ^ 1<sub>1011</sub> ^ 1<sub>1100</sub> ^ 0<sub>1101</sub> ^ 1<sub>1110</sub> ^ 1<sub>1111</sub>

Nous pouvons voir que G<sub>0000</sub>, P<sub>0001</sub>, et P<sub>0010</sub> ne tiennent pas. Nous savons donc que le bit 3<sub>0011</sub> est renversé, car `0001 | 0010 = 0011`. Faire le OU au niveau de bits (bitwise OR) des positions des bits de parité qui contiennent une erreur nous donne la position du bit erroné.

<sub>NB: Les codes Hamming peuvent aussi détecter des bits de parité (incluant G<sub>0000</sub>) renversés</sub>

#### <a id='parity_2_flip' />2 bits erronés

Supposons que les bits 3<sub>0011</sub> et 14<sub>1110</sub> sont reversés lors de la transmission et que nous recevons le bloc suivant:

` `|Col 1|Col 2|Col 3|Col 4
---|---|---|---|---
<b>Row 1</b>|1<sub>0000</sub>|1<sub>0001</sub>|0<sub>0010</sub>|0<sub>0011</sub>
<b>Row 2</b>|0<sub>0100</sub>|1<sub>0101</sub>|0<sub>0110</sub>|0<sub>0111</sub>
<b>Row 3</b>|1<sub>1000</sub>|1<sub>1001</sub>|0<sub>1010</sub>|1<sub>1011</sub>
<b>Row 4</b>|1<sub>1100</sub>|0<sub>1101</sub>|0<sub>1110</sub>|1<sub>1111</sub>

Vérifions nos équations:
- P<sub>0001</sub>: 1 = 0<sub>0011</sub> ^ 1<sub>0101</sub> ^ 0<sub>0111</sub> ^ 1<sub>1001</sub> ^ 1<sub>1011</sub> ^ 0<sub>1101</sub> ^ 1<sub>1111</sub> (!!!)
- P<sub>0010</sub>: 0 = 0<sub>0011</sub> ^ 0<sub>0110</sub> ^ 0<sub>0111</sub> ^ 0<sub>1010</sub> ^ 1<sub>1011</sub> ^ 0<sub>1110</sub> ^ 1<sub>1111</sub>
- P<sub>0100</sub>: 0 = 1<sub>0101</sub> ^ 0<sub>0110</sub> ^ 0<sub>0111</sub> ^ 1<sub>1100</sub> ^ 0<sub>1101</sub> ^ 0<sub>1110</sub> ^ 1<sub>1111</sub> (!!!)
- P<sub>1000</sub>: 1 = 1<sub>1001</sub> ^ 0<sub>1010</sub> ^ 1<sub>1011</sub> ^ 1<sub>1100</sub> ^ 0<sub>1101</sub> ^ 0<sub>1110</sub> ^ 1<sub>1111</sub> (!!!)

Nous pouvons voir que P<sub>0001</sub>, P<sub>0010</sub>, et P<sub>1000</sub> ne tiennent pas, mais que G<sub>0000</sub> tient! Ce cas démontre qu'il y a 2 bits renversés, mais que nous ne pouvons pas trouver leur position. Nous devons donc demander au crawler de renvoyer ce paquet.

## <a id="helpme"/>Aide

Assurez-vous d'inclure les étapes pour compiler et/ou rouler votre code. Ce peut être un Makefile, une CMakeLists.txt, ou même une liste de commandes. Si je ne peux pas facilement rouler votre code, je ne le corrigerai pas.

Vous avez accès à Internet, et la librairie standard de votre langage. Rien d'autre. Si je dois installer une librairie tierce pour rouler votre code, vous aurez droit à 0 points.

Le fichier `processify.py` ne vous sera pas utile. C'est un décorateur pour rouler une fonction dans un processus séparé.

Pour vous aider à tester, le comportement du crawler peut être contrôlé avec des variables d'environnement. Une valeur invalide est équivalente à ne pas avoir de valeur du tout.

* `CRWL_METADATA`: Si présente, le crawler enverra toujours les paquets de métadonnées (MODE, SEQN) avant de transmettre les données.
* `CRWL_MODE`: Si présente, le crawler enverra toujours un paquet MODE avec la valeur spécifiée.
* `CRWL_SEQN`: Si présente, le crawler enverra toujours un paquet SEQN avec la valeur spécifiée.
* `CRWL_FORCE_OUT_OF_ORDER`: Si présente, le crawler enverra des paquets dans le mauvais ordre.
* `CRWL_FORCE_ERROR`: Si présente, le crawler ajoutera des erreurs dans les paquets.
* `CRWL_FORCE_DUPLICATE`: Si présente, le crawler téléversera un fichier déjà téléversé.
* `CRWL_NB_CRAWLERS`: Le script de test générera ce nombre de crawlers. La valeur par défaut est 2.
* `CRWL_NO_HAMMING`: Le crawler ne calculera pas la parité des paquets (les bits de parité ne seront pas dans la charge utile). La valeur par défaut est que la parité est calculée et ajoutée aux paquets.
* `CRWL_NO_RLE`: Le crawler n'encodera pas les données par plage. La valeur par défaut est que les données seront encodées par plage.
* `CRWL_RX_TIMEOUT`: Le temps en secondes que le crawler attendra une réponse avant de lancer une erreur. La valeur par défaut est 5. Ceci est aussi le temps d'attente après l'envoi du dernier paquet DATA.
* `CRWL_DEBUG`: Si présente, le crawler imprimera des données de débogage.

Pièges courant à éviter:
* Tout entier envoyé doit être envoyé en ordre des octets du réseau (voir `man htons`)
* Tout entier reçu doit être converti en ordre des octets de l'hôte (voir `man ntohs`)
* Les bits de parité devraient être _retirés_ des données avant d'être écrites au disque
* Assurez-vous que le tampon de mémoire (buffer) pour recevoir les requêtes du crawler est assez large (>= 508 octets), sinon le paquet est perdu
* Le crawler ne termine pas le type de message avec un caractère nul

### <a id="workflow"/>Flux de travail

Le flux de travail typique pour traiter un seul téléversement pourrait ressembler à:
1. Recevoir le paquet UPLD.
2. Recevoir les métadonnées du téléversement, s'il y a lieu.
3. Recevoir les données.
4. Réordonner les paquets si nécessaire.
5. Envoyer les numéros de séquence manquants si nécessaire.
6. Retourner à l'étape 3 jusqu'à la fin du téléversement.

## <a id="grading"/>Correction

Requis|Points
-----|----:
Traiter un seul téléversement|20
Traiter plusieurs téléversements du même crawler|15
Traiter plusieurs crawlers à la fois|10
Envoyer des réponses correctes/valides au crawler|10
Valider les paquets reçus|15
Traiter des fichiers doublons|5
Traiter le mode compressé|5
Corriger des erreurs de 1 bit|5
Détecter des erreurs de 2 bits|5
Traiter des paquets dans le mauvais ordre|5
Traiter la perte de paquets|5

Votre directeur de compétition, Philippe Gorley
