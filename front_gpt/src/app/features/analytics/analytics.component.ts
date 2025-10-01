import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatDividerModule } from '@angular/material/divider';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTableModule } from '@angular/material/table';

import { RagApiService } from '../../core/services/rag-api.service';
import { RagStore } from '../../core/state/rag-store.service';
import { MetricCardComponent } from '../../shared/components/metric-card/metric-card.component';

interface QueryDistributionItem {
  type: string;
  count: number;
  percentage: number;
}

@Component({
  selector: 'app-analytics-page',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatDividerModule,
    MatIconModule,
    MatListModule,
    MatProgressBarModule,
    MatTableModule,
    MetricCardComponent
  ],
  templateUrl: './analytics.component.html',
  styleUrl: './analytics.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class AnalyticsPageComponent implements OnInit {
  private readonly ragApi = inject(RagApiService);
  private readonly store = inject(RagStore);

  readonly isLoading = signal(false);
  readonly stats = this.store.systemStats;
  readonly searchHistory = this.store.searchHistory;

  readonly queryDistribution = computed<QueryDistributionItem[]>(() => {
    const history = this.searchHistory();
    if (!history.length) {
      return [];
    }

    const counts = history.reduce<Record<string, number>>((acc, entry) => {
      const type = entry.queryType ?? 'general';
      acc[type] = (acc[type] ?? 0) + 1;
      return acc;
    }, {});

    const total = history.length;
    return Object.entries(counts)
      .map(([type, count]) => ({
        type,
        count,
        percentage: Math.round((count / total) * 100)
      }))
      .sort((a, b) => b.count - a.count);
  });

  readonly averageConfidence = computed(() => {
    const history = this.searchHistory();
    if (!history.length) {
      return 0;
    }

    return (
      history.reduce((sum, item) => sum + (item.confidence ?? 0), 0) /
      history.length
    );
  });
  ngOnInit(): void {
    this.refreshStats();
  }

  refreshStats(): void {
    this.isLoading.set(true);
    this.ragApi.stats().subscribe({
      next: (stats) => this.store.setSystemStats(stats),
      complete: () => this.isLoading.set(false)
    });
  }

  get configurationRows(): Array<{ parameter: string; value: string | number | boolean | null | undefined }> {
    const config = this.stats()?.configuration;
    if (!config) {
      return [];
    }

    return [
      { parameter: 'Parent tokens', value: config.chunking?.parent_max_tokens },
      { parameter: 'Child proc tokens', value: config.chunking?.child_proc_max_tokens },
      { parameter: 'Child param tokens', value: config.chunking?.child_param_max_tokens },
      { parameter: 'K dense', value: config.retrieval?.k_dense },
      { parameter: 'K lexical', value: config.retrieval?.k_lexical },
      { parameter: 'K finale', value: config.retrieval?.k_final },
      { parameter: 'Embedding model', value: config.embedding?.model },
      { parameter: 'Embedding batch', value: config.embedding?.batch_size },
      { parameter: 'LLM attivo', value: config.llm?.enabled },
      { parameter: 'LLM model', value: config.llm?.model }
    ];
  }

  trackByType(_index: number, item: QueryDistributionItem): string {
    return item.type;
  }
}


