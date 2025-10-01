import { CommonModule } from '@angular/common';
import { Component, Input, OnInit, ViewChild, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatMenuModule, MatMenuTrigger } from '@angular/material/menu';
import { MatTooltipModule } from '@angular/material/tooltip';

import { ApiConfigService } from '../../../core/services/api-config.service';
import { NotificationService } from '../../../core/services/notification.service';

@Component({
  selector: 'app-api-settings',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatMenuModule,
    MatTooltipModule
  ],
  templateUrl: './api-settings.component.html',
  styleUrl: './api-settings.component.scss'
})
export class ApiSettingsComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly apiConfig = inject(ApiConfigService);
  private readonly notification = inject(NotificationService);

  @Input() appearance: 'panel' | 'toolbar' = 'panel';
  @ViewChild(MatMenuTrigger) menuTrigger?: MatMenuTrigger;

  readonly baseUrl = signal('');

  readonly form = this.fb.nonNullable.group({
    apiBaseUrl: ['', [Validators.required, Validators.pattern(/^https?:\/\//i)]]
  });
  ngOnInit(): void {
    const current = this.apiConfig.apiBaseUrl;
    this.form.patchValue({ apiBaseUrl: current });
    this.baseUrl.set(current);
  }

  submit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    const value = this.form.getRawValue().apiBaseUrl;
    this.apiConfig.updateBaseUrl(value);
    this.baseUrl.set(value);
    this.notification.success('Endpoint API aggiornato');

    if (this.menuTrigger) {
      this.menuTrigger.closeMenu();
    }
  }
}


