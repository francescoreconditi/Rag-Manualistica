"""
Streamlit App per Sistema RAG Gestionale
Interface web completa per ingestione documenti e ricerca intelligente
"""

# Carica variabili d'ambiente dal file .env
import os
from pathlib import Path

from dotenv import load_dotenv

# Carica il file .env dalla root del progetto
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

# IMPORTANTE: importa settings DOPO aver caricato .env
from src.rag_gestionale.config.settings import Settings


# Forza ricreazione delle impostazioni dopo aver caricato .env
def get_fresh_settings():
    return Settings()


import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict, List

import httpx
import pandas as pd
import streamlit as st

# Configurazione pagina
st.set_page_config(
    page_title="RAG Gestionale - Sistema Documentazione",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS personalizzato
st.markdown(
    """
<style>
    .main {
        padding-top: 2rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f0f2f6;
        border-radius: 4px;
        padding: 10px 20px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1f77b4;
        color: white;
    }
    .source-card {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
    }
    .answer-box {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
    }
    .url-input-area {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Configurazione API
API_BASE_URL = st.sidebar.text_input(
    "🔗 URL API", value="http://localhost:8000", help="URL base del sistema RAG"
)

# Inizializza session state
if "search_history" not in st.session_state:
    st.session_state.search_history = []
if "ingested_urls" not in st.session_state:
    st.session_state.ingested_urls = []
if "last_search_results" not in st.session_state:
    st.session_state.last_search_results = None


async def check_api_health():
    """Verifica stato API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/health", timeout=5.0)
            return response.status_code == 200, response.json()
    except Exception as e:
        return False, str(e)


async def ingest_urls(urls: List[str]):
    """Ingestione URLs nel sistema"""
    try:
        # Timeout aumentato a 30 minuti per ingestione di pagine HTML grosse
        async with httpx.AsyncClient(timeout=1800.0) as client:
            response = await client.post(f"{API_BASE_URL}/ingest", json={"urls": urls})
            return response.json()
    except httpx.TimeoutException as e:
        return {"status": "error", "message": f"Timeout dopo 30 minuti: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def search_rag(
    query: str,
    filters: Dict[str, Any] = None,
    top_k: int = 5,
    llm_config: Dict[str, Any] = None,
):
    """Ricerca nel sistema RAG"""
    try:
        # Timeout aumentato a 600s (10 minuti) per gestire LLM e processing immagini
        async with httpx.AsyncClient(timeout=600.0) as client:
            payload = {
                "query": query,
                "filters": filters or {},
                "top_k": top_k,
                "include_sources": True,
            }

            # Aggiungi configurazione LLM se fornita
            if llm_config:
                payload["llm_config"] = llm_config

            response = await client.post(
                f"{API_BASE_URL}/search",
                json=payload,
            )

            # Log del response per debugging
            if response.status_code != 200:
                error_detail = f"Status {response.status_code}: {response.text[:500]}"
                return {"error": error_detail}

            return response.json()
    except httpx.TimeoutException as e:
        return {"error": f"Timeout dopo 10 minuti: {str(e)}"}
    except httpx.HTTPError as e:
        return {"error": f"Errore HTTP: {str(e)}"}
    except Exception as e:
        return {"error": f"Errore inatteso ({type(e).__name__}): {str(e)}"}


async def get_system_stats():
    """Ottieni statistiche sistema"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/stats")
            return response.json()
    except Exception as e:
        return {}


def main():
    """App principale"""

    # Header
    st.title("🤖 RAG Gestionale - Sistema Documentazione")
    st.markdown(
        "**Sistema intelligente per ricerca nella documentazione di gestionali**"
    )

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurazione")

        # Health check
        with st.spinner("Verifica connessione..."):
            is_healthy, health_data = asyncio.run(check_api_health())

        if is_healthy:
            st.success("✅ Sistema operativo")
            if isinstance(health_data, dict):
                with st.expander("📊 Statistiche Sistema"):
                    if "stats" in health_data:
                        stats = health_data["stats"]
                        if (
                            "retrieval" in stats
                            and "vector_store" in stats["retrieval"]
                        ):
                            vs_stats = stats["retrieval"]["vector_store"]
                            st.metric(
                                "Documenti indicizzati", vs_stats.get("total_points", 0)
                            )
        else:
            st.error(f"❌ Sistema non disponibile")
            st.info("Avviare il server con: `python -m src.rag_gestionale.api.main`")

        st.divider()

        # Filtri ricerca
        st.header("🔍 Filtri Ricerca")

        module_filter = st.selectbox(
            "Modulo",
            [
                "Tutti",
                "Contabilità",
                "Fatturazione",
                "Magazzino",
                "HR",
                "Desktop Teseo7",
            ],
            help="Filtra risultati per modulo",
        )

        content_type_filter = st.selectbox(
            "Tipo contenuto",
            ["Tutti", "parameter", "procedure", "error", "general"],
            help="Filtra per tipo di contenuto",
        )

        max_results = st.slider(
            "Risultati massimi",
            min_value=1,
            max_value=20,
            value=5,
            help="Numero massimo di risultati da restituire",
        )

        st.divider()

        # Configurazione LLM
        st.header("🧠 LLM (OpenAI)")

        # Controlla configurazione da environment
        settings = get_fresh_settings()

        # Leggi configurazione LLM (con fallback diretto alle variabili d'ambiente)
        env_llm_enabled = (
            settings.llm.enabled
            or os.environ.get("RAG_LLM__ENABLED", "false").lower() == "true"
        )
        env_api_key = settings.llm.api_key or os.environ.get("RAG_LLM__API_KEY", "")
        env_generation_mode = settings.generation.generation_mode or os.environ.get(
            "RAG_GENERATION__GENERATION_MODE", "template"
        )

        # Mostra stato configurazione
        if env_api_key:
            st.success(f"✅ API Key configurata tramite environment (.env)")
            st.info(f"🔧 Modalità: {env_generation_mode}")
            st.info(f"🤖 Modello: {settings.llm.model_name}")

            # Controllo per sovrascrivere modalità
            override_mode = st.checkbox(
                "Sovrascrivere modalità generazione",
                value=False,
                help="Temporaneamente cambia modalità per questa sessione",
            )

            if override_mode:
                generation_mode = st.selectbox(
                    "Modalità generazione (override)",
                    ["hybrid", "llm", "template"],
                    index=["hybrid", "llm", "template"].index(env_generation_mode),
                    help="hybrid: automatico, llm: sempre LLM, template: sempre template",
                )
                llm_enabled = generation_mode != "template"
                openai_api_key = env_api_key
            else:
                generation_mode = env_generation_mode
                llm_enabled = env_llm_enabled and bool(env_api_key)
                openai_api_key = env_api_key
        else:
            st.warning("⚠️ API Key OpenAI non configurata nel file .env")
            st.info("💡 Aggiungi RAG_LLM__API_KEY=your-key nel file .env")

            # Fallback a input manuale se non configurato
            llm_enabled = st.checkbox(
                "Abilita LLM (input manuale)",
                value=False,
                help="Configurazione temporanea - meglio usare .env",
            )

            if llm_enabled:
                openai_api_key = st.text_input(
                    "API Key OpenAI (temporanea)",
                    type="password",
                    help="Meglio configurare nel file .env",
                    placeholder="sk-...",
                )
                generation_mode = st.selectbox(
                    "Modalità generazione",
                    ["hybrid", "llm", "template"],
                    index=0,
                    help="hybrid: automatico, llm: sempre LLM, template: sempre template",
                )
            else:
                openai_api_key = ""
                generation_mode = "template"

        st.divider()

        # URL memorizzati
        if st.session_state.ingested_urls:
            st.header("📚 Documenti Indicizzati")
            for url in st.session_state.ingested_urls[-5:]:  # Ultimi 5
                st.caption(f"• {url[:50]}...")

    # Tabs principali
    tab1, tab2, tab3, tab4 = st.tabs(
        ["🔍 Ricerca", "📥 Ingestione", "📊 Analisi", "📜 Cronologia"]
    )

    # Tab 1: Ricerca
    with tab1:
        col1, col2 = st.columns([3, 1])

        with col1:
            query = st.text_input(
                "💬 Fai una domanda al sistema",
                placeholder="Es: Come impostare l'aliquota IVA predefinita?",
                help="Inserisci la tua domanda sulla documentazione",
            )

        with col2:
            search_button = st.button(
                "🔎 Cerca", type="primary", width="stretch", disabled=not query
            )

        if search_button and query:
            with st.spinner("🔄 Ricerca in corso..."):
                # Prepara filtri
                filters = {}
                if module_filter != "Tutti":
                    filters["module"] = module_filter
                if content_type_filter != "Tutti":
                    filters["content_type"] = content_type_filter

                # Prepara configurazione LLM
                llm_config = None
                if llm_enabled and openai_api_key:
                    llm_config = {
                        "enabled": True,
                        "api_key": openai_api_key,
                        "generation_mode": generation_mode,
                    }

                # Esegui ricerca
                start_time = time.time()
                result = asyncio.run(
                    search_rag(query, filters, max_results, llm_config)
                )
                search_time = time.time() - start_time

                if "error" in result:
                    st.error(f"❌ Errore: {result['error']}")
                else:
                    # Salva in session state
                    st.session_state.last_search_results = result
                    st.session_state.search_history.append(
                        {
                            "query": query,
                            "timestamp": datetime.now().isoformat(),
                            "confidence": result.get("confidence", 0),
                        }
                    )

                    # Mostra risposta
                    st.markdown("### 📋 Risposta")

                    # Box risposta con metriche
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.info(
                            f"**Tipo Query**: {result.get('query_type', 'general')}"
                        )
                    with col2:
                        confidence = result.get("confidence", 0)
                        st.metric("Confidenza", f"{confidence:.2%}")
                    with col3:
                        st.metric("Tempo", f"{search_time:.2f}s")

                    # Risposta principale
                    st.markdown('<div class="answer-box">', unsafe_allow_html=True)
                    st.markdown(result.get("answer", "Nessuna risposta"))
                    st.markdown("</div>", unsafe_allow_html=True)

                    # Fonti
                    if result.get("sources"):
                        st.markdown("### 📚 Fonti")

                        sources_df = []
                        for idx, source in enumerate(result["sources"], 1):
                            chunk_data = source.get("chunk", {})
                            metadata = chunk_data.get("metadata", {})

                            # Conta immagini per questa fonte
                            source_images = source.get("images", [])
                            img_count_text = (
                                f" • {len(source_images)} immagini"
                                if source_images
                                else ""
                            )

                            with st.expander(
                                f"Fonte {idx}: {metadata.get('title', 'N/A')} (Score: {source.get('score', 0):.3f}){img_count_text}"
                            ):
                                col1, col2 = st.columns([3, 1])

                                with col1:
                                    st.markdown(
                                        f"**Modulo**: {metadata.get('module', 'N/A')}"
                                    )
                                    st.markdown(
                                        f"**Tipo**: {metadata.get('content_type', 'N/A')}"
                                    )
                                    st.markdown(
                                        f"**URL**: [{metadata.get('source_url', 'N/A')}]({metadata.get('source_url', '#')})"
                                    )

                                with col2:
                                    st.metric(
                                        "Rilevanza", f"{source.get('score', 0):.3f}"
                                    )

                                # Mostra immagini prima del testo (se presenti)
                                if source_images:
                                    st.divider()
                                    st.markdown(
                                        f"**🖼️ Immagini associate** ({len(source_images)})"
                                    )

                                    # Crea colonne per mostrare immagini in griglia
                                    num_images = len(source_images)
                                    cols_per_row = 2
                                    num_rows = (
                                        num_images + cols_per_row - 1
                                    ) // cols_per_row

                                    for row_idx in range(num_rows):
                                        cols = st.columns(cols_per_row)
                                        for col_idx in range(cols_per_row):
                                            img_idx = row_idx * cols_per_row + col_idx
                                            if img_idx < num_images:
                                                img_data = source_images[img_idx]
                                                with cols[col_idx]:
                                                    # URL immagine dal backend
                                                    img_url = img_data.get(
                                                        "image_url", ""
                                                    )
                                                    if img_url:
                                                        # Costruisci URL completo
                                                        full_img_url = (
                                                            f"{API_BASE_URL}{img_url}"
                                                        )
                                                        try:
                                                            st.image(
                                                                full_img_url,
                                                                use_container_width=True,
                                                            )
                                                            # Info sotto l'immagine
                                                            st.caption(
                                                                f"📐 {img_data.get('width', 0)}x{img_data.get('height', 0)} • "
                                                                f"{img_data.get('format', 'N/A').upper()}"
                                                            )
                                                        except Exception as e:
                                                            st.warning(
                                                                f"Errore: {str(e)[:50]}"
                                                            )

                                st.divider()

                                # Mostra estratto del contenuto
                                content = chunk_data.get("content", "")[:500] + "..."
                                st.text_area(
                                    "Estratto contenuto testuale",
                                    content,
                                    height=150,
                                    disabled=True,
                                    key=f"extract_{chunk_data.get('id', idx)}",
                                )

                            # Aggiungi a dataframe
                            sources_df.append(
                                {
                                    "Titolo": metadata.get("title", "N/A"),
                                    "Modulo": metadata.get("module", "N/A"),
                                    "Score": f"{source.get('score', 0):.3f}",
                                    "URL": metadata.get("source_url", "N/A"),
                                }
                            )

                        # Tabella riassuntiva fonti
                        if sources_df:
                            st.markdown("#### 📊 Riepilogo Fonti")
                            st.dataframe(
                                pd.DataFrame(sources_df),
                                width="stretch",
                                hide_index=True,
                            )

    # Tab 2: Ingestione
    with tab2:
        st.header("📥 Ingestione Documenti")
        st.markdown("Aggiungi nuovi documenti al sistema inserendo gli URL")

        # Area input URL multipli
        st.markdown('<div class="url-input-area">', unsafe_allow_html=True)
        urls_input = st.text_area(
            "🔗 Inserisci URL (uno per riga)",
            height=200,
            placeholder="""https://cassiopea.centrosistemi.it/zcswiki/index.php/DesktopTeseo7_Comando_Editor_Query
https://cassiopea.centrosistemi.it/zcswiki/index.php/DesktopTeseo7_Configurazione
https://docs.example.com/manuale_contabilita.pdf""",
            help="Inserisci uno o più URL di documentazione, uno per riga",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            # Conteggio URL
            urls_list = [url.strip() for url in urls_input.split("\n") if url.strip()]
            st.info(f"📊 {len(urls_list)} URL inseriti")

        with col2:
            clear_button = st.button("🗑️ Pulisci", width="stretch")
            if clear_button:
                st.rerun()

        with col3:
            ingest_button = st.button(
                "📤 Avvia Ingestione",
                type="primary",
                width="stretch",
                disabled=len(urls_list) == 0,
            )

        if ingest_button and urls_list:
            with st.spinner(f"🔄 Ingestione di {len(urls_list)} URL in corso..."):
                progress_bar = st.progress(0)
                status_text = st.empty()

                # Simula progresso (in produzione userai WebSocket o polling)
                for i, url in enumerate(urls_list):
                    status_text.text(f"Elaborazione: {url[:50]}...")
                    progress_bar.progress((i + 1) / len(urls_list))
                    time.sleep(0.5)  # Simula delay

                # Esegui ingestione
                result = asyncio.run(ingest_urls(urls_list))

                if result.get("status") == "success":
                    st.success(
                        f"✅ Ingestione completata! {result.get('chunks_processed', 0)} chunk processati"
                    )

                    # Aggiungi a URL memorizzati
                    st.session_state.ingested_urls.extend(urls_list)

                    # Mostra statistiche
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("URL Processati", len(urls_list))
                    with col2:
                        st.metric("Chunk Creati", result.get("chunks_processed", 0))
                    with col3:
                        st.metric(
                            "Tempo",
                            f"{result.get('processing_time_ms', 0) / 1000:.2f}s",
                        )
                else:
                    st.error(
                        f"❌ Errore: {result.get('message', 'Errore sconosciuto')}"
                    )

        # Mostra URL recentemente ingeriti
        if st.session_state.ingested_urls:
            st.divider()
            st.subheader("📚 Documenti Recentemente Aggiunti")

            recent_urls = st.session_state.ingested_urls[-10:]  # Ultimi 10
            for idx, url in enumerate(reversed(recent_urls), 1):
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(f"{idx}. [{url}]({url})")
                with col2:
                    st.caption("✅ Indicizzato")

    # Tab 3: Analisi
    with tab3:
        st.header("📊 Dashboard Analisi")

        # Ottieni statistiche
        stats = asyncio.run(get_system_stats())

        if stats:
            # Metriche principali
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                total_docs = (
                    stats.get("retrieval", {})
                    .get("vector_store", {})
                    .get("total_points", 0)
                )
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric("📄 Documenti Totali", total_docs)
                st.markdown("</div>", unsafe_allow_html=True)

            with col2:
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric("🔍 Ricerche Oggi", len(st.session_state.search_history))
                st.markdown("</div>", unsafe_allow_html=True)

            with col3:
                avg_confidence = sum(
                    s.get("confidence", 0) for s in st.session_state.search_history
                ) / max(len(st.session_state.search_history), 1)
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric("🎯 Confidenza Media", f"{avg_confidence:.2%}")
                st.markdown("</div>", unsafe_allow_html=True)

            with col4:
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.metric("📥 URL Ingeriti", len(st.session_state.ingested_urls))
                st.markdown("</div>", unsafe_allow_html=True)

            st.divider()

            # Configurazione sistema
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("⚙️ Configurazione Retrieval")
                config = stats.get("configuration", {})
                retrieval_config = config.get("retrieval", {})

                config_df = pd.DataFrame(
                    [
                        {
                            "Parametro": "K Dense",
                            "Valore": retrieval_config.get("k_dense", "N/A"),
                        },
                        {
                            "Parametro": "K Lexical",
                            "Valore": retrieval_config.get("k_lexical", "N/A"),
                        },
                        {
                            "Parametro": "K Final",
                            "Valore": retrieval_config.get("k_final", "N/A"),
                        },
                    ]
                )
                st.dataframe(config_df, width="stretch", hide_index=True)

            with col2:
                st.subheader("🧩 Configurazione Chunking")
                chunking_config = config.get("chunking", {})

                chunking_df = pd.DataFrame(
                    [
                        {
                            "Parametro": "Parent Max Tokens",
                            "Valore": chunking_config.get("parent_max_tokens", "N/A"),
                        },
                        {
                            "Parametro": "Child Proc Tokens",
                            "Valore": chunking_config.get(
                                "child_proc_max_tokens", "N/A"
                            ),
                        },
                        {
                            "Parametro": "Child Param Tokens",
                            "Valore": chunking_config.get(
                                "child_param_max_tokens", "N/A"
                            ),
                        },
                    ]
                )
                st.dataframe(chunking_df, width="stretch", hide_index=True)

            # Grafico tipo query
            if st.session_state.search_history:
                st.divider()
                st.subheader("📈 Distribuzione Tipi Query")

                # Conta tipi di query (simulato)
                query_types = ["parameter", "procedure", "error", "general"]
                counts = [
                    len([h for h in st.session_state.search_history if i % 4 == idx])
                    for idx, i in enumerate(range(4))
                ]

                chart_data = pd.DataFrame({"Tipo": query_types, "Conteggio": counts})

                st.bar_chart(chart_data.set_index("Tipo"))

    # Tab 4: Cronologia
    with tab4:
        st.header("📜 Cronologia Ricerche")

        if st.session_state.search_history:
            # Pulsante pulizia
            if st.button("🗑️ Pulisci Cronologia"):
                st.session_state.search_history = []
                st.rerun()

            # Mostra cronologia
            history_df = pd.DataFrame(st.session_state.search_history)
            history_df["timestamp"] = pd.to_datetime(history_df["timestamp"])
            history_df = history_df.sort_values("timestamp", ascending=False)

            for idx, row in history_df.iterrows():
                with st.expander(
                    f"🕐 {row['timestamp'].strftime('%H:%M:%S')} - {row['query'][:50]}..."
                ):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**Query completa**: {row['query']}")
                    with col2:
                        st.metric("Confidenza", f"{row.get('confidence', 0):.2%}")

                    # Pulsante per ripetere ricerca
                    if st.button(f"🔄 Ripeti", key=f"repeat_{idx}"):
                        st.session_state.repeat_query = row["query"]
                        st.rerun()
        else:
            st.info("📭 Nessuna ricerca effettuata")

    # Footer
    st.divider()
    st.caption(
        "🤖 RAG Gestionale v1.0 - Sistema intelligente per documentazione di gestionali"
    )


if __name__ == "__main__":
    main()
