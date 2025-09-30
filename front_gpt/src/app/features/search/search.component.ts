import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatChipsModule } from '@angular/material/chips';
import { MatDividerModule } from '@angular/material/divider';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatTooltipModule } from '@angular/material/tooltip';

import { NotificationService } from '../../core/services/notification.service';
import { RagApiService } from '../../core/services/rag-api.service';
import { RagStore } from '../../core/state/rag-store.service';
import {
  HealthResponse,
  LlmConfig,
  SearchFilters,
  SearchRequest
} from '../../core/models/rag.models';
import { MetricCardComponent } from '../../shared/components/metric-card/metric-card.component';
import { SourceListComponent } from '../../shared/components/source-list/source-list.component';

@Component({
  selector: 'app-search-page',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatChipsModule,
    MatDividerModule,
    MatIconModule,
    MatCheckboxModule,
    MatProgressBarModule,
    MatSlideToggleModule,
    MatTooltipModule,
    MetricCardComponent,
    SourceListComponent
  ],
  templateUrl: './search.component.html',
  styleUrl: './search.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class SearchPageComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly ragApi = inject(RagApiService);
  private readonly store = inject(RagStore);
  private readonly notification = inject(NotificationService);

  readonly searchForm = this.fb.nonNullable.group({
    query: ['', [Validators.required, Validators.minLength(3)]],
    module: ['Tutti'],
    contentType: ['Tutti'],
    topK: [5],
    includeSources: [true],
    llmEnabled: [false],
    generationMode: ['template'],
    apiKey: ['']
  });

  readonly modules = ['Tutti', 'Contabilita', 'Fatturazione', 'Magazzino', 'HR', 'Desktop Teseo7'];
  readonly contentTypes = ['Tutti', 'parameter', 'procedure', 'error', 'general'];
  readonly generationModes: LlmConfig['generation_mode'][] = ['hybrid', 'llm', 'template'];

  readonly isSearching = signal(false);
  readonly searchDurationMs = signal<number | null>(null);
  readonly health = signal<HealthResponse | null>(null);

  readonly lastSearchResult = computed(() => this.store.lastSearchResult());
  readonly searchHistory = computed(() => this.store.searchHistory());
  ngOnInit(): void {
    this.loadHealth();
  }

  onSubmit(): void {
    if (this.searchForm.invalid) {
      this.searchForm.markAllAsTouched();
      return;
    }

    const request = this.buildSearchRequest();

    this.isSearching.set(true);
    const start = performance.now();

    this.ragApi.search(request).subscribe({
      next: (response) => {
        const duration = performance.now() - start;
        this.searchDurationMs.set(duration);

        this.store.setLastSearchResult(response);
        this.store.addSearchHistory({
          query: response.query,
          timestamp: new Date().toISOString(),
          confidence: response.confidence,
          queryType: response.query_type
        });

        this.notification.success('Risposta generata dal motore RAG');
      },
      error: () => {
        this.searchDurationMs.set(null);
      },
      complete: () => this.isSearching.set(false)
    });
  }

  get llmConfigured(): boolean {
    const services = this.health()?.services ?? {};
    return services['llm'] === 'enabled';
  }

  private buildSearchRequest(): SearchRequest {
    const value = this.searchForm.getRawValue();
    const filters: SearchFilters = {};

    if (value.module && value.module !== 'Tutti') {
      filters['module'] = value.module;
    }

    if (value.contentType && value.contentType !== 'Tutti') {
      filters['content_type'] = value.contentType;
    }

    const topK = Number(value.topK ?? 5);
    const normalizedTopK = Number.isFinite(topK) && topK > 0 ? Math.min(topK, 20) : 5;
    const includeSources = value.includeSources ?? true;
    const generationMode = (value.generationMode ?? 'template') as LlmConfig['generation_mode'];

    const payload: SearchRequest = {
      query: value.query.trim(),
      filters,
      top_k: normalizedTopK,
      include_sources: includeSources
    };

    if (value.llmEnabled) {
      payload.llm_config = {
        enabled: true,
        api_key: value.apiKey?.trim() || undefined,
        generation_mode: generationMode
      };
    }

    return payload;
  }

  private loadHealth(): void {
    this.ragApi.health().subscribe({
      next: (res) => {
        this.health.set(res);
        this.store.setSystemStats(res.stats);

        if (res.services['llm'] === 'enabled') {
          this.searchForm.patchValue({
            llmEnabled: true,
            generationMode: 'hybrid'
          });
        }
      },
      error: () => {
        this.health.set(null);
      }
    });
  }
}









