# Obiettivo e contesto

Sistema RAG (Retrieval-Augmented Generation) specializzato **solo** sulla documentazione/manuale di un gestionale. Target: helpdesk, consulenti applicativi e utenti finali che pongono domande su **parametri**, **procedure** e **errori** dell’applicativo.

Assunzioni chiave:

* Fonte: manuali HTML/PDF/Markdown, release notes, guide operative, FAQ ufficiali.
* Lingua principale: **italiano** (con acronimi tipici: IVA, PEC, CIG, CIG, PA, F24, Mav, SDI ecc.).
* Dominio ristretto (un singolo prodotto), con versioni (es. v10.5, v10.6) e moduli (es. Contabilità, Fatturazione, Magazzino, HR).

---

# Architettura ad alto livello

1. **Ingestione** → Crawling/lettura URL e PDF → Estrazione testo + strutture (titoli, tabelle, immagini con didascalie) → normalizzazione.
2. **Chunking strutturale** → sezioni/parametri/procedure → chunk gerarchici (parent/child) con overlap controllato.
3. **Indicizzazione ibrida** → **Vector** + **BM25** (+ sparse learned opzionale) con metadati ricchi.
4. **Retrieval adattivo** → classifica query (Parametro / Procedura / Errore) → profilo K, filtri e booster diversi.
5. **Reranking** → cross-encoder/reranker multilingue.
6. **Generazione** → template di risposta tipizzati e **citazioni obbligatorie** con ancore.
7. **Freshness & versioning** → aggiornamenti incrementali, ETag/Last-Modified, filtri per versione/modulo.
8. **Valutazione e guardrail** → metriche IR + groundedness, anti-injection, fallback “Answer only if supported”.

---

# Schema metadati (consigliato)

Per ogni chunk:

```json
{
  "id": "contabilita/impostazioni/iva#h2-registri-iva:ch-03",
  "title": "Registri IVA",
  "breadcrumbs": ["Contabilità", "Impostazioni", "IVA"],
  "section_level": 2,
  "section_path": "contabilita/impostazioni/iva",
  "content_type": "procedure|parameter|concept|faq|error",
  "version_min": "10.5",
  "version_max": "10.7",
  "module": "Contabilità",
  "param_name": "Aliquota predefinita vendite",
  "ui_path": "Menu > Contabilità > Impostazioni > IVA",
  "page_range": [34, 36],
  "anchor": "#registri-iva",
  "lang": "it",
  "hash": "sha1:...",
  "updated_at": "2025-09-01"
}
```

---

# Ingestione & parsing

**Fonti**: URL whitelisted (docs aziendali), PDF manuali, release notes.

**Parsing HTML**: rimuovere nav/aside/footer/cookie; mantenere H1–H4, liste, note “Attenzione/Nota”, code blocks, tabelle.

**Parsing PDF**: PyMuPDF + estrazione heading per font/size; preservare **page_number**; estrarre tabelle (Camelot/Tabula) e convertirle in Markdown; salvare immagini con **caption** → OCR per screenshots di UI se contengono testo chiave (etichetta campo).

**Dedup/normalizzazione**:

* Canonical URL, normalizza whitespace, unisci paragrafi spezzati.
* Soft dedupe: cosine sim > 0.92 = duplicato.
* Unifica glosse (es. “N°” vs “Numero”).

**Controllo aggiornamenti**:

* Usa ETag/Last-Modified; diffs a livello di **section**; re-embedding solo dei chunk cambiati.

---

# Chunking specializzato per manuali di gestionale

**Principi**:

* Chunk **semantici e stabili** su confini H2/H3.
* Doppio livello: **Parent (sezione intera)** + **Child (unità atomica)** per steps/parametri.
* Overlap minimo ma informativo.

**Parametri consigliati**

* **Parent chunks**: 800–1.200 token, **overlap 80–120** token.
* **Child procedural** (passi): 250–450 token, **overlap 40–60** token.
* **Child parameter** (schede impostazioni): 120–280 token, **no overlap** (parametri sono record atomici).
* **Tabelle**: mantieni in chunk dedicati; se molto lunghe, splitta per righe affini (max 25 righe per chunk).
* **Figure/UI**: crea un mini-chunk con caption + eventuale OCR dei label.

**Heuristics**:

* Spezzare **solo** ai confini di heading o bullet list significative (— non a metà frase).
* Raggruppa “Prerequisiti/Limitazioni” nello stesso chunk del procedimento a cui si riferiscono.
* Crea un **glossario**: un chunk per voce (sigle, acronimi, sinonimi).

---

# Doppio indice: non strutturato + knowledge base di parametri

Oltre all’indice testuale, costruisci una **KB strutturata** dei parametri (estrazione durante ingestion):

```yaml
- name: Aliquota predefinita vendite
  module: Contabilità
  section_path: contabilita/impostazioni/iva
  ui_path: Menu > Contabilità > Impostazioni > IVA
  type: enum
  allowed_values: [22%, 10%, 4%]
  default: 22%
  constraints: "Applicata se il cliente non ha aliquota specifica"
  dependencies: ["Profilo fiscale cliente"]
  since: 10.5
  until: 10.7
  related_errors: ["IVA-102 Aliquota mancante"]
  doc_anchor: "#aliquota-predefinita"
```

Usi quindi **dual retrieval**: se la query contiene segni di “parametro” ("come si imposta…", "dove trovo…", "valori ammessi…"), interroga prima la KB; altrimenti l’indice testuale.

---

# Embedding & indicizzazione

**Obiettivi**: robustezza in italiano, buona resa su termini tecnici e abbreviazioni.

* **Embeddings**: modelli multilingue moderni (e.g. *bge-m3* o *multilingual-e5-large*). Abilita **normalizzazione L2**.
* **Vector DB**: Qdrant o Weaviate (filtri, payload ricchi, HNSW). Dimensioni secondo modello (768–1024). HNSW: `M=64`, `efConstruction=256`, `ef=64` iniziale.
* **Indice lessicale**: BM25 (es. Elasticsearch/OpenSearch) con analizzatore italiano (stopwords, stemming leggero).
* **Indice sparso learned (opz.)**: SPLADE/uniCOIL per boost delle keyword rare (codici errore, sigle).

**Strategia ibrida**:

* Recupera `k_dense=40` (vector) + `k_lex=20` (BM25) → unione → **re-ranking** top 30.
* Booster per campi: `title x1.4`, `breadcrumbs x1.2`, match esatto su `param_name x2.0`, `error_code x2.5`.
* Filtri hard: `version in [user_version]`, `module in [user_module?]` (se forniti dall’utente o profilo).

---

# Classificazione della query (routing)

Regole/indicazioni:

* **Parametro**: pattern ["param", "impostaz", "valori", "predefin"], presenza di `?=`, `default`, `range`.
* **Procedura**: verbi d’azione (configurare, stampare, generare, inviare, contabilizzare), presenza di sequenze (passo/passi/step).
* **Errore**: pattern `[A-Z]{2,4}-?\d{2,4}` o parole “errore/avviso/codice”.

Routing outcome:

* Parametro → priorità KB parametri + child-parameter chunks.
* Procedura → child-procedural + parent.
* Errore → chunks “error” + release notes collegate.

---

# Re-ranking

* Cross-encoder multilingue (es. **bge-reranker-large** o **mono-multilingual-msmarco**). Top 30 → Top 8–10.
* Penalità per risultati della **stessa sezione** oltre 2 elementi (diversificazione, `xQuAD`).
* Bonus a contenuti con **ancora** presente nel testo della query.

---

# Costruzione del contesto (Context Builder)

Budget: adegua al contesto del LLM (es. 8k–32k token). Consigliato:

* **Max 6** chunk: 1 parent + 3–5 child pertinenti.
* Prepend un **riassunto estrattivo** della sezione (2–3 frasi) calcolato all’indicizzazione per comprimere.
* Includi **metadati** e **ancore** (URL#anchor o path + pagina) per citazioni.

---

# Generazione: template di risposta

**Parametro (template)**

* Nome parametro, Modulo, Percorso UI
* Descrizione sintetica (1–2 frasi)
* **Valori ammessi** / default / formato
* Dipendenze/Prerequisiti
* Effetti collaterali e note operative
* Versioni in cui esiste
* Collegamenti a errori correlati
* Citazioni (2–3) con ancore

**Procedura (template)**

* Scopo e prerequisiti
* Passi numerati (max 8, compatti)
* Deviazioni/varianti (se fatturazione elettronica vs estero, ecc.)
* Check finale / output atteso
* Citazioni

**Errore (template)**

* Codice e messaggio
* Causa probabile
* Passi di risoluzione
* Prevenzione
* Citazioni

**Regole anti-hallucination**

* “Se l’informazione non è nelle citazioni → rispondi che non è disponibile e proponi sezioni correlate.”
* Mai inventare valori ammessi o percorsi UI.

---

# Guardrail & sicurezza

* **Whitelisting dei domini** (solo docs ufficiali).
* **Filtro prompt-injection** sui contenuti recuperati (regex per pattern malevoli; sandbox del parser).
* **Redaction** di eventuali dati sensibili nei manuali interni.
* **Rate limit** e rispetto robots.

---

# Aggiornamenti, versioning e varianti

* Ogni chunk porta `version_min/max`. Filtra in retrieval sulla versione utente (profilo o domanda: “v10.6”).
* Migrazioni: mantieni mapping “vecchio → nuovo nome” parametro.
* **Incremental indexing** giornaliero: controlla sitemap/release notes; se cambia una sezione, re-embedd **solo** i suoi chunk.
* Mantieni **history** per audit (chi ha risposto con quali citazioni).

---

# UI/UX consigliata

* Campo di ricerca con **modulo** e **versione** opzionali.
* Risposte con **pannello citazioni** (link profondi `#ancore`/pagina), pulsante “Apri sezione completa”.
* Pulsanti rapidi: “Mostra percorso UI”, “Valori ammessi”, “Copia comando/menu path”.
* Snippet evidenziati per **codici errore**.

---

# Valutazione (offline & online)

**Dataset**: genera 200–500 domande sintetiche per modulo (Parametro/Procedura/Errore) + 50 reali dal supporto.

**Metriche IR**: Recall@20 (≥0.9), nDCG@10 (≥0.6), MRR@10 (≥0.7) su giudizi livello sezione.

**Metriche generazione**: Answer Faithfulness, Context Precision/Recall, Citation Coverage (≥95%).

**Canary tests**: query-trappola (parametri inesistenti) → il sistema deve **rifiutare** con spiegazione.

---

# Stack consigliato (3 opzioni)

**A. Open-source, on-prem (consigliato)**

* Ingest: Python (Playwright, trafilatura), PyMuPDF, Camelot/Tabula
* Pipeline: Prefect/Airflow per job ETL
* Vector DB: **Qdrant** (HNSW, payload filters)
* Lexical: **OpenSearch/Elasticsearch** (analisi IT)
* Embeddings: **bge-m3** o **multilingual-e5-large**
* Reranker: **bge-reranker-large**
* Orchestrazione RAG: **LlamaIndex** o **Haystack**
* API: FastAPI

**B. Gestito (rapid delivery)**

* Vector: Pinecone/Weaviate Cloud
* Lexical: Elastic Cloud
* Embedding/Rerank: provider SaaS (se privacy consente)
* Orchestrazione: LangChain + serverless (Cloud Run/FaaS)

**C. Minimal (budget/POC)**

* Vector: FAISS + SQLite metadati
* Lexical: Tantivy/Lucene embedded
* Embedding: multilingual-MiniLM
* Rerank: cross-encoder base

---

# Parametri di riferimento (che puoi copiare)

* Chunk parent: **1.000** token, overlap **100**
* Chunk procedural: **350** token, overlap **50**
* Chunk parametro: **200** token, **0** overlap
* k_dense=40, k_lex=20 → rerank top 30 → **context 6**
* HNSW: M=64, efConstruction=256, efSearch=64
* BM25: k1=0.9, b=0.55 (stems leggeri IT)
* Reranker top_k=10
* Boost: title 1.4, breadcrumbs 1.2, param_name 2.0, error_code 2.5

---

# Pseudocodice della pipeline

```python
# Ingestion
for doc in sources:
    raw = fetch(doc)
    sections = parse_to_sections(raw)  # estrae H1–H4, tabelle, figure
    for sec in sections:
        parent = mk_parent_chunk(sec)
        index(parent)
        for unit in split_into_child_units(sec):  # passi, parametri, tabelle
            child = mk_child_chunk(unit)
            index(child)
        if is_parameter_section(sec):
            records = extract_parameters(sec)
            upsert_kb(records)

# Query time
q = user_query()
cls = classify(q)  # parameter/procedure/error
cands = hybrid_search(q, filters=version,module, boosts)
reranked = cross_encode(q, cands)[:10]
context = build_context(reranked, budget=6)
answer = generate_with_templates(q, context, cls)
return answer_with_citations(answer, context)
```

---

# Trucchi pratici & anti-dolorifici

* Mantieni **breadcrumb** coerenti: utili per filtri e UX.
* Estrai **percorsi di menu** come stringa standard ("Menu > Modulo > ...").
* Normalizza i **codici errore** (regex + uppercase). Indicizzali in campo dedicato.
* Pre-calcola **riassunti** per ogni sezione (2–3 frasi) per standing-up risposte brevi.
* Inserisci sinonimi IT ("impostazione", "settaggio", "configurazione").
* Sezione “**Cosa è cambiato in vX**” per release: tagga chunk con `changed_in=[v]` e preferiscili per query con “nuovo”, “da v10.6”.

---

# Roadmap di implementazione (4 sprint)

**S1 – Ingestion & Index**: crawler, parser HTML/PDF, chunking, vector+BM25, KB parametri (baseline).
**S2 – Retrieval avanzato**: hybrid + reranker, routing query, filtri versione/modulo.
**S3 – Generazione**: template tipizzati, citazioni, guardrail, UI minima.
**S4 – Qualità**: dataset valutazione, canary, dashboard metriche, incremental updates.

---