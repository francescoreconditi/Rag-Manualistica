import { Component, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { NgFor } from '@angular/common';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatListModule } from '@angular/material/list';
import { MatDividerModule } from '@angular/material/divider';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBarModule } from '@angular/material/snack-bar';

import { ApiSettingsComponent } from './shared/components/api-settings/api-settings.component';

interface NavItem {
  icon: string;
  label: string;
  path: string;
  description: string;
}

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    NgFor,    MatToolbarModule,
    MatSidenavModule,
    MatButtonModule,
    MatIconModule,
    MatListModule,
    MatDividerModule,
    MatTooltipModule,
    MatSnackBarModule,
    ApiSettingsComponent
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent {
  readonly title = 'RAG Gestionale';
  readonly sidenavOpened = signal(true);

  readonly navItems: NavItem[] = [
    {
      icon: 'search',
      label: 'Ricerca',
      path: '/search',
      description: 'Interroga i documenti con il motore RAG'
    },
    {
      icon: 'cloud_upload',
      label: 'Ingestione',
      path: '/ingest',
      description: 'Indicizza nuovi manuali e risorse'
    },
    {
      icon: 'analytics',
      label: 'Analisi',
      path: '/analytics',
      description: 'Monitora stato sistema e metadati'
    },
    {
      icon: 'history',
      label: 'Cronologia',
      path: '/history',
      description: 'Rivedi e ripeti le ricerche recenti'
    }
  ];

  toggleSidenav(): void {
    this.sidenavOpened.update((isOpen) => !isOpen);
  }
}


