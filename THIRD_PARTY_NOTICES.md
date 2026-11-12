# Runtime scaricati separatamente

Questo repository non contiene questi binari. `Setup-Run.ps1` li scarica sul PC dell'utente dalle fonti indicate in `runtime-lock.json` e ne verifica gli SHA-256 prima dell'estrazione.

| Componente | Versione | Fonte e licenza |
| --- | --- | --- |
| Python embeddable Windows x64 | 3.12.10 | [python.org](https://www.python.org/downloads/release/python-31210/), PSF License; licenza inclusa nell'archivio ufficiale |
| NumPy Windows CPython 3.12 x64 | 2.3.5 | [PyPI](https://pypi.org/project/numpy/2.3.5/), BSD-3-Clause e avvisi inclusi nel wheel |
| Node.js Windows x64 | 22.16.0 | [nodejs.org](https://nodejs.org/dist/v22.16.0/), MIT e avvisi delle dipendenze inclusi nell'archivio |
| TFVPKTool | 0.3.1 | [release e codice sorgente](https://github.com/barnabwhy/TFVPKTool/releases/tag/0.3.1), GPL-3.0; `LICENSE.md` incluso nell'archivio scaricato |

TFVPKTool viene usato da un processo Node separato per leggere gli archivi già installati. Non viene scaricato alcun asset del gioco. Conservare gli avvisi di licenza presenti nei runtime se si distribuiscono copie dei runtime separatamente.
