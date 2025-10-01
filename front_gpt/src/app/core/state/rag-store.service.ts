import { Injectable, computed, signal } from '@angular/core';

import {
  IngestedDocument,
  RagResponse,
  SearchHistoryEntry,
  SystemStats
} from '../models/rag.models';

@Injectable({ providedIn: 'root' })
export class RagStore {
  private readonly searchHistorySignal = signal<SearchHistoryEntry[]>([]);
  private readonly ingestedDocumentsSignal = signal<IngestedDocument[]>([]);
  private readonly lastSearchResultSignal = signal<RagResponse | null>(null);
  private readonly systemStatsSignal = signal<SystemStats | null>(null);

  readonly searchHistory = this.searchHistorySignal.asReadonly();
  readonly ingestedDocuments = this.ingestedDocumentsSignal.asReadonly();
  readonly lastSearchResult = this.lastSearchResultSignal.asReadonly();
  readonly systemStats = this.systemStatsSignal.asReadonly();

  readonly totalIngested = computed(() => this.ingestedDocumentsSignal().length);

  addSearchHistory(entry: SearchHistoryEntry): void {
    this.searchHistorySignal.update((history) => [entry, ...history].slice(0, 100));
  }

  clearSearchHistory(): void {
    this.searchHistorySignal.set([]);
  }

  setLastSearchResult(result: RagResponse | null): void {
    this.lastSearchResultSignal.set(result);
  }

  addIngestedDocuments(urls: string[]): void {
    const timestamp = new Date().toISOString();
    const entries: IngestedDocument[] = urls.map((url) => ({ url, ingestedAt: timestamp }));

    this.ingestedDocumentsSignal.update((docs) => [...entries, ...docs].slice(0, 200));
  }

  setSystemStats(stats: SystemStats | null): void {
    this.systemStatsSignal.set(stats);
  }
}
