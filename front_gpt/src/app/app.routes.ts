import { Routes } from '@angular/router';

import { SearchPageComponent } from './features/search/search.component';
import { IngestPageComponent } from './features/ingest/ingest.component';
import { AnalyticsPageComponent } from './features/analytics/analytics.component';
import { HistoryPageComponent } from './features/history/history.component';

export const routes: Routes = [
  { path: '', redirectTo: 'search', pathMatch: 'full' },
  { path: 'search', component: SearchPageComponent, title: 'Ricerca | RAG Gestionale' },
  { path: 'ingest', component: IngestPageComponent, title: 'Ingestione | RAG Gestionale' },
  { path: 'analytics', component: AnalyticsPageComponent, title: 'Analisi | RAG Gestionale' },
  { path: 'history', component: HistoryPageComponent, title: 'Cronologia | RAG Gestionale' },
  { path: '**', redirectTo: 'search' }
];
