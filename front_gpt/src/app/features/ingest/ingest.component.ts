import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDividerModule } from '@angular/material/divider';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatListModule } from '@angular/material/list';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTooltipModule } from '@angular/material/tooltip';

import { NotificationService } from '../../core/services/notification.service';
import { RagApiService } from '../../core/services/rag-api.service';
import { RagStore } from '../../core/state/rag-store.service';
import { MetricCardComponent } from '../../shared/components/metric-card/metric-card.component';

@Component({
  selector: 'app-ingest-page',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatDividerModule,
    MatProgressBarModule,
    MatTooltipModule,
    MatListModule,
    MetricCardComponent
  ],
  templateUrl: './ingest.component.html',
  styleUrl: './ingest.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class IngestPageComponent {
  private readonly fb = inject(FormBuilder);
  private readonly ragApi = inject(RagApiService);
  private readonly store = inject(RagStore);
  private readonly notification = inject(NotificationService);

  readonly ingestForm = this.fb.nonNullable.group({
    urls: ['', [Validators.required, Validators.minLength(5)]]
  });

  readonly isIngesting = signal(false);
  readonly ingestOutcome = signal<{ chunks: number; timeMs: number } | null>(null);

  readonly ingestedDocuments = this.store.ingestedDocuments;
  readonly totalIngested = this.store.totalIngested;


  get parsedUrls(): string[] {
    const raw = this.ingestForm.getRawValue().urls;
    return raw
      .split(/\\r\?\\n/)
      .map((line) => line.trim())
      .filter((line) => !!line);
  }

  ingest(): void {
    if (this.ingestForm.invalid) {
      this.ingestForm.markAllAsTouched();
      return;
    }

    const urls = this.parsedUrls;
    if (!urls.length) {
      this.notification.info('Inserisci almeno un URL da indicizzare.');
      return;
    }

    this.isIngesting.set(true);
    this.ingestOutcome.set(null);

    this.ragApi.ingest({ urls }).subscribe({
      next: (response) => {
        this.notification.success(`Ingestione completata: ${response.chunks_processed} chunk`);
        this.store.addIngestedDocuments(urls);
        this.ingestOutcome.set({
          chunks: response.chunks_processed,
          timeMs: response.processing_time_ms
        });
        this.ingestForm.reset({ urls: '' });
      },
      complete: () => this.isIngesting.set(false)
    });
  }
}




