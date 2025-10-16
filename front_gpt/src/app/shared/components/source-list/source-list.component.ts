import { CommonModule } from '@angular/common';
import { Component, Input, inject } from '@angular/core';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatButtonModule } from '@angular/material/button';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDividerModule } from '@angular/material/divider';

import { SearchResult } from '../../../core/models/rag.models';
import { ApiConfigService } from '../../../core/services/api-config.service';

@Component({
  selector: 'app-source-list',
  standalone: true,
  imports: [
    CommonModule,
    MatExpansionModule,
    MatIconModule,
    MatChipsModule,
    MatButtonModule,
    MatTooltipModule,
    MatDividerModule
  ],
  templateUrl: './source-list.component.html',
  styleUrl: './source-list.component.scss'
})
export class SourceListComponent {
  private readonly apiConfig = inject(ApiConfigService);

  @Input({ required: true }) sources: SearchResult[] | null = [];

  getImageUrl(relativeUrl: string): string {
    // relativeUrl arriva come "/images/hash/filename.png"
    return `${this.apiConfig.apiBaseUrl}${relativeUrl}`;
  }
}
