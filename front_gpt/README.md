# Frontend RAG Gestionale (Angular)

Frontend enterprise-ready per il sistema RAG Gestionale, realizzato con Angular 20 e Material Design. L'applicazione replica in chiave SPA le funzionalità fornite dall'interfaccia Streamlit, adottando best practice di architettura e UX.

## Struttura

- `src/app/core` – servizi condivisi, modelli tipizzati e stato applicativo basato su Signals.
- `src/app/features` – feature standalone (`search`, `ingest`, `analytics`, `history`). Ogni feature è incapsulata in componenti standalone e lazy-ready.
- `src/app/shared` – componenti riutilizzabili (es. `api-settings`, `metric-card`, `source-list`).
- `src/environments` – configurazioni ambientali con API endpoint predefinito.

## Funzionalità principali

- **Ricerca**: form avanzato con filtri, gestione LLM opzionale, rendering risposta e fonti.
- **Ingestione**: inserimento massivo URL, progress feedback, statistiche e cronologia locale.
- **Analisi**: dashboard con metriche sistema, distribuzione tipi di query, configurazioni backend.
- **Cronologia**: elenco ricerche eseguite localmente con copie rapide.

## Avvio progetto

```bash
cd front_gpt
npm install
npm start
```

Il server di sviluppo sarà disponibile su `http://localhost:4200`. Configura l'endpoint API tramite il pannello laterale o l'icona in toolbar.

## Best practice adottate

- Componenti standalone con Change Detection `OnPush` e Signals per stato reactive.
- Tipizzazione completa dei payload FastAPI (modelli condivisi).
- Interceptor HTTP per gestione errori e notifiche contestuali.
- Design system coerente tramite Angular Material theming.
- Suddivisione core/shared/features per evolvere in lazy loading o micro frontends.

## Prossimi passi suggeriti

- Integrare autenticazione/ruoli se richiesto.
- Collegare analytics a metriche reali via `/stats` (grafici custom).
- Aggiungere test unitari e E2E (Jasmine/Cypress) sulle feature critiche.
