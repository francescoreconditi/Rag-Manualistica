import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  HealthResponse,
  IngestRequest,
  IngestResponse,
  RagResponse,
  SearchRequest,
  SystemStats
} from '../models/rag.models';
import { ApiConfigService } from './api-config.service';

@Injectable({ providedIn: 'root' })
export class RagApiService {
  constructor(
    private readonly http: HttpClient,
    private readonly apiConfig: ApiConfigService
  ) {}

  health(): Observable<HealthResponse> {
    return this.http.get<HealthResponse>(this.buildUrl('/health'));
  }

  search(request: SearchRequest): Observable<RagResponse> {
    return this.http.post<RagResponse>(this.buildUrl('/search'), request);
  }

  ingest(request: IngestRequest): Observable<IngestResponse> {
    return this.http.post<IngestResponse>(this.buildUrl('/ingest'), request);
  }

  stats(): Observable<SystemStats> {
    return this.http.get<SystemStats>(this.buildUrl('/stats'));
  }

  private buildUrl(path: string): string {
    const base = this.apiConfig.apiBaseUrl;
    return `${base}${path}`;
  }
}
