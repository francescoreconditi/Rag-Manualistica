import { CommonModule } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatDividerModule } from '@angular/material/divider';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';

import { NotificationService } from '../../core/services/notification.service';
import { RagStore } from '../../core/state/rag-store.service';
import { SearchHistoryEntry } from '../../core/models/rag.models';

@Component({
  selector: 'app-history-page',
  standalone: true,
  imports: [CommonModule, MatCardModule, MatIconModule, MatListModule, MatButtonModule, MatDividerModule],
  templateUrl: './history.component.html',
  styleUrl: './history.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class HistoryPageComponent {
  private readonly store = inject(RagStore);
  private readonly notification = inject(NotificationService);

  readonly history = this.store.searchHistory;
  readonly lastSearch = this.store.lastSearchResult;
  readonly copying = signal<string | null>(null);


  async copy(entry: SearchHistoryEntry): Promise<void> {
    if (!navigator?.clipboard) {
      this.notification.error('Clipboard non disponibile nel browser.');
      return;
    }

    try {
      this.copying.set(entry.query);
      await navigator.clipboard.writeText(entry.query);
      this.notification.success('Query copiata negli appunti');
    } finally {
      this.copying.set(null);
    }
  }

  clear(): void {
    this.store.clearSearchHistory();
    this.notification.info('Cronologia ricerche svuotata');
  }
}


