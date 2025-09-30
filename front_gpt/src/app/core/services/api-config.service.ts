import { Injectable, Signal, signal } from '@angular/core';

import { environment } from '../../../environments/environment';

const STORAGE_KEY = 'rag_gestionale.apiBaseUrl';

@Injectable({ providedIn: 'root' })
export class ApiConfigService {
  private readonly baseUrlSignal = signal<string>(this.loadInitialBaseUrl());

  get baseUrl(): Signal<string> {
    return this.baseUrlSignal.asReadonly();
  }

  get apiBaseUrl(): string {
    return this.baseUrlSignal();
  }

  updateBaseUrl(url: string): void {
    const sanitized = url.trim().replace(/\/$/, '');
    this.baseUrlSignal.set(sanitized);

    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, sanitized);
    }
  }

  private loadInitialBaseUrl(): string {
    if (typeof localStorage !== 'undefined') {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        return stored;
      }
    }

    return environment.apiBaseUrl;
  }
}
