# titanfall2mod_no_body_no_reload

Add-on non ufficiale di **jshodanVR** per la campagna VR di Titanfall 2.

**Qui non è incluso l'installer di CircuitLord, né alcun suo eseguibile, DLL o asset. `Install.cmd` è soltanto il patcher di questo add-on: non installa e non scarica la mod VR base.**

La mod base deve essere ottenuta e installata separatamente dal **[GitHub ufficiale di CircuitLord](https://github.com/CircuitLord/CircuitLordVRModInstaller)**.

- Ripristina la ricarica gestita dal gioco, senza dover inserire il caricatore o azionare l'otturatore a mano in VR.
- Nasconde il corpo del pilota lasciando visibili mani, armi e oggetti.
- Chiude e rifinisce i polsi delle mani, senza i lembi elastici del primo prototipo.

**“no_reload” nel nome significa niente ricarica manuale VR: non significa munizioni infinite e non elimina la ricarica del gioco.**

## Versione della mod base richiesta

| Componente | Versione |
| --- | --- |
| **Mod base obbligatoria: CircuitLord Titanfall2VR** | **1.0.25, canale stabile** |
| Installer ufficiale di riferimento: CircuitLordVRModInstaller | **1.2.12** |
| Questo add-on | 1.0.1 |

**1.0.25 è la versione della mod VR; 1.2.12 è la versione del programma che la installa. Sono due numeri diversi.** Usare l'installer 1.2.12 non garantisce da solo che sia installata la mod corretta: selezionare Titanfall2VR 1.0.25 e controllare la versione effettivamente installata.

Installare prima il gioco e la mod base, quindi avviare la campagna VR almeno una volta e verificarne il funzionamento.

Per la mod base e il suo installer usare esclusivamente il **[repository GitHub dell'autore](https://github.com/CircuitLord/CircuitLordVRModInstaller)**, nella sua sezione Releases. Non sono ospitati o allegati in questo progetto.

Il patcher verifica anche l'hash SHA-256 esatto della DLL e dei due modelli originali. Se i file sono diversi, si ferma invece di provare a modificarli. **Non è compatibile automaticamente con altre versioni, beta o DLL già modificate.**

## Installazione

1. Scaricare questo progetto con **Code → Download ZIP** ed estrarlo completamente.
2. Chiudere Titanfall 2.
3. Eseguire **Install.cmd (il nostro patcher, non l'installer di CircuitLord)** e incollare il percorso della cartella che contiene `Titanfall2.exe`.
4. Attendere il messaggio di completamento, poi avviare il gioco tramite il consueto launcher VR.

Richiede Windows 10/11 **x64**, PowerShell 5.1 o successivo e una connessione Internet al primo avvio. Non serve installare Python o Node.js a livello di sistema: lo script scarica copie portabili e librerie open source, con versioni e checksum bloccati, nella cartella locale dell'utente. Non modifica il PATH di Windows e non richiede normalmente privilegi di amministratore.

**Check.cmd** verifica la compatibilità senza modificare il gioco. Al primo utilizzo può scaricare il solo runtime Python.

La modifica viene applicata al profilo `TF2VR`. Il patcher salva una copia della DLL originale e una ricevuta locale in:

```text
Titanfall2/TF2VR/titanfall2mod_no_body_no_reload.backup/
```

I modelli generati localmente vengono installati come mod separata:

```text
Titanfall2/TF2VR/mods/titanfall2mod_no_body_no_reload/
```

## Ripristino

Chiudere il gioco ed eseguire **Uninstall.cmd**, indicando la stessa cartella. Ripristina la DLL originale e rimuove i soli file generati da questo add-on. Se trova file aggiornati o modificati in seguito, interrompe il ripristino per non sovrascriverli.

Non cancellare la cartella di backup prima del ripristino. Le copie portabili dei runtime rimangono in `%LOCALAPPDATA%\titanfall2mod_no_body_no_reload\runtime` e possono essere rimosse manualmente quando non servono più.

## Cosa viene distribuito

Questo repository contiene **codice del patcher, istruzioni, checksum e documentazione**. Non contiene la DLL della mod VR, eseguibili della mod, modelli del gioco, texture o archivi VPK, né completi né modificati.

Il nostro patcher legge la DLL e gli archivi VPK già presenti sul PC dell'utente, genera le modifiche sul posto e crea backup esclusivamente locali. Non scarica l'installer di CircuitLord, la sua mod VR o i modelli, da questo repository o da altri siti. I soli download automatici sono strumenti open source elencati in `runtime-lock.json`. Non caricare su GitHub i file generati, i backup o le cartelle temporanee.

La ricarica automatica modifica tre chiamate della DLL compatibile. La modalità solo mani viene generata dai due modelli locali del pilota; posizioni e pesi dei soli bordi dei polsi vengono rifiniti per mantenerne la chiusura durante l'animazione.

## Compatibilità e limiti

- Provato su una specifica installazione di Titanfall2VR 1.0.25 e sui due modelli identificati in `compatibility.json`.
- La verifica dei file non sostituisce una prova su ogni visore/controller e in ogni sequenza della campagna.
- Gli aggiornamenti della mod base possono sostituire la DLL. Prima di aggiornare, disinstallare questo add-on; una nuova versione della mod richiede una nuova verifica di compatibilità.
- Evitare altre modifiche che sostituiscono gli stessi modelli del pilota. Il patcher non modifica i salvataggi.

## Crediti

Titanfall 2 è un gioco di Respawn Entertainment / Electronic Arts. La mod VR base è **Titanfall2VR di CircuitLord** e deve essere installata separatamente dalla sua fonte ufficiale. Questo progetto non è affiliato, approvato o mantenuto dagli autori del gioco o della mod VR.

Il lettore VPK è TFVPKTool di barnabwhy, scaricato separatamente dalla release originale. Vedere [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) per dipendenze e licenze. La licenza di questo repository riguarda il suo codice e non concede diritti sui file originali del gioco o della mod.

## Sviluppo

Il codice richiede Python 3.12 e NumPy 2.3.5; l'estrazione VPK usa Node.js e TFVPKTool 0.3.1. I runtime sono bloccati in `runtime-lock.json`. Eseguire i test di gestione dei file con:

```text
python -m unittest discover -s tests -v
```

I test pubblici usano file sintetici: non richiedono e non includono asset del gioco.
